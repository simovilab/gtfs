#!/usr/bin/env python3
"""Build the explorer site and serve it locally for review.

Rebuilds web/dist/index.html, then serves it at http://localhost:8777 until
interrupted with Ctrl+C.

Usage:
    uv run converters/schedule/serve_site.py
    uv run converters/schedule/serve_site.py --port 9000 --no-build
"""

from __future__ import annotations

import argparse
import functools
import http.server
import socketserver
import sys
import webbrowser
from pathlib import Path

import yaml2site

DIST_DIR = yaml2site.OUTPUT_PATH.parent


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8777)
    parser.add_argument("--no-build", action="store_true", help="serve without rebuilding")
    parser.add_argument("--no-open", action="store_true", help="do not open a browser")
    args = parser.parse_args()

    if not args.no_build:
        if (code := yaml2site.main()) != 0:
            return code

    if not (DIST_DIR / "index.html").exists():
        print(f"ERROR: nothing to serve; {DIST_DIR / 'index.html'} is missing", file=sys.stderr)
        return 2

    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(DIST_DIR))
    socketserver.TCPServer.allow_reuse_address = True

    try:
        with socketserver.TCPServer(("127.0.0.1", args.port), handler) as httpd:
            url = f"http://localhost:{args.port}/"
            print(f"\nServing {DIST_DIR} at {url}\nPress Ctrl+C to stop.\n")
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
