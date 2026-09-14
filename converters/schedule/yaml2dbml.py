"""Convert GTFS YAML specification to DBML using Jinja2 templates.

The DBML is a diagram of the spec: it keeps every relationship the spec
describes, including ones a database could not enforce as a foreign key
(alternative targets, non-unique targets). Those carry a note saying so.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Set, Tuple

import yaml
from jinja2 import Environment, FileSystemLoader

BASE_DIR = Path(__file__).resolve().parents[2]
TEMPLATE_DIR = BASE_DIR / "converters" / "schedule" / "templates"

# GTFS field type (lowercase) -> DBML column type. Matched exactly, else by the
# longest prefix (so "text or url or email" maps via "text").
TYPE_MAP: Dict[str, str] = {
    # textual
    "text": "string",
    "string": "string",
    "url": "string",
    "email": "string",
    "phone number": "string",
    "language code": "string",
    "currency code": "string",
    "timezone": "string",
    "color": "string",
    "id": "string",
    "unique id": "string",
    "foreign id": "string",
    "enum": "string",
    # numeric
    "integer": "int",
    "float": "float",
    "non-negative integer": "int",
    "non-negative float": "float",
    "non-zero integer": "int",
    "non-zero float": "float",
    "non-null integer": "int",
    "positive integer": "int",
    "positive float": "float",
    "latitude": "float",
    "longitude": "float",
    "currency amount": "float",
    # temporal. GTFS "Time" may exceed 24:00:00 for service past midnight, so it
    # is a duration from the start of the service day, not a time of day.
    "date": "date",
    "time": "interval",
    "local time": "time",
    "datetime": "datetime",
    "timestamp": "datetime",
}


def _type_key(field_type: str) -> str | None:
    t = (field_type or "").strip().lower()
    if t in TYPE_MAP:
        return t
    prefixes = [key for key in TYPE_MAP if t.startswith(key)]
    return max(prefixes, key=len) if prefixes else None


def is_known_type(field_type: str) -> bool:
    return _type_key(field_type) is not None


def map_type(field_type: str) -> str:
    """Map a GTFS/YAML field type to a DBML type; unknown types become string."""
    key = _type_key(field_type)
    return TYPE_MAP[key] if key else "string"


def _flatten(value: Any) -> str:
    """Collapse lists (YAML `notes`), HTML breaks and newlines into one line of text."""
    if isinstance(value, list):
        value = " ".join(str(v) for v in value if v)
    value = re.sub(r"<\s*(br|hr)\s*/?\s*>", " ", str(value), flags=re.I)
    return " ".join(value.split())


def escape_note(value: Any) -> str:
    """Escape text for a double-quoted DBML string."""
    return _flatten(value).replace("\\", "\\\\").replace('"', '\\"')


def escape_single(value: Any) -> str:
    """Escape text for a single-quoted DBML string."""
    return _flatten(value).replace("\\", "\\\\").replace("'", "\\'")


def flatten_options(options: List[Any] | None) -> List[Dict[str, str]]:
    """Normalize enum options to unique {value, description} pairs.

    Categorized options ({category, values: [...]}) repeat the same values per
    category; DBML enum values must be unique, so descriptions are merged.
    """
    merged: Dict[str, List[str]] = {}
    for option in options or []:
        if not isinstance(option, dict):
            continue
        if "values" in option:
            prefix = f"{option['category']}: " if option.get("category") else ""
            pairs = [(v.get("value"), prefix + str(v.get("description", ""))) for v in option["values"]]
        else:
            pairs = [(option.get("value"), str(option.get("description", "")))]
        for value, desc in pairs:
            if value is None or value == "":
                continue
            merged.setdefault(str(value), []).append(desc)
    return [
        {"value": escape_note(v), "description": escape_single(" ".join(d))}
        for v, d in merged.items()
    ]


def flatten_fields(fields: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Flatten nested (GeoJSON) field trees into table columns.

    Containers (features, properties) are descended into, `type` discriminators
    are dropped, and `geometry` becomes one serialized column.
    """
    if not any(f.get("children") for f in fields):
        return fields
    flat: List[Dict[str, Any]] = []
    for f in fields:
        if f.get("name") == "geometry":
            flat.append({**{k: v for k, v in f.items() if k != "children"}, "type": "Text"})
        elif f.get("children"):
            flat.extend(flatten_fields(f["children"]))
        elif f.get("name") != "type":
            flat.append(f)
    return flat


def fk_targets(fk: Any) -> List[str]:
    if not fk:
        return []
    return [str(t).replace(".txt", "").replace(".geojson", "") for t in (fk if isinstance(fk, list) else [fk])]


def normalize_table_name(file_name: str) -> str:
    """Turn a GTFS file name into a DB table name ("agency.txt" -> "agency")."""
    for ext in (".txt", ".geojson"):
        if file_name.endswith(ext):
            return file_name[: -len(ext)]
    return file_name


def entry_name(entry: Dict[str, Any]) -> str:
    return str(entry.get("name") or entry.get("file") or "unknown")


