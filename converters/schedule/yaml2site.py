#!/usr/bin/env python3
"""Build the static editor/validation explorer site.

Merges serializers/schedule/schedule.yaml (GTFS ground truth) with
serializers/schedule/schedule.ui.yaml (editor annotations) into a single
self-contained HTML page written to web/dist/index.html.

Data is embedded at build time rather than fetched at page load so the result
is a fully static page with no runtime requests, which is what GitHub Pages
serves best.

Usage:
    uv run converters/schedule/yaml2site.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape

import ui_form_model

ROOT = Path(__file__).resolve().parents[2]

# The composites model lives beside the other UI converters. It is imported by
# path rather than as a package because these converters are run as scripts.
sys.path.insert(0, str(ROOT / "converters" / "ui"))
import composites as composites_model  # noqa: E402
SPEC_PATH = ROOT / "serializers" / "schedule" / "schedule.yaml"
UI_PATH = ROOT / "serializers" / "schedule" / "schedule.ui.yaml"
SCHEMA_PATH = ROOT / "serializers" / "schedule" / "schedule.ui.schema.json"
TEMPLATE_DIR = ROOT / "converters" / "schedule" / "templates"
ASSET_DIR = TEMPLATE_DIR / "site"
OUTPUT_PATH = ROOT / "web" / "dist" / "index.html"

LANGS = ("es", "en", "pt")


def table_name(filename: str) -> str:
    """'stops.txt' -> 'stops'."""
    return filename.rsplit(".", 1)[0]


def normalize_options(options) -> list[dict]:
    """Flatten the spec's two enum shapes into one.

    Most enums are a flat list of {value, description}. A few (such as
    stops.wheelchair_boarding) group values under {category, values}.
    """
    if not options:
        return []
    groups: list[dict] = []
    flat: list[dict] = []
    for option in options:
        if "values" in option:
            groups.append(
                {
                    "category": option.get("category", ""),
                    "values": [
                        {"value": str(v.get("value", "")), "description": v.get("description", "")}
                        for v in option.get("values", [])
                    ],
                }
            )
        else:
            flat.append(
                {"value": str(option.get("value", "")), "description": option.get("description", "")}
            )
    if flat:
        groups.insert(0, {"category": "", "values": flat})
    return groups


def as_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return [str(v) for v in value]


def annotation_of(note: dict | None) -> dict | None:
    """Shape one annotation for the page.

    Absent optional keys are left out rather than emitted as null. The editor
    compares a submitted annotation against this baseline to decide whether a
    field still counts as changed, and `{"group": null}` would never compare
    equal to a form that simply omits an empty group.
    """
    if not note:
        return None
    shaped = {
        "component": note.get("component"),
        "validation": note.get("validation") or {},
        "i18n": note.get("i18n") or {},
    }
    for optional in ("group", "references"):
        if note.get(optional):
            shaped[optional] = note[optional]
    return shaped


def display_usage() -> dict[str, list[dict]]:
    """'routes.route_color' -> the composites that display it.

    A missing or broken composites file must not stop the field explorer from
    building: composites.py is the authority on whether that file is valid,
    and it fails on its own in CI.
    """
    try:
        model = composites_model.load()
    except Exception as e:  # noqa: BLE001 - reported, not swallowed
        print(f"WARNING: composites not resolved ({e}); "
              f"fields will show no usage", file=sys.stderr)
        return {}
    usage: dict[str, list[dict]] = {}
    for ref, uses in model["reverse"].items():
        feed, _, path = ref.partition(":")
        if feed == "schedule":
            usage.setdefault(path, []).extend(uses)
    return usage


def build_data(spec: dict, ui: dict) -> dict:
    annotations = ui.get("fields", {})
    usage = display_usage()
    tables = []

    for entry in spec.get("field_definitions", {}).get("files", []):
        table = table_name(entry["file"])
        fields = []

        for field in entry.get("fields", []) or []:
            key = f"{table}.{field['name']}"
            note = annotations.get(key)

            fields.append(
                {
                    "name": field["name"],
                    "key": key,
                    "type": field.get("type", ""),
                    "presence": field.get("presence", ""),
                    "description": field.get("description", ""),
                    "foreign_key": field.get("foreign_key"),
                    "conditions": as_list(field.get("conditions")),
                    "notes": as_list(field.get("notes")),
                    "options": normalize_options(field.get("options")),
                    "annotation": annotation_of(note),
                    "usage": usage.get(key, []),
                }
            )

        annotated = sum(1 for f in fields if f["annotation"])
        tables.append(
            {
                "name": table,
                "file": entry["file"],
                "presence": entry.get("presence", ""),
                "description": entry.get("description", ""),
                "fields": fields,
                "total": len(fields),
                "annotated": annotated,
            }
        )

    total = sum(t["total"] for t in tables)
    done = sum(t["annotated"] for t in tables)

    return {
        "metadata": spec.get("metadata", {}),
        "regions": ui.get("regions", {}),
        "tables": tables,
        "coverage": {
            "total": total,
            "annotated": done,
            "percent": round(100 * done / total, 1) if total else 0.0,
        },
        "langs": list(LANGS),
    }


def asset(name: str) -> str:
    """Read a CSS/JS asset verbatim.

    These are plain files rather than Jinja templates so they stay valid,
    lintable CSS and JavaScript, and so nothing in them is mistaken for
    template syntax.
    """
    return (ASSET_DIR / name).read_text(encoding="utf-8")


def embed(payload: dict) -> str:
    """Serialize for a <script type="application/json"> block.

    Escaping the three characters that could close the block early is what
    keeps a description in schedule.yaml from being able to inject markup.
    """
    return (
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )


def main() -> int:
    for path in (SPEC_PATH, UI_PATH, SCHEMA_PATH):
        if not path.exists():
            print(f"ERROR: missing required file: {path}", file=sys.stderr)
            return 2

    spec = yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))
    ui = yaml.safe_load(UI_PATH.read_text(encoding="utf-8"))
    data = build_data(spec, ui)

    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(["html"]),
    )
    template = env.get_template("site.html.jinja")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        template.render(
            data_json=embed(data),
            form_json=embed(ui_form_model.load(SCHEMA_PATH)),
            style=asset("style.css"),
            state_js=asset("state.js"),
            strings_js=asset("strings.js"),
            render_js=asset("render.js"),
            editor_js=asset("editor.js"),
            export_js=asset("export.js"),
        ),
        encoding="utf-8",
    )

    coverage = data["coverage"]
    print(f"Wrote {OUTPUT_PATH}")
    print(
        f"Embedded {len(data['tables'])} tables, {coverage['total']} fields, "
        f"{coverage['annotated']} annotated ({coverage['percent']}%)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
