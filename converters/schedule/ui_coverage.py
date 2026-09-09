#!/usr/bin/env python3
"""Report how much of the GTFS Schedule spec has editor annotations yet.

Diffs the fields declared in serializers/schedule/schedule.yaml (ground truth)
against the keys in serializers/schedule/schedule.ui.yaml (editor annotations),
and validates the annotation file against schedule.ui.schema.json.

Note: schedule.schema.json describes the *structure* of the YAML document, not
the GTFS field inventory, so the field list is read from schedule.yaml itself.

Missing annotations are expected while the sweep is in progress and do not fail
the run. Annotations pointing at fields that do not exist, or an annotation file
that violates its schema, do fail: those are always mistakes.

Usage:
    uv run converters/schedule/ui_coverage.py
    uv run converters/schedule/ui_coverage.py --json
    uv run converters/schedule/ui_coverage.py --min-coverage 10
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = ROOT / "serializers" / "schedule" / "schedule.yaml"
UI_PATH = ROOT / "serializers" / "schedule" / "schedule.ui.yaml"
UI_SCHEMA_PATH = ROOT / "serializers" / "schedule" / "schedule.ui.schema.json"


def table_name(filename: str) -> str:
    """'stops.txt' -> 'stops'; 'locations.geojson' -> 'locations'."""
    return filename.rsplit(".", 1)[0]


def spec_fields(spec: dict) -> dict[str, list[str]]:
    """Map each GTFS table to its field names, in spec order."""
    tables: dict[str, list[str]] = {}
    for entry in spec.get("field_definitions", {}).get("files", []):
        table = table_name(entry["file"])
        tables[table] = [f["name"] for f in entry.get("fields", []) or []]
    return tables


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


def build_report(spec: dict, ui: dict) -> dict:
    tables = spec_fields(spec)
    annotated = set(ui.get("fields", {}))

    all_keys = {f"{t}.{f}" for t, fields in tables.items() for f in fields}
    orphans = sorted(annotated - all_keys)

    per_table = {}
    for table, fields in sorted(tables.items()):
        covered = [f for f in fields if f"{table}.{f}" in annotated]
        per_table[table] = {
            "total": len(fields),
            "annotated": len(covered),
            "missing": [f for f in fields if f"{table}.{f}" not in annotated],
        }

    total = sum(t["total"] for t in per_table.values())
    done = sum(t["annotated"] for t in per_table.values())

    return {
        "total_fields": total,
        "annotated_fields": done,
        "coverage_percent": round(100 * done / total, 2) if total else 0.0,
        "tables_total": len(per_table),
        "tables_started": sum(1 for t in per_table.values() if t["annotated"]),
        "orphan_annotations": orphans,
        "schema_errors": validate_annotations(ui),
        "per_table": per_table,
    }


def print_report(report: dict) -> None:
    print("GTFS Schedule — editor annotation coverage")
    print("=" * 52)
    print(
        f"Fields annotated : {report['annotated_fields']}/{report['total_fields']}"
        f"  ({report['coverage_percent']}%)"
    )
    print(f"Tables started   : {report['tables_started']}/{report['tables_total']}")
    print()

    started = {t: d for t, d in report["per_table"].items() if d["annotated"]}
    if started:
        print("Tables with annotations:")
        for table, data in started.items():
            pct = round(100 * data["annotated"] / data["total"], 1)
            mark = "complete" if not data["missing"] else f"{len(data['missing'])} pending"
            print(f"  {table:<24} {data['annotated']:>3}/{data['total']:<3} ({pct:>5}%)  {mark}")
            for name in data["missing"]:
                print(f"      not yet mapped: {name}")
        print()

    untouched = [t for t, d in report["per_table"].items() if not d["annotated"]]
    if untouched:
        print(f"Tables with no annotations yet ({len(untouched)}):")
        print("  " + ", ".join(untouched))
        print()

    for orphan in report["orphan_annotations"]:
        print(f"ERROR: annotation '{orphan}' has no matching field in schedule.yaml")
    for err in report["schema_errors"]:
        print(f"ERROR: schedule.ui.yaml — {err}")


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

    for path in (SPEC_PATH, UI_PATH, UI_SCHEMA_PATH):
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

    if report["orphan_annotations"] or report["schema_errors"]:
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
