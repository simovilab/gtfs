#!/usr/bin/env python3
"""Build the explorer pages, serve them locally, and let them write back.

Rebuilds web/dist/ and serves it at http://localhost:8777 until interrupted
with Ctrl+C.

Four endpoints sit alongside the static files:

    GET  /api/status                does this server accept writes?
    PUT  /api/annotations           merge a changeset into schedule.ui.yaml
    PUT  /api/realtime-annotations  merge a changeset into realtime.ui.yaml
    PUT  /api/composites            merge a changeset into composites.yaml

Each page probes /api/status at load. On GitHub Pages nothing answers, so a
page falls back to exporting a YAML patch to copy by hand; here, the "write to
file" button appears. Writes go through ui_yaml_io, which keeps the comments.

The two annotation endpoints are one piece of code over two files: which file a
request writes, and which schema it must satisfy, is decided by the route and
never by the payload. Every endpoint only ever touches the one file it names,
only accepts requests from this server's own origin, and only writes payloads
that already validate against that file's schema.

Usage:
    uv run converters/schedule/serve_site.py
    uv run converters/schedule/serve_site.py --port 9000 --read-only
"""

from __future__ import annotations

import argparse
import http.server
import json
import socketserver
import sys
import webbrowser

import jsonschema

import yaml2site

# Same reason as in yaml2site: these converters run as scripts, not a package.
sys.path.insert(0, str(yaml2site.ROOT / "converters" / "site"))
sys.path.insert(0, str(yaml2site.ROOT / "converters" / "realtime"))
sys.path.insert(0, str(yaml2site.ROOT / "converters" / "ui"))
import composites  # noqa: E402
import composites2site  # noqa: E402
import realtime2site  # noqa: E402
import ui_yaml_io  # noqa: E402

# The two annotation files, by the route that writes each. Adding a feed is an
# entry here plus its builder, not another copy of the endpoint.
ANNOTATIONS = {
    "/api/annotations": yaml2site,
    "/api/realtime-annotations": realtime2site,
}

# Every page is rebuilt after any write. An annotation edit changes the badges
# the composites page shows, and a composite edit changes the usage tags on
# both explorers, so there is no such thing as a write that touches one page.
BUILDERS = (yaml2site, realtime2site, composites2site)

DIST_DIR = yaml2site.OUTPUT_PATH.parent
MAX_BODY = 4 * 1024 * 1024
LOCAL_HOSTS = ("localhost", "127.0.0.1")


class Handler(http.server.SimpleHTTPRequestHandler):
    """Static files, plus the write-back endpoints."""

    writable = True
    port = 0

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DIST_DIR), **kwargs)

    # ------------------------------------------------------------- helpers

    def _json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _same_origin(self) -> bool:
        """Reject cross-site writes and DNS-rebinding.

        A page on any other origin can reach a localhost port; requiring the
        Origin and Host headers to be this server's own is what stops one from
        rewriting the annotation file in the background.
        """
        host = (self.headers.get("Host") or "").split(":")[0]
        if host not in LOCAL_HOSTS:
            return False
        origin = self.headers.get("Origin") or ""
        return origin in (f"http://{h}:{self.port}" for h in LOCAL_HOSTS)

    def _body(self) -> dict | None:
        if "application/json" not in (self.headers.get("Content-Type") or ""):
            self._json(415, {"error": "expected application/json"})
            return None
        length = int(self.headers.get("Content-Length") or 0)
        if not 0 < length <= MAX_BODY:
            self._json(413, {"error": "empty or oversized body"})
            return None
        try:
            return json.loads(self.rfile.read(length))
        except json.JSONDecodeError as e:
            self._json(400, {"error": f"malformed JSON: {e}"})
            return None

    # ------------------------------------------------------------- routing

    def do_GET(self):  # noqa: N802 - http.server's naming
        if self.path.rstrip("/") == "/api/status":
            return self._json(200, {
                "writable": self.writable,
                "paths": {route: str(module.UI_PATH.relative_to(yaml2site.ROOT))
                          for route, module in ANNOTATIONS.items()},
            })
        return super().do_GET()

    def do_PUT(self):  # noqa: N802
        route = self.path.rstrip("/")
        if route not in (*ANNOTATIONS, "/api/composites"):
            return self._json(404, {"error": "no such endpoint"})
        if not self.writable:
            return self._json(403, {"error": "server started read-only"})
        if not self._same_origin():
            return self._json(403, {"error": "cross-origin write refused"})

        payload = self._body()
        if payload is None:
            return None

        changes = payload.get("changes")
        if not isinstance(changes, dict) or not changes:
            return self._json(400, {"error": "no changes given"})

        try:
            if route in ANNOTATIONS:
                counts = write_annotations(ANNOTATIONS[route], changes)
            else:
                counts = composites.write(changes)
        except jsonschema.ValidationError as e:
            return self._json(422, {"errors": [f"{'.'.join(map(str, e.path))}: {e.message}"]})
        except ValueError as e:  # references that resolve nowhere
            return self._json(422, {"errors": str(e).split("; ")})
        except Exception as e:  # surfaced to the page rather than swallowed
            return self._json(500, {"error": str(e)})

        rebuilt = all(builder.main() == 0 for builder in BUILDERS)
        return self._json(200, {"counts": counts, "rebuilt": rebuilt})

    def handle_one_request(self):
        """Serve one request, tolerating a reader that walks away.

        Reloading or navigating mid-response closes the socket while the file
        is still being copied. That is normal browsing, not a fault, so it is
        reported as one line instead of a traceback.
        """
        try:
            super().handle_one_request()
        except (BrokenPipeError, ConnectionResetError):
            self.close_connection = True
            sys.stderr.write(f"  {self.command or '?'} {self.path or '?'} "
                             f"-> client disconnected\n")

    def log_message(self, fmt, *args):
        if not self.path.startswith("/api/"):
            return
        sys.stderr.write(f"  {self.command} {self.path} -> {args[1]}\n")


