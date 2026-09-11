#!/usr/bin/env python3
"""Build the composites page.

Writes web/dist/composites.html, a sibling of the field explorer that
yaml2site.py builds. Same approach: data resolved at build time and embedded,
so the result is a static page with no runtime requests.

Three payloads go into the page:

    doc       the authored composites.yaml, which the editor treats as the
              baseline its draft is diffed against
    catalog   every reference that could be typed, resolved once here so the
              browser can re-resolve an edited document on its own
    form      the vocabulary, read out of the JSON schema

Under serve_site.py the page can write composites.yaml back through
converters/ui/composites_io.py. On GitHub Pages nothing answers api/status and
it falls back to exporting a patch.

Usage:
    uv run converters/ui/composites2site.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema
import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape

import composites as model
import composites_form

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_DIR = ROOT / "converters" / "ui" / "templates"
ASSET_DIR = TEMPLATE_DIR / "site"
OUTPUT_PATH = ROOT / "web" / "dist" / "composites.html"

# The shared stylesheet and the nav both live with the explorers, which is what
# keeps this page looking like them and linking to all of them.
sys.path.insert(0, str(ROOT / "converters" / "site"))
import explorer  # noqa: E402

SHARED_CSS = explorer.SITE_DIR / "style.css"


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


def asset(name: str) -> str:
    """Read a CSS/JS asset verbatim.

    These are plain files rather than Jinja templates so they stay valid,
    lintable CSS and JavaScript, and so nothing in them is mistaken for
    template syntax.
    """
    return (ASSET_DIR / name).read_text(encoding="utf-8")


def options(catalog: dict) -> str:
    """The reference pick list, as <option> markup.

    Rendered server-side rather than built in JavaScript: 869 options created
    one at a time on load is visible work, and this is static text.
    """
    return "".join(
        f'<option value="{ref}">' for ref in sorted(catalog)
        if '"' not in ref and "<" not in ref
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

    document = data["document"]
    errors, _ = model.check(document, data)
    if errors:
        # Building a page from a file with dangling references would show a
        # screen that cannot exist. Refuse, and point at the checker.
        print("ERROR: composites.yaml has unresolved references; "
              "run converters/ui/composites.py for the list", file=sys.stderr)
        return 1

    spec = yaml.safe_load(model.SCHEDULE_PATH.read_text(encoding="utf-8"))
    realtime = yaml.safe_load(model.REALTIME_PATH.read_text(encoding="utf-8"))
    ui = yaml.safe_load(model.UI_PATH.read_text(encoding="utf-8")) or {}
    rt_ui = yaml.safe_load(model.REALTIME_UI_PATH.read_text(encoding="utf-8")) or {}
    browser = composites_form.build(model.COMPOSITES_SCHEMA, spec, realtime,
                                    ui.get("fields", {}), rt_ui.get("fields", {}),
                                    document)

    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(["html"]),
    )
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        env.get_template("composites.html.jinja").render(
            nav=explorer.nav("composites"),
            doc_json=embed(document),
            catalog_json=embed(browser["catalog"]),
            form_json=embed(browser["form"]),
            refs_options=options(browser["catalog"]),
            style=SHARED_CSS.read_text(encoding="utf-8"),
            composites_css=asset("composites.css"),
            state_js=asset("composites_state.js"),
            composites_js=asset("composites.js"),
            editor_js=asset("composites_editor.js"),
            export_js=asset("composites_export.js"),
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
