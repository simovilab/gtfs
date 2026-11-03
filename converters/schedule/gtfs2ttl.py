"""Convert a local or HTTP(S) GTFS ZIP into feed.ttl.

uv run python converters/schedule/gtfs2ttl.py SOURCE --output-dir ./output
"""

import argparse
import csv
import hashlib
import io
import json
import logging
import re
import shutil
import tempfile
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import quote, urlsplit
from urllib.request import urlopen
from zipfile import BadZipFile, ZipFile

import yaml
from rdflib import BNode, Graph, Literal, Namespace, RDF, URIRef, XSD
from rdflib.collection import Collection

from yaml2ttl import class_name, type_list

ROOT = Path(__file__).resolve().parents[2]
SPEC_DIR = ROOT / "serializers" / "schedule"
GTFS = Namespace("http://gtfs.simovi.org/schedule#")
LOGGER = logging.getLogger(__name__)


@dataclass
class Record:
    table: str
    number: int
    values: dict[str, Any]
    subject: URIRef


def load_specification() -> tuple[dict[str, dict], dict[str, dict], list[dict]]:
    with (SPEC_DIR / "schedule.yaml").open(encoding="utf-8") as stream:
        tables = {
            entry["file"]: entry
            for entry in yaml.safe_load(stream)["field_definitions"]["files"]
        }
    with (SPEC_DIR / "fieldtypes.yaml").open(encoding="utf-8") as stream:
        types = {entry["name"]: entry for entry in yaml.safe_load(stream)["types"]}
    with (SPEC_DIR / "relations.yaml").open(encoding="utf-8") as stream:
        relations = yaml.safe_load(stream)["relations"]
    expected = {
        (name, field["name"], target)
        for name, table in tables.items()
        for field in table["fields"]
        if "Foreign ID" in type_list(field["type"])
        for target in type_list(field["foreign_key"])
    }
    configured = [
        (relation["file"], relation["field"], relation["references"])
        for relation in relations
    ]
    if len(configured) != len(set(configured)):
        raise ValueError("Duplicate foreign-key mappings in relations.yaml")
    if set(configured) != expected:
        raise ValueError(
            "relations.yaml differs from schedule.yaml foreign keys: "
            f"missing={sorted(expected - set(configured))}, "
            f"stale={sorted(set(configured) - expected)}"
        )
    return tables, types, relations


def check_iri(value: str) -> URIRef:
    if not urlsplit(value).scheme or re.search(r'[\s<>"{}|\\^`\x00-\x1f]', value):
        raise ValueError(f"Expected an absolute IRI, got {value!r}")
    return URIRef(value)


def record_iri(base: str, table: dict, values: dict[str, Any]) -> URIRef:
    primary = table["primary_key"]
    keys = [primary] if isinstance(primary, str) else primary
    if primary in ("*", "none"):
        identity = values if primary == "*" else ["singleton"]
    elif len(keys) == 1 and not values.get(keys[0]):
        # Optional IDs (e.g. agency_id) may be omitted in a valid feed.
        identity = values
    else:
        identity = [values.get(key, "") for key in keys]
    if isinstance(identity, dict):
        canonical = json.dumps(identity, sort_keys=True, ensure_ascii=False)
        suffix = "row/" + hashlib.sha256(canonical.encode()).hexdigest()
    else:
        suffix = "key/" + quote(
            json.dumps(identity, ensure_ascii=False, separators=(",", ":")), safe=""
        )
    return URIRef(f"{base}{table['file']}/{suffix}")


def csv_records(archive: ZipFile, member: str) -> Iterator[dict[str, str]]:
    with archive.open(member) as binary:
        with io.TextIOWrapper(binary, encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream, strict=True)
            headers = reader.fieldnames
            if not headers or any(not name for name in headers):
                raise ValueError(f"{member}: missing or empty column names")
            if len(headers) != len(set(headers)):
                raise ValueError(f"{member}: duplicate column names")
            for number, row in enumerate(reader, 2):
                if None in row or any(value is None for value in row.values()):
                    raise ValueError(f"{member}:{number}: column count differs from header")
                yield row


