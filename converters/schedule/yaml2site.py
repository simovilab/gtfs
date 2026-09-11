#!/usr/bin/env python3
"""Build the GTFS Schedule field explorer.

Merges serializers/schedule/schedule.yaml (GTFS ground truth) with
serializers/schedule/schedule.ui.yaml (editor annotations) into a single
self-contained HTML page written to web/dist/index.html.

The page itself is built by converters/site/explorer.py, which the Realtime
explorer uses too. What is left here is the one feed-specific job: turning
schedule.yaml's files and fields into the payload that page draws.

Data is embedded at build time rather than fetched at page load so the result
is a fully static page with no runtime requests, which is what GitHub Pages
serves best.

Usage:
    uv run converters/schedule/yaml2site.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]

# The shared explorer and the composites model live in sibling directories.
# They are imported by path rather than as packages because these converters
# are run as scripts.
sys.path.insert(0, str(ROOT / "converters" / "site"))
sys.path.insert(0, str(ROOT / "converters" / "ui"))
import composites as composites_model  # noqa: E402
import explorer  # noqa: E402
import ui_form_model  # noqa: E402

SPEC_PATH = ROOT / "serializers" / "schedule" / "schedule.yaml"
UI_PATH = ROOT / "serializers" / "schedule" / "schedule.ui.yaml"
SCHEMA_PATH = ROOT / "serializers" / "schedule" / "schedule.ui.schema.json"
ASSET_DIR = ROOT / "converters" / "schedule" / "templates" / "site"
OUTPUT_PATH = ROOT / "web" / "dist" / "index.html"

LANGS = explorer.LANGS

# What the page says about itself: which files back it, where its edits go.
PAGE = {
    "feed": "schedule",
    "feedLabel": "GTFS Schedule",
    "specFile": "serializers/schedule/schedule.yaml",
    "file": "serializers/schedule/schedule.ui.yaml",
    "fileName": "schedule.ui.yaml",
    "patchName": "schedule.ui.patch.yaml",
    "endpoint": "api/annotations",
    "draftKey": "gtfs.schedule.ui.draft.v1",
}


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
                    # The spec-column rows, named by translation key. Schedule
                    # fields have a type and a presence; Realtime adds more.
                    "facts": [
                        {"k": "type", "v": field.get("type", "")},
                        {"k": "presence", "v": field.get("presence", "")},
                    ],
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
                "title": entry["file"],
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


def main() -> int:
    for path in (SPEC_PATH, UI_PATH, SCHEMA_PATH):
        if not path.exists():
            print(f"ERROR: missing required file: {path}", file=sys.stderr)
            return 2

    spec = yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))
    ui = yaml.safe_load(UI_PATH.read_text(encoding="utf-8"))
    data = build_data(spec, ui)

    explorer.render(
        OUTPUT_PATH,
        page=PAGE,
        data=data,
        form=ui_form_model.load(SCHEMA_PATH),
        suggest_js=explorer.asset("suggest.js", ASSET_DIR),
        title="GTFS Schedule — Componentes de edición y validación",
        heading="GTFS Schedule",
        current="schedule",
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
