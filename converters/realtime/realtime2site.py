#!/usr/bin/env python3
"""Build the GTFS Realtime field explorer.

Merges serializers/realtime/realtime.yaml (GTFS Realtime ground truth) with
serializers/realtime/realtime.ui.yaml (editor annotations) into a single
self-contained HTML page written to web/dist/realtime.html.

The page is the one converters/site/explorer.py builds for the Schedule side;
what is feed-specific is here, and it is mostly the difference between a set of
CSV files and a graph of protobuf messages:

    a "table" is a message, and its fields are the message's fields
    a field's options come from whichever enum it selects, which has to be
      resolved by position because enum names repeat (see rt_spec)
    a message-typed field links to the message it opens, the way a Schedule
      foreign key links to the file it points into
    regions come from schedule.ui.yaml, because the national bounding box is a
      property of the territory and not of the feed

Usage:
    uv run converters/realtime/realtime2site.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

import rt_spec

ROOT = Path(__file__).resolve().parents[2]

# The shared explorer and the composites model live in sibling directories.
# They are imported by path rather than as packages because these converters
# are run as scripts.
sys.path.insert(0, str(ROOT / "converters" / "site"))
sys.path.insert(0, str(ROOT / "converters" / "ui"))
import composites as composites_model  # noqa: E402
import explorer  # noqa: E402
import ui_form_model  # noqa: E402

SPEC_PATH = ROOT / "serializers" / "realtime" / "realtime.yaml"
UI_PATH = ROOT / "serializers" / "realtime" / "realtime.ui.yaml"
SCHEMA_PATH = ROOT / "serializers" / "realtime" / "realtime.ui.schema.json"
SCHEDULE_UI_PATH = ROOT / "serializers" / "schedule" / "schedule.ui.yaml"
ASSET_DIR = ROOT / "converters" / "realtime" / "templates" / "site"
OUTPUT_PATH = ROOT / "web" / "dist" / "realtime.html"

LANGS = explorer.LANGS

# What the page says about itself: which files back it, where its edits go.
PAGE = {
    "feed": "realtime",
    "feedLabel": "GTFS Realtime",
    "specFile": "serializers/realtime/realtime.yaml",
    "file": "serializers/realtime/realtime.ui.yaml",
    "fileName": "realtime.ui.yaml",
    "patchName": "realtime.ui.patch.yaml",
    "endpoint": "api/realtime-annotations",
    "draftKey": "gtfs.realtime.ui.draft.v1",
}

ANNOTATION_KEYS = ("origin", "component", "group", "references")


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
        "validation": note.get("validation") or {},
        "i18n": note.get("i18n") or {},
    }
    for key in ANNOTATION_KEYS:
        if note.get(key):
            shaped[key] = note[key]
    return shaped


def display_usage() -> dict[str, list[dict]]:
    """'StopTimeEvent.time' -> the composites that display it.

    composites.yaml addresses realtime fields by path, since a screen has to
    say whether it means the arrival or the departure. Here the question is
    about the field itself, so the paths are folded onto the definition they
    reach and a field shows every screen that reads it, by either route.

    A missing or broken composites file must not stop the explorer from
    building: composites.py is the authority on whether that file is valid,
    and it fails on its own in CI.
    """
    try:
        model = composites_model.load()
    except Exception as e:  # noqa: BLE001 - reported, not swallowed
        print(f"WARNING: composites not resolved ({e}); "
              f"fields will show no usage", file=sys.stderr)
        return {}

    idx = rt_spec.index(yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8")))
    usage: dict[str, list[dict]] = {}
    for ref, uses in model["reverse"].items():
        feed, _, path = ref.partition(":")
        if feed != "realtime":
            continue
        if resolved := rt_spec.resolve_path(path, idx):
            usage.setdefault(resolved["key"], []).extend(
                {**use, "via": path} for use in uses)
    return usage


def build_data(spec: dict, ui: dict, regions: dict) -> dict:
    idx = rt_spec.index(spec)
    annotations = ui.get("fields", {})
    usage = display_usage()
    tables = []

    for message in rt_spec.messages(idx):
        fields = []
        for field in message.get("fields") or []:
            key = f"{message['name']}.{field['name']}"
            type_name, data_type = rt_spec.field_type(field)
            enum = rt_spec.enum_options(idx, message, field)

            fields.append(
                {
                    "name": field["name"],
                    "key": key,
                    "type": type_name,
                    "presence": field.get("presence", ""),
                    # The spec-column rows, named by translation key. Protobuf
                    # cardinality is the one a CSV field cannot have: "Many"
                    # is a repeated field, and a screen showing it needs a list.
                    "facts": [
                        {"k": "type", "v": type_name},
                        {"k": "presence", "v": field.get("presence", "")},
                        {"k": "cardinality", "v": field.get("cardinality", "")},
                    ],
                    "description": field.get("description", ""),
                    # A message-typed field opens another message, the way a
                    # Schedule foreign key points into another file.
                    "opens": type_name if data_type == "message" else None,
                    "conditions": [],
                    "notes": [],
                    # The enum's own name and description caption its values,
                    # which is what distinguishes the two ScheduleRelationship
                    # enums on screen as well as in the resolver.
                    "options": [{
                        "category": " — ".join(
                            x for x in (enum["name"], enum["description"]) if x),
                        "values": enum["values"],
                    }] if enum else [],
                    "annotation": annotation_of(annotations.get(key)),
                    "usage": usage.get(key, []),
                }
            )

        annotated = sum(1 for f in fields if f["annotation"])
        tables.append(
            {
                "name": message["name"],
                "title": message["name"],
                "presence": "",
                "description": message.get("description", ""),
                "fields": fields,
                "total": len(fields),
                "annotated": annotated,
            }
        )

    total = sum(t["total"] for t in tables)
    done = sum(t["annotated"] for t in tables)

    return {
        "metadata": spec.get("metadata", {}),
        # Read from schedule.ui.yaml: one national box, not one per feed.
        "regions": regions,
        "tables": tables,
        "coverage": {
            "total": total,
            "annotated": done,
            "percent": round(100 * done / total, 1) if total else 0.0,
        },
        "langs": list(LANGS),
    }


def main() -> int:
    for path in (SPEC_PATH, UI_PATH, SCHEMA_PATH, SCHEDULE_UI_PATH):
        if not path.exists():
            print(f"ERROR: missing required file: {path}", file=sys.stderr)
            return 2

    spec = yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))
    ui = yaml.safe_load(UI_PATH.read_text(encoding="utf-8"))
    regions = (yaml.safe_load(SCHEDULE_UI_PATH.read_text(encoding="utf-8")) or {}).get(
        "regions", {})
    data = build_data(spec, ui, regions)

    explorer.render(
        OUTPUT_PATH,
        page=PAGE,
        data=data,
        form=ui_form_model.load(SCHEMA_PATH),
        suggest_js=explorer.asset("suggest.js", ASSET_DIR),
        title="GTFS Realtime — Componentes de edición y validación",
        heading="GTFS Realtime",
        current="realtime",
    )

    coverage = data["coverage"]
    print(f"Wrote {OUTPUT_PATH}")
    print(
        f"Embedded {len(data['tables'])} messages, {coverage['total']} fields, "
        f"{coverage['annotated']} annotated ({coverage['percent']}%)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
