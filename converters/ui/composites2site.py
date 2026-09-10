#!/usr/bin/env python3
"""Build the composites page.

Writes web/dist/composites.html, a sibling of the field explorer that
yaml2site.py builds. Same approach: data resolved at build time and embedded,
so the result is a static page with no runtime requests.

The page is read-only. composites.yaml is edited by hand and checked by
converters/ui/composites.py, which is the CI step.

Usage:
    uv run converters/ui/composites2site.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema
from jinja2 import Environment, FileSystemLoader, select_autoescape

import composites as model

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_DIR = ROOT / "converters" / "ui" / "templates"
ASSET_DIR = TEMPLATE_DIR / "site"
# The shared stylesheet lives with the field explorer and is included first;
# composites.css only adds what this page needs on top of it.
SHARED_CSS = ROOT / "converters" / "schedule" / "templates" / "site" / "style.css"
OUTPUT_PATH = ROOT / "web" / "dist" / "composites.html"


def embed(payload: dict) -> str:
    """Serialize for a <script type="application/json"> block.

    Escaping the three characters that could close the block early is what
    keeps a description in the reference from being able to inject markup.
    """
    return (
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )


def main() -> int:
    try:
        data = model.load()
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    except jsonschema.ValidationError as e:
        location = ".".join(str(p) for p in e.path) or "(root)"
        print(f"ERROR: composites.yaml does not match its schema\n"
              f"  at {location}: {e.message}", file=sys.stderr)
        return 1

    errors, _ = model.check(data["document"], data)
    if errors:
        # Building a page from a file with dangling references would show a
        # screen that cannot exist. Refuse, and point at the checker.
        print("ERROR: composites.yaml has unresolved references; "
              "run converters/ui/composites.py for the list", file=sys.stderr)
        return 1

    data.pop("document")

    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(["html"]),
    )
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        env.get_template("composites.html.jinja").render(
            data_json=embed(data),
            style=SHARED_CSS.read_text(encoding="utf-8"),
            composites_css=(ASSET_DIR / "composites.css").read_text(encoding="utf-8"),
            composites_js=(ASSET_DIR / "composites.js").read_text(encoding="utf-8"),
        ),
        encoding="utf-8",
    )

    stats = data["stats"]
    print(f"Wrote {OUTPUT_PATH}")
    print(f"Embedded {stats['composites']} composites, {stats['views']} views, "
          f"{stats['refs']} field references")
    return 0


if __name__ == "__main__":
    sys.exit(main())
