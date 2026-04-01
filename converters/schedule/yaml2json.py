#!/usr/bin/env python3
"""
Convert schedule.yaml to schedule.json with pretty formatting.
- Input: serializers/schedule.yaml
- Output: serializers/schedule.json (overwrites)
Requirements: PyYAML
"""

from __future__ import annotations
import json
import sys
from pathlib import Path

try:
    import yaml  # PyYAML
except Exception:
    print("ERROR: PyYAML is required. Install with: uv add pyyaml", file=sys.stderr)
    sys.exit(1)

ROOT = Path(__file__).resolve().parent.parent
YAML_PATH = ROOT / "serializers/schedule.yaml"
JSON_PATH = ROOT / "serializers/schedule.json"


def main() -> int:
    if not YAML_PATH.exists():
        print(f"ERROR: Input YAML not found: {YAML_PATH}", file=sys.stderr)
        return 2

    try:
        with YAML_PATH.open("r", encoding="utf-8") as f:
            # Safe loader prevents arbitrary code execution
            data = yaml.safe_load(f)
    except yaml.YAMLError as ye:
        print(f"ERROR: Failed to parse YAML: {ye}", file=sys.stderr)
        return 3
    except Exception as e:
        print(f"ERROR: Could not read YAML: {e}", file=sys.stderr)
        return 4

    try:
        with JSON_PATH.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
    except Exception as e:
        print(f"ERROR: Could not write JSON: {e}", file=sys.stderr)
        return 5

    print(f"Wrote {JSON_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
