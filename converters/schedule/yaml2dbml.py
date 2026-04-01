"""Convert GTFS YAML specification to DBML using Jinja2 templates."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml
from jinja2 import Environment, FileSystemLoader


def map_type(field_type: str) -> str:
    """Map GTFS/YAML field types to DBML types.

    Falls back to string for unknown types to keep generation robust.
    """
    if not field_type:
        return "string"

    t = field_type.strip().lower()

    mapping = {
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
        "positive integer": "int",
        "positive float": "float",
        "latitude": "float",
        "longitude": "float",
        "currency amount": "float",
        # temporal
        "date": "date",
        "time": "time",
        "local time": "time",
        "datetime": "datetime",
        "timestamp": "datetime",
    }

    for key, dbml in mapping.items():
        if t == key or t.startswith(key):
            return dbml

    return "string"


def escape_note(value: str) -> str:
    return value.replace('"', '\\"')


def normalize_table_name(file_name: str) -> str:
    """Turn a GTFS file name into a DB table name.

    Examples:
      - "agency.txt" -> "agency"
      - "locations.geojson" -> "locations"
    """
    base = file_name
    for ext in (".txt", ".geojson"):
        if base.endswith(ext):
            base = base[: -len(ext)]
            break
    return base


def load_yaml(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_tables(
    data: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Transform YAML data to structures for DBML generation.

    Returns (enums, tables) where enums are DBML enum definitions and tables are table definitions.
    """
    fd = (data or {}).get("field_definitions", {})
    files = fd.get("files")

    if not files:
        return [], []

    # Build a map of file names to their dataset_files descriptions
    dataset_files = (data or {}).get("dataset_files", {})
    dataset_files_list = dataset_files.get("files", [])
    file_descriptions = {}
    for df in dataset_files_list:
        df_name = df.get("name")
        df_desc = df.get("description")
        if df_name and df_desc:
            file_descriptions[df_name] = df_desc

    # Support both list and mapping forms
    if isinstance(files, dict):
        iterable = (
            {"name": k, **(v or {})}
            for k, v in files.items()  # type: ignore[operator]
        )
    else:
        iterable = files

    tables: List[Dict[str, Any]] = []
    enums: List[Dict[str, Any]] = []
    seen_enum_names = set()

    for file_entry in iterable:
        file_name = file_entry.get("name") or file_entry.get("file") or "unknown"
        table_name = normalize_table_name(str(file_name))
        fields = file_entry.get("fields", [])

        # Get primary key definition from YAML (supports both string and array)
        primary_key_def = file_entry.get("primary_key")
        if isinstance(primary_key_def, str):
            primary_keys = [primary_key_def]
        elif isinstance(primary_key_def, list):
            primary_keys = primary_key_def
        else:
            primary_keys = []

        columns: List[Dict[str, Any]] = []
        for field in fields:
            fname = field.get("name", "field")
            ftype_raw = str(field.get("type", "text"))
            ftype_lower = ftype_raw.strip().lower()
            presence = (field.get("presence") or "").strip().lower()
            description = field.get("description") or ""
            notes = field.get("notes")
            options = field.get("options")

            # Check if this is an enum field with options
            if ftype_lower == "enum" and options:
                enum_name = f"{table_name}_{fname}_options"

                # Avoid duplicate enum definitions
                if enum_name not in seen_enum_names:
                    seen_enum_names.add(enum_name)

                    # Build enum values
                    enum_values = []
                    for option in options:
                        if isinstance(option, dict):
                            value = option.get("value", "")
                            description_opt = option.get("description", "")
                            if value:
                                enum_values.append(
                                    {
                                        "value": str(value),
                                        "description": str(description_opt),
                                    }
                                )

                    if enum_values:
                        enums.append({"name": enum_name, "options": enum_values})

                # Use the enum type instead of mapping to string
                dbml_type = f"gtfs.{enum_name}"
            else:
                dbml_type = map_type(ftype_raw)

            attrs: List[str] = []

            # Required -> not null. We avoid enforcing for conditionals to stay conservative.
            if presence.startswith("required"):
                attrs.append("not null")

            # Primary key: check if field is in the primary_keys list
            is_pk = fname in primary_keys
            if is_pk:
                attrs.append("pk")

            # Default values (quote strings)
            if "default" in field:
                default_val = field["default"]
                if isinstance(default_val, str):
                    attrs.append(f"default: '{default_val}'")
                else:
                    attrs.append(f"default: {default_val}")

            # Foreign key reference
            if "foreign_key" in field:
                fk = field["foreign_key"]
                attrs.append(f"ref: > gtfs.{fk}")

            # Compose note from description + notes
            note_parts = []
            if description:
                note_parts.append(str(description))
            if notes:
                note_parts.append(str(notes))
            if note_parts:
                attrs.append(f'note: "{escape_note(" ".join(note_parts))}"')

            columns.append(
                {
                    "name": fname,
                    "type": dbml_type,
                    "attrs": attrs,
                }
            )

        # Get table description from dataset_files mapping
        table_description = file_descriptions.get(file_name, "")
        tables.append(
            {"name": table_name, "columns": columns, "description": table_description}
        )

    return enums, tables


def generate_schedule_dbml(overwrite: bool = True) -> Path:
    """Generate schedule DBML from YAML data and Jinja2 template.

    Returns the path to the generated file.
    """
    base_dir = Path(__file__).parent.parent
    yaml_path = base_dir / "serializers" / "schedule.yaml"
    template_dir = base_dir / "converters" / "templates"
    output_dir = base_dir / "models"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "schedule.dbml"
    if not overwrite:
        output_path = output_dir / "schedule.generated.dbml"

    data = load_yaml(yaml_path)
    metadata = data.get("metadata", {})
    enums, tables = build_tables(data)

    env = Environment(
        loader=FileSystemLoader(template_dir), trim_blocks=True, lstrip_blocks=True
    )
    template = env.get_template("schedule.dbml.jinja")

    rendered = template.render(metadata=metadata, enums=enums, tables=tables)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(rendered)

    print(f"Generated {output_path}")
    return output_path


if __name__ == "__main__":
    # Allow optional flag to avoid overwriting the canonical schema
    no_overwrite = "--no-overwrite" in sys.argv
    generate_schedule_dbml(overwrite=not no_overwrite)
