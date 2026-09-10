#!/usr/bin/env python3
"""Resolve serializers/ui/composites.yaml against the GTFS references.

Every source in a composite names a real field in schedule.yaml or
realtime.yaml. Resolving those references is what makes the file checkable:
a typo, or a field withdrawn from a future spec revision, fails here rather
than silently blanking a screen.

Resolution also produces the two things the composites page shows:

    the forward view   composite -> props -> fields, with each field's editor
                       component from schedule.ui.yaml
    the reverse index  field -> the composites that display it

Run directly to validate and print a report; exits non-zero on errors, so it
works as a CI step.

Usage:
    uv run converters/ui/composites.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parents[2]
COMPOSITES_PATH = ROOT / "serializers" / "ui" / "composites.yaml"
COMPOSITES_SCHEMA = ROOT / "serializers" / "ui" / "composites.schema.json"
SCHEDULE_PATH = ROOT / "serializers" / "schedule" / "schedule.yaml"
REALTIME_PATH = ROOT / "serializers" / "realtime" / "realtime.yaml"
UI_PATH = ROOT / "serializers" / "schedule" / "schedule.ui.yaml"

LANGS = ("es", "en", "pt")


# --------------------------------------------------------------- indexing


def schedule_index(spec: dict) -> dict[str, dict]:
    """'routes.route_color' -> the field's entry in schedule.yaml."""
    index = {}
    for entry in spec.get("field_definitions", {}).get("files", []):
        table = entry["file"].rsplit(".", 1)[0]
        for field in entry.get("fields") or []:
            index[f"{table}.{field['name']}"] = {
                "table": table,
                "file": entry["file"],
                "name": field["name"],
                "type": field.get("type", ""),
                "presence": field.get("presence", ""),
                "description": field.get("description", ""),
            }
    return index


def realtime_elements(spec: dict) -> dict[str, dict]:
    """'TripUpdate' -> the message's entry in realtime.yaml."""
    return {e["name"]: e for e in spec.get("elements", [])}


def resolve_realtime(path: str, elements: dict[str, dict]) -> dict | None:
    """Walk 'TripUpdate.stop_time_update.departure.time' through the messages.

    Walking rather than matching a flat name is what keeps arrival.time and
    departure.time distinguishable: both end at StopTimeEvent.time, and a flat
    key could not tell a screen which one it meant.
    """
    head, *rest = path.split(".")
    element = elements.get(head)
    if element is None or element.get("data_type") != "message" or not rest:
        return None

    field = None
    for step, segment in enumerate(rest):
        if element is None or element.get("data_type") != "message":
            return None
        field = next((f for f in element.get("fields") or [] if f["name"] == segment), None)
        if field is None:
            return None
        nested = (field.get("type") or {}).get("element") or {}
        last = step == len(rest) - 1
        element = elements.get(nested.get("name")) if nested else None
        if not last and element is None:
            return None  # more path left, but this field is a scalar

    kind = (field.get("type") or {})
    return {
        "message": head,
        "name": field["name"],
        "type": (kind.get("element") or kind.get("format") or {}).get("name", ""),
        "presence": field.get("presence", ""),
        "cardinality": field.get("cardinality", ""),
        "description": field.get("description", ""),
    }


# -------------------------------------------------------------- resolving


def resolve(ref: str, ctx: dict) -> dict:
    """One source reference, resolved to everything the page needs to show it.

    `exists` false is an error, not a rendering nuance: it means the file
    points at a field the specification does not have.
    """
    feed, _, path = ref.partition(":")
    out = {"ref": ref, "feed": feed, "path": path, "exists": False,
           "type": "", "presence": "", "description": "",
           "component": None, "annotated": False, "label": {}}

    if feed == "schedule":
        field = ctx["schedule"].get(path)
        if field:
            note = ctx["annotations"].get(path) or {}
            out.update(
                exists=True, type=field["type"], presence=field["presence"],
                description=field["description"], table=field["table"],
                name=field["name"], component=note.get("component"),
                annotated=bool(note),
                label={l: (note.get("i18n", {}).get(l) or {}).get("label", "") for l in LANGS},
            )
    elif feed == "realtime":
        field = resolve_realtime(path, ctx["realtime"])
        if field:
            out.update(
                exists=True, type=field["type"], presence=field["presence"],
                description=field["description"], table=field["message"],
                name=field["name"], cardinality=field["cardinality"],
            )
    return out


def build(doc: dict, ctx: dict) -> dict:
    """The whole file, resolved, plus the reverse index and the counters."""
    composites, reverse = [], {}

    for name, spec in doc.get("composites", {}).items():
        params = [
            {**param, "resolved": resolve(param["source"], ctx),
             "required": param.get("required", True)}
            for param in spec.get("params") or []
        ]
        props = []
        for prop in spec.get("props") or []:
            sources = [resolve(s, ctx) for s in prop.get("sources") or []]
            props.append({**prop, "required": prop.get("required", False), "sources": sources})
            for source in sources:
                reverse.setdefault(source["ref"], []).append(
                    {"composite": name, "prop": prop["name"]})

        for param in params:
            reverse.setdefault(param["resolved"]["ref"], []).append(
                {"composite": name, "prop": param["name"], "param": True})

        composites.append({
            "name": name,
            "entity": spec["entity"],
            "cardinality": spec["cardinality"],
            "key": resolve(spec["key"], ctx) if spec.get("key") else None,
            "i18n": spec.get("i18n", {}),
            "params": params,
            "props": props,
            "notes": spec.get("notes") or [],
            "usedBy": [v for v, view in doc.get("views", {}).items()
                       if name in view.get("blocks", [])],
            "nestedIn": sorted({
                other for other, ospec in doc.get("composites", {}).items()
                if any(p.get("composite") == name for p in ospec.get("props") or [])
            }),
        })

    views = [{"name": name, **view} for name, view in doc.get("views", {}).items()]

    refs = list(reverse)
    schedule_refs = [r for r in refs if r.startswith("schedule:")]
    annotated = sum(1 for r in schedule_refs
                    if (ctx["annotations"].get(r.split(":", 1)[1]) is not None))

    return {
        "composites": composites,
        "views": views,
        "reverse": reverse,
        "langs": list(LANGS),
        "stats": {
            "composites": len(composites),
            "views": len(views),
            "refs": len(refs),
            "schedule": len(schedule_refs),
            "realtime": len(refs) - len(schedule_refs),
            "annotated": annotated,
            "percent": round(100 * annotated / len(schedule_refs), 1) if schedule_refs else 0.0,
        },
    }


