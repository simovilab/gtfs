"""Tests for the schedule YAML -> DBML converter and the YAML's fidelity to the spec.

Spec conformance tests read references/schedule.md, the vendored copy of
https://github.com/google/transit/blob/master/gtfs/spec/en/reference.md.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "converters" / "schedule"))

import yaml2dbml as m  # noqa: E402

YAML_PATH = ROOT / "serializers" / "schedule" / "schedule.yaml"
DBML_PATH = ROOT / "models" / "schedule" / "dbml" / "schedule.dbml"
SPEC_PATH = ROOT / "references" / "schedule.md"

SPEC = SPEC_PATH.read_text(encoding="utf-8")
DATA = m.load_yaml(YAML_PATH)
FILE_ENTRIES = DATA["field_definitions"]["files"]
FLAT_FILES = [e for e in FILE_ENTRIES if e["file"] != "locations.geojson"]
SECTIONS = {
    name: body
    for name, body in re.findall(
        r"^### (\S+)\n(.*?)(?=^### |\Z)", SPEC.split("## Field Definitions", 1)[1], re.S | re.M
    )
    if name.endswith((".txt", ".geojson"))
}
# Some spec rows omit the trailing pipe, so the description runs to end of line.
SPEC_ROW = re.compile(r"^\|\s*`([a-z_]+)`\s*\|\s*([^|]*)\|\s*([^|]*)\|(.*?)\|?\s*$", re.M)


@pytest.fixture(scope="module")
def built():
    return m.build_tables(DATA)


# --- type mapping ------------------------------------------------------------


@pytest.mark.parametrize(
    "gtfs_type, dbml_type",
    [
        ("Text", "string"),
        ("Text or URL or Email or Phone number", "string"),
        ("Unique ID", "string"),
        ("Foreign ID", "string"),
        ("Timezone", "string"),
        ("Integer", "int"),
        ("Non-negative integer", "int"),
        ("Non-null integer", "int"),
        ("Latitude", "float"),
        ("Currency amount", "float"),
        ("Date", "date"),
        ("Time", "interval"),
        ("Local time", "time"),
        ("Timestamp", "datetime"),
        ("", "string"),
        ("Something new", "string"),
    ],
)
def test_map_type(gtfs_type, dbml_type):
    assert m.map_type(gtfs_type) == dbml_type


def test_every_yaml_type_is_mapped_explicitly():
    types = {str(f.get("type")) for e in FILE_ENTRIES for f in m.flatten_fields(e.get("fields", []))}
    assert sorted(t for t in types if not m.is_known_type(t)) == []


# --- text escaping -----------------------------------------------------------


def test_escaping_for_single_and_double_quoted_strings():
    assert m.escape_single("agency's routes") == "agency\\'s routes"
    assert m.escape_note('say "hi"') == 'say \\"hi\\"'
    assert m.escape_note("back\\slash") == "back\\\\slash"


def test_notes_are_one_line_without_html_breaks():
    assert m.escape_note(["First.<br>Second.", "Third.\n  Fourth.<hr/>"]) == "First. Second. Third. Fourth."


# --- enums, references, nested fields ------------------------------------------


def test_flatten_options_plain():
    options = [{"value": "0 or empty", "description": "None."}, {"value": 1, "description": "It's on."}]
    assert m.flatten_options(options) == [
        {"value": "0 or empty", "description": "None."},
        {"value": "1", "description": "It\\'s on."},
    ]


def test_flatten_options_merges_categories():
    options = [
        {"category": "Parentless", "values": [{"value": "0", "description": "A."}, {"value": "1", "description": "B."}]},
        {"category": "Child", "values": [{"value": "0", "description": "C."}]},
    ]
    assert m.flatten_options(options) == [
        {"value": "0", "description": "Parentless: A. Child: C."},
        {"value": "1", "description": "Parentless: B."},
    ]


def test_flatten_options_skips_empty_and_malformed_values():
    assert m.flatten_options([{"value": "", "description": "x"}, "junk"]) == []


def test_enum_without_options_falls_back_to_string():
    data = {"field_definitions": {"files": [{"file": "t.txt", "fields": [{"name": "e", "type": "Enum"}]}]}}
    enums, [table] = m.build_tables(data)
    assert enums == [] and table["columns"][0]["type"] == "string"


def test_fk_targets():
    assert m.fk_targets(None) == []
    assert m.fk_targets("stops.stop_id") == ["stops.stop_id"]
    assert m.fk_targets(["calendar.service_id", "calendar_dates.txt.service_id"]) == [
        "calendar.service_id",
        "calendar_dates.service_id",
    ]


def test_ref_caveats():
    unique = {"stops.stop_id"}
    assert m.ref_caveat(["stops.stop_id"], unique) == ""
    assert m.ref_caveat([], unique) == ""
    assert "not a unique key" in m.ref_caveat(["stops.zone_id"], unique)
    assert "one of" in m.ref_caveat(["calendar.service_id", "calendar_dates.service_id"], unique)


def test_flatten_fields_geojson():
    fields = [
        {"name": "type", "type": "String"},
        {
            "name": "features",
            "type": "Array",
            "children": [
                {"name": "type", "type": "String"},
                {"name": "id", "type": "String", "presence": "Required"},
                {"name": "properties", "type": "Object", "children": [{"name": "stop_name", "type": "String"}]},
                {"name": "geometry", "type": "Object", "children": [{"name": "type"}, {"name": "coordinates"}]},
            ],
        },
    ]
    flat = m.flatten_fields(fields)
    assert [f["name"] for f in flat] == ["id", "stop_name", "geometry"]
    assert flat[2]["type"] == "Text" and "children" not in flat[2]


def test_flatten_fields_leaves_flat_tables_alone():
    fields = [{"name": "type", "type": "Text"}]
    assert m.flatten_fields(fields) is fields


# --- primary keys --------------------------------------------------------------


def _one_table(pk):
    fields = [{"name": n, "type": "Text", "presence": "Required"} for n in ("a", "b")]
    return {"field_definitions": {"files": [{"file": "t.txt", "primary_key": pk, "fields": fields}]}}


@pytest.mark.parametrize(
    "pk, inline, composite",
    [
        ("a", ["a"], []),
        (["a"], ["a"], []),
        (["a", "b"], [], ["a", "b"]),
        ("*", [], ["a", "b"]),
        ("none", [], []),
        (None, [], []),
    ],
)
def test_primary_keys(pk, inline, composite):
    _, [table] = m.build_tables(_one_table(pk))
    assert [c["name"] for c in table["columns"] if "pk" in c["attrs"]] == inline
    assert table["composite_pk"] == composite


# --- generated DBML ----------------------------------------------------------------


def test_committed_dbml_is_in_sync_with_yaml():
    expected = m.render_dbml(DATA)
    assert DBML_PATH.read_text(encoding="utf-8") == expected, "regenerate: uv run python converters/schedule/yaml2dbml.py"


def test_every_spec_file_becomes_a_table(built):
    _, tables = built
    assert sorted(t["name"] for t in tables) == sorted(m.normalize_table_name(n) for n in SECTIONS)


def test_references_resolve_to_existing_columns(built):
    _, tables = built
    columns = {f"{t['name']}.{c['name']}" for t in tables for c in t["columns"]}
    refs = {a.removeprefix("ref: > gtfs.") for t in tables for c in t["columns"] for a in c["attrs"] if a.startswith("ref:")}
    assert refs and sorted(refs - columns) == []


def test_enum_types_are_defined(built):
    enums, tables = built
    used = {c["type"] for t in tables for c in t["columns"] if c["type"].startswith("gtfs.")}
    assert used - {f"gtfs.{e['name']}" for e in enums} == set()


def test_locations_geojson_is_an_id_keyed_table(built):
    _, tables = built
    locations = next(t for t in tables if t["name"] == "locations")
    assert [c["name"] for c in locations["columns"]] == ["id", "stop_name", "stop_desc", "geometry"]
    assert "pk" in locations["columns"][0]["attrs"]


@pytest.mark.skipif(shutil.which("npx") is None, reason="needs Node/npx for @dbml/cli")
def test_dbml_parses_with_official_parser(tmp_path):
    out = tmp_path / "schedule.sql"
    result = subprocess.run(
        ["npx", "-y", "-p", "@dbml/cli@3", "dbml2sql", str(DBML_PATH), "--postgres", "-o", str(out)],
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert out.exists(), result.stdout + result.stderr
    assert out.read_text(encoding="utf-8").count("CREATE TABLE") == len(FILE_ENTRIES)


# --- spec conformance (references/schedule.md) ---------------------------------------


def spec_rows(file_name):
    return [(n, t.strip(), p.replace("*", "").strip(), d) for n, t, p, d in SPEC_ROW.findall(SECTIONS[file_name])]


def spec_fk_targets(spec_type):
    geojson = re.search(r"`(\w+)` from `(\w+)\.geojson`", spec_type)
    if geojson:
        return [f"{geojson.group(2)}.{geojson.group(1)}"]
    return sorted(m.fk_targets(re.findall(r"`([^`]+\.[^`]+)`", spec_type)))


def spec_enum_values(description):
    found = re.findall(r"(?:^|<br>)\s*(?:-\s*)?`([^`]+)`", description)
    return sorted({v for v in found if re.fullmatch(r"-?\d+", v)})


def yaml_enum_values(options):
    values = set()
    for option in options or []:
        for v in option.get("values", [option]):
            match = re.match(r"\s*(-?\d+)", str(v.get("value")))
            if match:
                values.add(match.group(1))
    return sorted(values)


def test_revision_matches_spec():
    revised = re.search(r"\*\*Revised (\w+ \d+, \d{4})", SPEC).group(1)
    expected = datetime.strptime(revised, "%B %d, %Y").date().isoformat()
    assert str(DATA["metadata"]["revision_date"]) == expected


def test_dataset_file_presence_matches_spec():
    spec_files = {
        name: presence.replace("*", "").strip()
        for name, presence in re.findall(
            r"^\|\s*\[([a-z_]+\.(?:txt|geojson))\]\([^)]*\)\s*\|\s*([^|]+)\|", SPEC, re.M
        )
    }
    yaml_files = {f["name"]: f.get("presence") for f in DATA["dataset_files"]["files"]}
    assert yaml_files == spec_files


@pytest.mark.parametrize("entry", FLAT_FILES, ids=lambda e: e["file"])
def test_fields_match_spec(entry):
    rows = spec_rows(entry["file"])
    fields = entry["fields"]
    assert [f["name"] for f in fields] == [r[0] for r in rows]
    for field, (name, spec_type, presence, description) in zip(fields, rows):
        assert str(field.get("presence")).lower() == presence.lower(), name
        if spec_type.startswith("Foreign ID"):
            assert field["type"] == "Foreign ID", name
            expected = spec_fk_targets(spec_type)
            if expected:  # polymorphic references (translations.record_id) name no target
                assert sorted(m.fk_targets(field.get("foreign_key"))) == expected, name
        else:
            assert str(field["type"]).lower() == spec_type.lower(), name
        if spec_type == "Enum":
            # "Functions in the same way as `monday`" lists no values of its own
            same_as = re.search(r"same way as `(\w+)`", description)
            if same_as and not spec_enum_values(description):
                description = next(r[3] for r in rows if r[0] == same_as.group(1))
            assert field.get("options"), name
            assert yaml_enum_values(field["options"]) == spec_enum_values(description), name


@pytest.mark.parametrize("entry", FILE_ENTRIES, ids=lambda e: e["file"])
def test_primary_key_matches_spec(entry):
    section = SECTIONS[entry["file"]]
    match = re.search(r"Primary key \(([^)]*)\)", section, re.I)
    if entry["file"] == "locations.geojson":
        # No "Primary key" line; the spec requires every Feature `id` to be unique instead.
        assert not match and "The `id` must be unique" in section
        assert entry.get("primary_key") == "id"
        return
    assert match, "spec section has no primary key line"
    spec_pk = [c.strip() for chunk in re.findall(r"`([^`]+)`", match.group(1)) for c in chunk.split(",")] or ["none"]
    pk = entry.get("primary_key")
    assert (pk if isinstance(pk, list) else [pk]) == spec_pk