def write_annotations(feed, changes: dict) -> dict[str, int]:
    """Validate a changeset, then merge it into that feed's annotation file.

    `feed` is the builder module, which already knows where its annotations and
    its schema live — so the route picks the file and the request cannot.

    Validation runs on the whole merged document, not just the incoming
    entries, so a change can never leave the file in a state CI would reject.
    The emission order comes from the schema too, which is what keeps an entry
    the editor rewrote shaped like the hand-written ones around it.
    """
    schema = json.loads(feed.SCHEMA_PATH.read_text(encoding="utf-8"))
    document = ui_yaml_io.load(feed.UI_PATH)
    counts = ui_yaml_io.apply_changes(document, changes, ui_yaml_io.key_order(schema))

    # json round-trip: validate plain data, not ruamel's comment-carrying nodes.
    jsonschema.validate(json.loads(json.dumps(document)), schema)

    ui_yaml_io.dump(document, feed.UI_PATH)
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8777)
    parser.add_argument("--no-build", action="store_true", help="serve without rebuilding")
    parser.add_argument("--no-open", action="store_true", help="do not open a browser")
    parser.add_argument("--read-only", action="store_true",
                        help="serve the page without the write-back endpoint")
    args = parser.parse_args()

    if not args.no_build:
        if (code := yaml2site.main()) != 0:
            return code
        # The other pages are siblings in the same directory, so the nav links
        # between them resolve during a local preview too.
        for builder in BUILDERS[1:]:
            if builder.main() != 0:
                print(f"WARNING: {builder.__name__} did not rebuild; a nav link "
                      f"will serve a stale page or 404", file=sys.stderr)

    if not (DIST_DIR / "index.html").exists():
        print(f"ERROR: nothing to serve; {DIST_DIR / 'index.html'} is missing", file=sys.stderr)
        return 2

    Handler.writable = not args.read_only
    Handler.port = args.port
    socketserver.TCPServer.allow_reuse_address = True

    try:
        with socketserver.TCPServer(("127.0.0.1", args.port), Handler) as httpd:
            url = f"http://localhost:{args.port}/"
            print(f"\nServing {DIST_DIR} at {url}")
            if Handler.writable:
                for module in ANNOTATIONS.values():
                    print(f"Edits save to "
                          f"{module.UI_PATH.relative_to(yaml2site.ROOT)}")
                print("(--read-only to disable.)")
            print("Press Ctrl+C to stop.\n")
            if not args.no_open:
                webbrowser.open(url)
            httpd.serve_forever()
    except OSError as e:
        print(f"ERROR: could not bind port {args.port}: {e}", file=sys.stderr)
        print("Try a different one with --port.", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nStopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
