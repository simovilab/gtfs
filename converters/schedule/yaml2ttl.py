"""Builds the GTFS Schedule ontology (Turtle) from the YAML source of truth.

Usage:
    uv run python converters/schedule/yaml2ttl.py
"""

import re
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader
from rdflib import Graph

BASE_DIR = Path(__file__).resolve().parents[2]
TEMPLATE_DIR = BASE_DIR / "converters" / "schedule" / "templates"
YAML_PATH = BASE_DIR / "serializers" / "schedule" / "schedule.yaml"
OUTPUT_PATH = BASE_DIR / "ontologies" / "schedule" / "schedule.ttl"


# -----------------
# Utility functions
# -----------------


def pascal_case(name: str) -> str:
    """Turn a human-readable name into a PascalCase ontology name.

    Existing capitalization is preserved: "Currency code" -> "CurrencyCode",
    "Unique ID" -> "UniqueID", "Text-to-speech field" -> "TextToSpeechField".
    """
    words = re.split(r"[\s\-_/]+", name.strip())
    joined = "".join(word[:1].upper() + word[1:] for word in words if word)
    return re.sub(r"[^0-9A-Za-z]", "", joined)


def singularize(word: str) -> str:
    """Naive English singularization, good enough for GTFS file names."""
    if word.endswith("ies"):
        return word[:-3] + "y"
    if word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def class_name(file_name: str) -> str:
    """Turn a GTFS file name into a class name.

    "stop_times.txt" -> "StopTime", "agency.txt" -> "Agency",
    "locations.geojson" -> "Location".
    """
    stem = file_name.split(".")[0]
    words = stem.split("_")
    words[-1] = singularize(words[-1])
    return pascal_case(" ".join(words))


def file_id(file_name: str) -> str:
    """Turn a GTFS file name into a dataset file individual name.

    "stop_times.txt" -> "StopTimesFile", "locations.geojson" -> "LocationsFile".
    """
    stem = file_name.split(".")[0]
    return pascal_case(stem.replace("_", " ")) + "File"


def ttl_escape(value: str) -> str:
    """Escape a value for safe inclusion in a Turtle string literal."""
    return str(value).replace("\\", "\\\\").replace('"', '\\"')


# -------------
# Build process
# -------------


def load_source() -> dict:
    with open(YAML_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def collect_extra_types(field_files: list, base_types: list) -> list:
    """Field types referenced in field definitions but absent from the
    base field type definitions (e.g. "Unique ID", "Non-negative integer")."""
    base = {pascal_case(t["name"]) for t in base_types}
    extras = {}
    for file in field_files:
        for field in file.get("fields", []):
            type_id = pascal_case(field["type"])
            if type_id not in base:
                extras[type_id] = field["type"]
    return [{"id": k, "label": v} for k, v in sorted(extras.items())]


def build_context(data: dict) -> dict:
    conventions = data["document_conventions"]
    types = conventions["field_types"]["types"]
    field_files = data["field_definitions"]["files"]
    return {
        "metadata": data["metadata"],
        "terms": conventions["term_definitions"]["terms"],
        "conditions": conventions["presence"]["conditions"],
        "types": types,
        "signs": conventions["field_signs"]["signs"],
        "files": data["dataset_files"]["files"],
        "field_files": field_files,
        "extra_types": collect_extra_types(field_files, types),
    }


def render(context: dict) -> str:
    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
    env.filters["pascal"] = pascal_case
    env.filters["class_name"] = class_name
    env.filters["file_id"] = file_id
    env.filters["ttl"] = ttl_escape
    return env.get_template("schedule.ttl.jinja").render(**context)


def validate(path: Path) -> int:
    """Parse the generated Turtle with rdflib; raises if invalid."""
    graph = Graph()
    graph.parse(path, format="turtle")
    return len(graph)


def main() -> None:
    data = load_source()
    output = render(build_context(data))
    OUTPUT_PATH.write_text(output, encoding="utf-8")
    triples = validate(OUTPUT_PATH)
    print(f"Wrote {OUTPUT_PATH.relative_to(BASE_DIR)} ({triples} triples)")


if __name__ == "__main__":
    main()