def read_records(
    archive_path: Path, tables: dict[str, dict], base: str
) -> tuple[list[Record], dict[str, Any] | None]:
    records: list[Record] = []
    seen: set[URIRef] = set()
    collection = None
    with ZipFile(archive_path) as archive:
        members: dict[str, str] = {}
        for info in archive.infolist():
            if info.is_dir():
                continue
            name = Path(info.filename).name
            if name not in tables:
                LOGGER.warning("Skipping file not in the specification: %s", info.filename)
                continue
            if name in members:
                raise ValueError(f"Duplicate GTFS file in ZIP: {name}")
            members[name] = info.filename
        if not members:
            raise ValueError("ZIP contains no recognized GTFS tables")
        for name, member in sorted(members.items()):
            table = tables[name]
            fields = {field["name"] for field in table["fields"]}
            if name == "locations.geojson":
                with archive.open(member) as stream:
                    collection = json.load(stream)
                if collection.get("type") != "FeatureCollection":
                    raise ValueError("locations.geojson must contain a FeatureCollection")
                rows = []
                for feature in collection["features"]:
                    if feature.get("type") != "Feature" or feature.get("id") is None:
                        raise ValueError("Every GeoJSON Feature must have a type and id")
                    rows.append(feature)
            else:
                rows = list(csv_records(archive, member))
                unknown = set(rows[0]) - fields if rows else set()
                if unknown:
                    LOGGER.warning(
                        "%s: preserving extension columns as strings: %s",
                        name, ", ".join(sorted(unknown)),
                    )
            for number, values in enumerate(rows, 1):
                subject = record_iri(base, table, values)
                if subject in seen:
                    raise ValueError(f"{name}: record {number}: duplicate primary key")
                seen.add(subject)
                records.append(Record(name, number, values, subject))
    if not records:
        raise ValueError("GTFS archive contains no records")
    return records, collection


def enum_is_integer(field: dict) -> bool:
    options = [
        item["value"]
        for option in field.get("options", [])
        for item in option.get("values", [option])
    ]
    if not options:
        raise ValueError(f"Enum {field['name']} has no options in schedule.yaml")
    return all(
        re.fullmatch(r"-?\d+(?:\s+(?:\(or empty\)|or empty))?", str(value))
        for value in options
    )


def field_value(value: str, field: dict, types: dict[str, dict]) -> Literal | URIRef:
    names = type_list(field["type"])
    if len(names) != 1:
        # A string is a valid member of the Text/URL/Email/Phone union.
        if "Text" not in names and "String" not in names:
            raise ValueError(f"Unsupported alternative field types: {names}")
        return Literal(value, datatype=XSD.string)
    name = names[0]
    spec = types[name]
    datatype = spec.get("datatype")
    if name == "Enum":
        datatype = "xsd:integer" if enum_is_integer(field) else "xsd:string"
    if datatype == "xsd:integer":
        if not re.fullmatch(r"[+-]?\d+", value, flags=re.ASCII):
            raise ValueError(f"Invalid integer: {value!r}")
        return Literal(int(value), datatype=XSD.integer)
    if datatype == "xsd:decimal":
        try:
            number = Decimal(value)
        except InvalidOperation as error:
            raise ValueError(f"Invalid decimal: {value!r}") from error
        if not number.is_finite():
            raise ValueError(f"Non-finite decimal: {value!r}")
        return Literal(format(number, "f"), datatype=XSD.decimal, normalize=False)
    if spec.get("nodeKind") == "sh:IRI":
        return check_iri(value)
    if datatype == "xsd:string" or "or" in spec:
        return Literal(value, datatype=XSD.string)
    raise ValueError(f"No scalar RDF mapping for field type {name!r}")


def add_json(graph: Graph, value: Any) -> URIRef | BNode | Literal:
    if isinstance(value, dict):
        node = BNode()
        for key, child in value.items():
            graph.add((node, GTFS[key], add_json(graph, child)))
        return node
    if isinstance(value, list):
        if not value:
            return RDF.nil
        node = BNode()
        Collection(graph, node, [add_json(graph, child) for child in value])
        return node
    if value is None:
        return Literal("null", datatype=RDF.JSON)
    return Literal(value)


def relation_index(
    records: list[Record], relations: list[dict], tables: dict[str, dict]
) -> tuple[dict[tuple[str, str, str], list[Record]], dict[str, list[dict]]]:
    stems = {Path(name).stem: name for name in tables}
    targets: set[tuple[str, str]] = set()
    by_source: dict[str, list[dict]] = defaultdict(list)
    for relation in relations:
        stem, column = relation["references"].rsplit(".", 1)
        targets.add((stems[stem], column))
        by_source[relation["file"]].append(relation)
    index: dict[tuple[str, str, str], list[Record]] = defaultdict(list)
    for record in records:
        for table, column in targets:
            if record.table == table and record.values.get(column, "") != "":
                index[(Path(table).stem, column, str(record.values[column]))].append(record)
    return index, by_source


def linked_records(
    record: Record, relation: dict, index: dict[tuple[str, str, str], list[Record]]
) -> list[Record]:
    stem, column = relation["references"].rsplit(".", 1)
    if record.table == "translations.txt":
        if record.values["table_name"] != stem:
            return []
        if stem == "stop_times":
            # record_id + record_sub_id together identify a stop-time record.
            trip = record.values.get("record_id", "")
            sequence = record.values.get("record_sub_id", "")
            if not re.fullmatch(r"[+-]?[0-9]+", sequence):
                return []
            return [
                target for target in index.get((stem, "trip_id", trip), [])
                if target.values["trip_id"] == trip
                and int(target.values["stop_sequence"]) == int(sequence)
            ]
    return index.get((stem, column, str(record.values[relation["field"]])), [])