def primary_key_columns(entry: Dict[str, Any], fields: List[Dict[str, Any]]) -> List[str]:
    """Primary key as a column list; YAML allows a string, a list, "*" (all fields) or "none"."""
    pk = entry.get("primary_key")
    if pk == "*":
        return [str(f.get("name")) for f in fields]
    if isinstance(pk, str) and pk.lower() != "none":
        return [pk]
    if isinstance(pk, list):
        return list(pk)
    return []


def unique_key_columns(entries: Iterable[Dict[str, Any]]) -> Set[str]:
    """"table.column" for every table whose primary key is a single column."""
    keys = set()
    for entry in entries:
        cols = primary_key_columns(entry, flatten_fields(entry.get("fields", [])))
        if len(cols) == 1:
            keys.add(f"{normalize_table_name(entry_name(entry))}.{cols[0]}")
    return keys


def ref_caveat(targets: List[str], unique_cols: Set[str]) -> str:
    """Explain a reference the diagram draws but a database could not enforce."""
    if len(targets) > 1:
        return f"References one of {', '.join(targets)} (alternative targets, not a single foreign key)."
    if targets and targets[0] not in unique_cols:
        return f"References {targets[0]}, which is not a unique key (logical reference, not a foreign key)."
    return ""


def load_yaml(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_column(
    field: Dict[str, Any],
    table_name: str,
    primary_keys: List[str],
    unique_cols: Set[str],
    enums: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Build one DBML column, registering its enum in `enums` if it has one."""
    fname = field.get("name", "field")
    ftype_raw = str(field.get("type", "text"))
    presence = (field.get("presence") or "").strip().lower()

    dbml_type = map_type(ftype_raw)
    enum_values = flatten_options(field.get("options")) if ftype_raw.strip().lower() == "enum" else []
    if enum_values:
        enum_name = f"{table_name}_{fname}_options"
        if all(e["name"] != enum_name for e in enums):
            enums.append({"name": enum_name, "options": enum_values})
        dbml_type = f"gtfs.{enum_name}"

    attrs: List[str] = []
    # Required -> not null; conditionals are not enforced.
    if presence.startswith("required"):
        attrs.append("not null")
    # Single-column PK inline; composite PKs go in the indexes block
    if len(primary_keys) == 1 and fname in primary_keys:
        attrs.append("pk")
    if "default" in field:
        default_val = field["default"]
        attrs.append(f"default: '{escape_single(default_val)}'" if isinstance(default_val, str) else f"default: {default_val}")

    targets = fk_targets(field.get("foreign_key"))
    attrs.extend(f"ref: > gtfs.{target}" for target in targets)

    note = escape_note([field.get("description") or "", _flatten(field.get("notes") or ""), ref_caveat(targets, unique_cols)])
    if note:
        attrs.append(f'note: "{note}"')

    return {"name": fname, "type": dbml_type, "attrs": attrs}


def build_tables(
    data: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Transform YAML data to (enums, tables) structures for the DBML template."""
    data = data or {}
    files = data.get("field_definitions", {}).get("files") or []
    entries = [{"name": k, **(v or {})} for k, v in files.items()] if isinstance(files, dict) else list(files)
    descriptions = {
        df["name"]: df["description"]
        for df in data.get("dataset_files", {}).get("files", [])
        if df.get("name") and df.get("description")
    }
    unique_cols = unique_key_columns(entries)

    enums: List[Dict[str, Any]] = []
    tables: List[Dict[str, Any]] = []
    for entry in entries:
        file_name = entry_name(entry)
        table_name = normalize_table_name(file_name)
        fields = flatten_fields(entry.get("fields", []))
        primary_keys = primary_key_columns(entry, fields)
        tables.append(
            {
                "name": table_name,
                "columns": [build_column(f, table_name, primary_keys, unique_cols, enums) for f in fields],
                "description": escape_single(descriptions.get(file_name, "")),
                "composite_pk": primary_keys if len(primary_keys) > 1 else [],
            }
        )
    return enums, tables


def render_dbml(data: Dict[str, Any]) -> str:
    enums, tables = build_tables(data)
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR), trim_blocks=True, lstrip_blocks=True)
    template = env.get_template("schedule.dbml.jinja")
    return template.render(metadata=data.get("metadata", {}), enums=enums, tables=tables)


def generate_schedule_dbml(overwrite: bool = True) -> Path:
    """Generate schedule DBML from YAML data and Jinja2 template.

    Returns the path to the generated file.
    """
    yaml_path = BASE_DIR / "serializers" / "schedule" / "schedule.yaml"
    output_dir = BASE_DIR / "models" / "schedule" / "dbml"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / ("schedule.dbml" if overwrite else "schedule.generated.dbml")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(render_dbml(load_yaml(yaml_path)))

    print(f"Generated {output_path}")
    return output_path


if __name__ == "__main__":
    # Allow optional flag to avoid overwriting the canonical schema
    no_overwrite = "--no-overwrite" in sys.argv
    generate_schedule_dbml(overwrite=not no_overwrite)
