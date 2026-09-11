#!/usr/bin/env python3
"""The parts of the field explorer that do not depend on which feed it shows.

There are two explorers — GTFS Schedule and GTFS Realtime — and they are the
same page twice: same layout, same two-layer draft model, same schema-driven
form, same write-back. Only the reference being browsed and the annotation
vocabulary differ, and both of those arrive as data.

So the page shell, the assets and the embedding live here, and each feed's
builder is left with the one job that really is its own: turning its reference
file into the table/field payload the page draws.

The per-feed builder passes a PAGE block naming the files behind the page and
the endpoint that writes them, which is what keeps the Realtime page from
claiming to write schedule.ui.yaml.
"""

from __future__ import annotations

import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = Path(__file__).resolve().parents[2]
SITE_DIR = ROOT / "converters" / "site"

LANGS = ("es", "en", "pt")

# The nav shown on every page, in one place so adding a third page is one edit
# rather than three. Keyed by the id each builder passes as `current`.
PAGES = (
    ("schedule", "index.html", "GTFS Schedule"),
    ("realtime", "realtime.html", "GTFS Realtime"),
    ("composites", "composites.html", "Composites"),
)


def nav(current: str) -> list[dict]:
    return [{"href": href, "label": label, "current": key == current}
            for key, href, label in PAGES]


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


def asset(name: str, directory: Path | None = None) -> str:
    """Read a CSS/JS asset verbatim.

    These are plain files rather than Jinja templates so they stay valid,
    lintable CSS and JavaScript, and so nothing in them is mistaken for
    template syntax.
    """
    return ((directory or SITE_DIR) / name).read_text(encoding="utf-8")


def render(output: Path, *, page: dict, data: dict, form: dict,
           suggest_js: str, title: str, heading: str, current: str) -> None:
    """Write one explorer page."""
    env = Environment(
        loader=FileSystemLoader(SITE_DIR),
        autoescape=select_autoescape(["html"]),
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        env.get_template("explorer.html.jinja").render(
            page_title=title,
            heading=heading,
            nav=nav(current),
            page_json=embed(page),
            data_json=embed(data),
            form_json=embed(form),
            style=asset("style.css"),
            state_js=asset("state.js"),
            strings_js=asset("strings.js"),
            render_js=asset("render.js"),
            suggest_js=suggest_js,
            editor_js=asset("editor.js"),
            export_js=asset("export.js"),
        ),
        encoding="utf-8",
    )