def write_feed(
    records: list[Record], collection: dict | None, tables: dict[str, dict],
    types: dict[str, dict], relations: list[dict], base: str, output: Path,
) -> int:
    index, by_source = relation_index(records, relations, tables)
    fields = {
        name: {field["name"]: field for field in table["fields"]}
        for name, table in tables.items()
    }
    missing: dict[tuple[str, str], int] = defaultdict(int)
    count = 0
    with output.open("w", encoding="utf-8") as stream:
        stream.write(f"@prefix gtfs: <{GTFS}> .\n\n")

        def emit(graph: Graph) -> None:
            nonlocal count
            for subject, predicate, obj in sorted(graph):
                stream.write(f"{subject.n3()} {predicate.n3()} {obj.n3()} .\n")
                count += 1

        for record in records:
            graph = Graph()
            graph.add((record.subject, RDF.type, GTFS[class_name(record.table)]))
            for name, value in record.values.items():
                if value == "":
                    continue
                try:
                    if record.table == "locations.geojson":
                        obj = add_json(graph, value)
                    elif name in fields[record.table]:
                        obj = field_value(value, fields[record.table][name], types)
                    else:
                        obj = Literal(value, datatype=XSD.string)
                except (ValueError, KeyError) as error:
                    raise ValueError(
                        f"{record.table}: record {record.number}, field {name}: {error}"
                    ) from error
                graph.add((record.subject, GTFS[name], obj))
            resolved: set[str] = set()
            attempted: set[str] = set()
            for relation in by_source.get(record.table, []):
                field = relation["field"]
                if not record.values.get(field, ""):
                    continue
                if record.table == "translations.txt":
                    stem = relation["references"].rsplit(".", 1)[0]
                    if record.values["table_name"] != stem:
                        continue
                attempted.add(field)
                for target in linked_records(record, relation, index):
                    resolved.add(field)
                    graph.add((record.subject, GTFS[relation["forward"]], target.subject))
                    graph.add((target.subject, GTFS[relation["inverse"]], record.subject))
            for field in attempted - resolved:
                missing[(record.table, field)] += 1
            emit(graph)
        if collection is not None:
            graph = Graph()
            document = URIRef(f"{base}locations.geojson/document")
            features = [
                record.subject for record in records if record.table == "locations.geojson"
            ]
            head = BNode() if features else RDF.nil
            if features:
                Collection(graph, head, features)
            graph.add((document, GTFS.features, head))
            for key, value in collection.items():
                if key != "features":
                    graph.add((document, GTFS[key], add_json(graph, value)))
            emit(graph)
    for (table, field), number in sorted(missing.items()):
        LOGGER.warning(
            "%s.%s: %d record(s) have no matching foreign-key target; "
            "ID literals retained, no object links fabricated", table, field, number,
        )
    return count


def convert(source: str, output_dir: Path, base_iri: str | None = None) -> Path:
    tables, types, relations = load_specification()
    with tempfile.TemporaryDirectory(prefix="gtfs2ttl-") as work:
        if urlsplit(source).scheme in ("http", "https"):
            archive = Path(work) / "feed.zip"
            with urlopen(source, timeout=120) as response, archive.open("wb") as stream:
                shutil.copyfileobj(response, stream)
        else:
            archive = Path(source)
        with archive.open("rb") as stream:
            fingerprint = hashlib.file_digest(stream, "sha256").hexdigest()
        base = base_iri or f"https://gtfs.simovi.org/feed/{fingerprint}/"
        check_iri(base)
        if not base.endswith("/"):
            base += "/"
        records, collection = read_records(archive, tables, base)
        output_dir.mkdir(parents=True, exist_ok=True)
        output = output_dir / "feed.ttl"
        # Keep a prior output intact if conversion fails.
        with tempfile.NamedTemporaryFile(dir=output_dir, suffix=".ttl", delete=False) as tmp:
            pending = Path(tmp.name)
        try:
            count = write_feed(
                records, collection, tables, types, relations, base, pending,
            )
            pending.replace(output)
        finally:
            pending.unlink(missing_ok=True)
    LOGGER.info("Wrote %s (%d records, %d triple statements)", output, len(records), count)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", help="Local GTFS ZIP or HTTP(S) URL")
    parser.add_argument("--output-dir", type=Path, default=Path("."), help="Default: .")
    parser.add_argument("--base-iri", help="Stable absolute namespace for this feed's records")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        convert(args.source, args.output_dir, args.base_iri)
    except (OSError, ValueError, csv.Error, BadZipFile) as error:
        parser.exit(1, f"ERROR: {error}\n")


if __name__ == "__main__":
    main()