# --------------------------------------------------------------- checking


def check(doc: dict, model: dict) -> tuple[list[str], list[str]]:
    """Semantic checks the JSON Schema cannot express. (errors, warnings)"""
    errors, warnings = [], []
    names = set(doc.get("composites", {}))

    for composite in model["composites"]:
        where = composite["name"]

        seen = set()
        for prop in composite["props"]:
            if prop["name"] in seen:
                errors.append(f"{where}: duplicate prop '{prop['name']}'")
            seen.add(prop["name"])

            if prop.get("composite") and prop["composite"] not in names:
                errors.append(f"{where}.{prop['name']}: unknown composite "
                              f"'{prop['composite']}'")

            for source in prop["sources"]:
                if not source["exists"]:
                    errors.append(f"{where}.{prop['name']}: '{source['ref']}' "
                                  f"is not a field in the reference")

            live = [s for s in prop["sources"] if s["feed"] == "realtime"]
            if prop.get("freshness") and not live:
                warnings.append(f"{where}.{prop['name']}: freshness set but no "
                                f"realtime source, so it can never expire")
            if prop["required"] and prop["sources"] and len(live) == len(prop["sources"]):
                warnings.append(f"{where}.{prop['name']}: required but every source "
                                f"is realtime, so it cannot render from a static feed")

        for param in composite["params"]:
            if not param["resolved"]["exists"]:
                errors.append(f"{where}.{param['name']}: '{param['source']}' "
                              f"is not a field in the reference")

        if composite["key"] and not composite["key"]["exists"]:
            errors.append(f"{where}: key '{composite['key']['ref']}' "
                          f"is not a field in the reference")

        if not composite["usedBy"] and not composite["nestedIn"]:
            warnings.append(f"{where}: no view uses it and nothing nests it")

    for view in model["views"]:
        for block in view["blocks"]:
            if block not in names:
                errors.append(f"view {view['name']}: unknown composite '{block}'")

    errors.extend(cycles(doc.get("composites", {})))
    return errors, warnings


def cycles(composites: dict) -> list[str]:
    """Nesting must be a tree; a cycle would render forever."""
    found, state = [], {}

    def walk(name: str, trail: list[str]) -> None:
        if state.get(name) == "done":
            return
        if state.get(name) == "open":
            found.append("composite nesting cycle: " + " -> ".join(trail + [name]))
            return
        state[name] = "open"
        for prop in composites.get(name, {}).get("props") or []:
            if prop.get("composite"):
                walk(prop["composite"], trail + [name])
        state[name] = "done"

    for name in composites:
        walk(name, [])
    return found


# ------------------------------------------------------------------ entry


def load() -> dict:
    """Parse, schema-validate and resolve; raises on a malformed file."""
    doc = yaml.safe_load(COMPOSITES_PATH.read_text(encoding="utf-8"))
    jsonschema.validate(doc, json.loads(COMPOSITES_SCHEMA.read_text(encoding="utf-8")))

    ui = yaml.safe_load(UI_PATH.read_text(encoding="utf-8")) or {}
    ctx = {
        "schedule": schedule_index(yaml.safe_load(SCHEDULE_PATH.read_text(encoding="utf-8"))),
        "realtime": realtime_elements(yaml.safe_load(REALTIME_PATH.read_text(encoding="utf-8"))),
        "annotations": ui.get("fields", {}),
    }
    return build(doc, ctx) | {"document": doc}


def main() -> int:
    for path in (COMPOSITES_PATH, COMPOSITES_SCHEMA, SCHEDULE_PATH, REALTIME_PATH, UI_PATH):
        if not path.exists():
            print(f"ERROR: missing required file: {path}", file=sys.stderr)
            return 2

    try:
        model = load()
    except jsonschema.ValidationError as e:
        location = ".".join(str(p) for p in e.path) or "(root)"
        print(f"ERROR: {COMPOSITES_PATH.name} does not match its schema\n"
              f"  at {location}: {e.message}", file=sys.stderr)
        return 1

    errors, warnings = check(model["document"], model)
    stats = model["stats"]

    print(f"{stats['composites']} composites across {stats['views']} views")
    print(f"{stats['refs']} field references — {stats['schedule']} schedule, "
          f"{stats['realtime']} realtime")
    print(f"{stats['annotated']}/{stats['schedule']} displayed schedule fields "
          f"have an editor annotation ({stats['percent']}%)")

    gaps = sorted({
        source["ref"] for composite in model["composites"] for prop in composite["props"]
        for source in prop["sources"] if source["feed"] == "schedule" and not source["annotated"]
    })
    if gaps:
        print(f"\nDisplayed but not annotated ({len(gaps)}):")
        for ref in gaps:
            print(f"  {ref}")

    sys.stdout.flush()  # keep the report above the diagnostics when piped
    for warning in warnings:
        print(f"\nWARNING: {warning}", file=sys.stderr)
    for error in errors:
        print(f"\nERROR: {error}", file=sys.stderr)

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
