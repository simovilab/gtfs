#!/usr/bin/env python3
"""Report how much of the GTFS Realtime spec has editor annotations yet.

Diffs the fields declared in serializers/realtime/realtime.yaml (ground truth)
against the keys in serializers/realtime/realtime.ui.yaml (editor annotations),
and validates the annotation file against realtime.ui.schema.json.

The same shape as the Schedule coverage script, with two checks it cannot have,
both of which cross a file boundary:

    `references`  names a GTFS *Schedule* field, so it is resolved against
                  schedule.yaml. This is the join that makes a realtime feed
                  consumable, and a typo here is invisible until a screen is
                  empty.
    `bounding_box` names a region defined in schedule.ui.yaml, since the
                  national box belongs to the territory and not to the feed.

Missing annotations are expected while the sweep is in progress and do not fail
the run. Annotations pointing at fields that do not exist, or an annotation file
that violates its schema, do fail: those are always mistakes.

Usage:
    uv run converters/realtime/ui_coverage.py
    uv run converters/realtime/ui_coverage.py --json
    uv run converters/realtime/ui_coverage.py --min-coverage 10
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

import rt_spec

ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = ROOT / "serializers" / "realtime" / "realtime.yaml"
UI_PATH = ROOT / "serializers" / "realtime" / "realtime.ui.yaml"
UI_SCHEMA_PATH = ROOT / "serializers" / "realtime" / "realtime.ui.schema.json"
SCHEDULE_PATH = ROOT / "serializers" / "schedule" / "schedule.yaml"
SCHEDULE_UI_PATH = ROOT / "serializers" / "schedule" / "schedule.ui.yaml"


def schedule_keys() -> set[str]:
    """Every '<file>.<field>' the static spec has, for checking `references`."""
    spec = yaml.safe_load(SCHEDULE_PATH.read_text(encoding="utf-8"))
    return {
        f"{entry['file'].rsplit('.', 1)[0]}.{field['name']}"
        for entry in spec.get("field_definitions", {}).get("files", [])
        for field in entry.get("fields") or []
    }


def validate_annotations(ui: dict) -> list[str]:
    """Validate the annotation file against its JSON Schema."""
    try:
        import jsonschema
    except ImportError:
        return ["jsonschema not installed; skipped schema validation"]

    schema = json.loads(UI_SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    return [
        f"{'/'.join(str(p) for p in err.path) or '<root>'}: {err.message}"
        for err in sorted(validator.iter_errors(ui), key=lambda e: list(e.path))
    ]


def cross_file_errors(annotations: dict, keys: set[str]) -> list[str]:
    """References into the other two files, resolved."""
    static = schedule_keys()
    regions = set(
        (yaml.safe_load(SCHEDULE_UI_PATH.read_text(encoding="utf-8")) or {})
        .get("regions", {})
    )

    errors = []
    for key, note in annotations.items():
        if (ref := note.get("references")) and ref not in static:
            errors.append(f"{key}: references '{ref}', which schedule.yaml does not have")

        validation = note.get("validation") or {}
        box = validation.get("bounding_box") or {}
        if (region := box.get("region")) and region not in regions:
            errors.append(f"{key}: bounding_box region '{region}' is not defined "
                          f"in schedule.ui.yaml")
        if (after := validation.get("after")) and after not in keys:
            errors.append(f"{key}: after '{after}' is not a field in realtime.yaml")
    return errors


def build_report(spec: dict, ui: dict) -> dict:
    idx = rt_spec.index(spec)
    annotations = ui.get("fields", {})
    annotated = set(annotations)

    per_message: dict[str, dict] = {}
    for message in rt_spec.messages(idx):
        names = [f["name"] for f in message.get("fields") or []]
        covered = [n for n in names if f"{message['name']}.{n}" in annotated]
        per_message[message["name"]] = {
            "total": len(names),
            "annotated": len(covered),
            "missing": [n for n in names if f"{message['name']}.{n}" not in annotated],
        }

    keys = {key for key, _ in rt_spec.inventory(idx)}
    total = sum(m["total"] for m in per_message.values())
    done = sum(m["annotated"] for m in per_message.values())

    # Coverage counted over fields a person actually edits, as well as over all
    # of them: the whole-spec figure can never reach 100% in any useful sense,
    # because most of these fields are produced by a machine.
    operator = [k for k, n in annotations.items() if n.get("origin") == "operator"]

    return {
        "total_fields": total,
        "annotated_fields": done,
        "coverage_percent": round(100 * done / total, 2) if total else 0.0,
        "messages_total": len(per_message),
        "messages_started": sum(1 for m in per_message.values() if m["annotated"]),
        "by_origin": {
            origin: sum(1 for n in annotations.values() if n.get("origin") == origin)
            for origin in ("operator", "system", "derived", "constant")
        },
        "operator_fields": len(operator),
        "orphan_annotations": sorted(annotated - keys),
        "schema_errors": validate_annotations(ui),
        "reference_errors": cross_file_errors(annotations, keys),
        "per_message": per_message,
    }


def print_report(report: dict) -> None:
    print("GTFS Realtime — editor annotation coverage")
    print("=" * 52)
    print(
        f"Fields annotated : {report['annotated_fields']}/{report['total_fields']}"
        f"  ({report['coverage_percent']}%)"
    )
    print(f"Messages started : {report['messages_started']}/{report['messages_total']}")
    origins = ", ".join(f"{k} {v}" for k, v in report["by_origin"].items() if v)
    print(f"By data origin   : {origins or 'none yet'}")
    print()

    started = {m: d for m, d in report["per_message"].items() if d["annotated"]}
    if started:
        print("Messages with annotations:")
        for message, data in started.items():
            pct = round(100 * data["annotated"] / data["total"], 1)
            mark = "complete" if not data["missing"] else f"{len(data['missing'])} pending"
            print(f"  {message:<24} {data['annotated']:>3}/{data['total']:<3} ({pct:>5}%)  {mark}")
            for name in data["missing"]:
                print(f"      not yet mapped: {name}")
        print()

    untouched = [m for m, d in report["per_message"].items() if not d["annotated"]]
    if untouched:
        print(f"Messages with no annotations yet ({len(untouched)}):")
        print("  " + ", ".join(untouched))
        print()

    sys.stdout.flush()  # keep the report above the diagnostics when piped
    for orphan in report["orphan_annotations"]:
        print(f"ERROR: annotation '{orphan}' has no matching field in realtime.yaml",
              file=sys.stderr)
    for err in report["reference_errors"]:
        print(f"ERROR: realtime.ui.yaml — {err}", file=sys.stderr)
    for err in report["schema_errors"]:
        print(f"ERROR: realtime.ui.yaml — {err}", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit the report as JSON")
    parser.add_argument(
        "--min-coverage",
        type=float,
        default=0.0,
        help="fail if coverage falls below this percentage (default: 0, never fails)",
    )
    args = parser.parse_args()

    for path in (SPEC_PATH, UI_PATH, UI_SCHEMA_PATH, SCHEDULE_PATH, SCHEDULE_UI_PATH):
        if not path.exists():
            print(f"ERROR: missing required file: {path}", file=sys.stderr)
            return 2

    spec = yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))
    ui = yaml.safe_load(UI_PATH.read_text(encoding="utf-8"))
    report = build_report(spec, ui)

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print_report(report)

    if (report["orphan_annotations"] or report["schema_errors"]
            or report["reference_errors"]):
        return 1
    if report["coverage_percent"] < args.min_coverage:
        print(
            f"ERROR: coverage {report['coverage_percent']}% is below the required "
            f"{args.min_coverage}%",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
