"""Builds HTML documentation of the GTFS Schedule ontology with Ontospy.

Usage:
    uv run python converters/schedule/ttl2docs.py
"""

from pathlib import Path

from ontospy import Ontospy
from ontospy.gendocs.viz.viz_html_multi import KompleteViz

BASE_DIR = Path(__file__).resolve().parents[2]
TTL_PATH = BASE_DIR / "ontologies" / "schedule" / "schedule.ttl"
OUTPUT_DIR = BASE_DIR / "documentation" / "schedule" / "ontology"
TITLE = "GTFS Schedule Ontology"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    model = Ontospy(uri_or_path=str(TTL_PATH), verbose=False)
    docs = KompleteViz(model, title=TITLE)
    docs.build(output_path=str(OUTPUT_DIR))
    print(f"Wrote {OUTPUT_DIR.relative_to(BASE_DIR)}/index.html")


if __name__ == "__main__":
    main()
