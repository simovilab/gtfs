#!/usr/bin/env python3
"""Build the explorer site, serve it locally, and let it write annotations back.

Rebuilds web/dist/index.html and serves it at http://localhost:8777 until
interrupted with Ctrl+C.

Two endpoints sit alongside the static files:

    GET  /api/status       does this server accept writes?
    PUT  /api/annotations  merge a changeset into schedule.ui.yaml

The page probes /api/status at load. On GitHub Pages nothing answers, so it
falls back to exporting a YAML patch to copy by hand; here, the "write to file"
button appears. Writes go through ui_yaml_io, which keeps the file's comments.

The endpoints only ever touch serializers/schedule/schedule.ui.yaml, only
accept requests from this server's own origin, and only write payloads that
already validate against schedule.ui.schema.json.

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

import ui_yaml_io
import yaml2site

# Same reason as in yaml2site: these converters run as scripts, not a package.
sys.path.insert(0, str(yaml2site.ROOT / "converters" / "ui"))
import composites2site  # noqa: E402

DIST_DIR = yaml2site.OUTPUT_PATH.parent
MAX_BODY = 4 * 1024 * 1024
LOCAL_HOSTS = ("localhost", "127.0.0.1")


class Handler(http.server.SimpleHTTPRequestHandler):
    """Static files, plus the two annotation endpoints."""

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
                "path": str(yaml2site.UI_PATH.relative_to(yaml2site.ROOT)),
            })
        return super().do_GET()

    def do_PUT(self):  # noqa: N802
        if self.path.rstrip("/") != "/api/annotations":
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
            counts = write_annotations(changes)
        except jsonschema.ValidationError as e:
            return self._json(422, {"errors": [f"{'.'.join(map(str, e.path))}: {e.message}"]})
        except Exception as e:  # surfaced to the page rather than swallowed
            return self._json(500, {"error": str(e)})

        code = yaml2site.main()
        return self._json(200, {"counts": counts, "rebuilt": code == 0})

    def log_message(self, fmt, *args):
        if not self.path.startswith("/api/"):
            return
        sys.stderr.write(f"  {self.command} {self.path} -> {args[1]}\n")


def write_annotations(changes: dict) -> dict[str, int]:
    """Validate a changeset, then merge it into schedule.ui.yaml.

    Validation runs on the whole merged document, not just the incoming
    entries, so a change can never leave the file in a state CI would reject.
    """
    schema = json.loads(yaml2site.SCHEMA_PATH.read_text(encoding="utf-8"))
    document = ui_yaml_io.load(yaml2site.UI_PATH)
    counts = ui_yaml_io.apply_changes(document, changes)

    # json round-trip: validate plain data, not ruamel's comment-carrying nodes.
    jsonschema.validate(json.loads(json.dumps(document)), schema)

    ui_yaml_io.dump(document, yaml2site.UI_PATH)
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
        # The composites page is a sibling in the same directory, so the nav
        # link between the two pages resolves during a local preview too.
        if composites2site.main() != 0:
            print("WARNING: composites page not rebuilt; the nav link will "
                  "serve a stale page or 404", file=sys.stderr)

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
                print(f"Edits save to {yaml2site.UI_PATH.relative_to(yaml2site.ROOT)} "
                      f"(--read-only to disable).")
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
