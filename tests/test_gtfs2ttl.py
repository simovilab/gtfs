"""GTFS ZIP -> RDF tests using the repository's actual ontology mappings."""

import io
import json
import sys
from pathlib import Path
from zipfile import ZipFile

import pytest
from rdflib import Graph, Literal, RDF, URIRef, XSD
from rdflib.compare import isomorphic

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "converters" / "schedule"))

import gtfs2ttl as converter

GTFS = converter.GTFS
BASE = "https://example.org/feed/"


def archive(tmp_path, files):
    path = tmp_path / "input.zip"
    with ZipFile(path, "w") as zipped:
        for name, content in files.items():
            zipped.writestr(name, content)
    return path


def convert(tmp_path, files):
    path = archive(tmp_path, files)
    output = converter.convert(str(path), tmp_path / "out", BASE)
    assert output.name == "feed.ttl"
    return Graph().parse(output, format="turtle")


def subject(graph, predicate, value):
    return graph.value(predicate=predicate, object=value)


def test_datatypes_literals_unicode_and_blank_values(tmp_path):
    graph = convert(tmp_path, {
        "agency.txt": (
            '\ufeffagency_id,agency_name,agency_url,agency_phone\n'
            '001,"San José, ""Central""",https://example.org,'
            '\n'
        ),
        "stops.txt": "stop_id,stop_lat,stop_lon\nA/B,9.1234567890123456789,-84.01\n",
        "stop_times.txt": (
            "trip_id,stop_sequence,arrival_time\nT1,01,25:35:00\n"
        ),
    })
    agency = subject(graph, GTFS.agency_id, Literal("001", datatype=XSD.string))
    assert (agency, RDF.type, GTFS.Agency) in graph
    assert (
        agency, GTFS.agency_name, Literal('San José, "Central"', datatype=XSD.string)
    ) in graph
    assert (agency, GTFS.agency_url, URIRef("https://example.org")) in graph
    assert not list(graph.objects(agency, GTFS.agency_phone))
    stop = subject(graph, GTFS.stop_id, Literal("A/B", datatype=XSD.string))
    assert "%2F" in str(stop)
    assert str(graph.value(stop, GTFS.stop_lat)) == "9.1234567890123456789"
    assert graph.value(stop, GTFS.stop_lat).datatype == XSD.decimal
    time = next(graph.subjects(RDF.type, GTFS.StopTime))
    assert graph.value(time, GTFS.stop_sequence) == Literal(1)
    assert graph.value(time, GTFS.arrival_time) == Literal("25:35:00", datatype=XSD.string)


def test_relations_inverse_composites_groups_and_alternative_targets(tmp_path):
    graph = convert(tmp_path, {
        "agency.txt": "agency_id,agency_name\nA,Operator\n",
        "routes.txt": "route_id,agency_id\nR,A\n",
        "trips.txt": "trip_id,route_id,service_id,shape_id\nT,R,S,G\n",
        "calendar.txt": "service_id,monday\nS,1\n",
        "calendar_dates.txt": "service_id,date,exception_type\nS,20261103,1\nS,20261104,2\n",
        "shapes.txt": "shape_id,shape_pt_sequence,shape_pt_lat\nG,0,9.1\nG,1,9.2\n",
    })
    agency = next(graph.subjects(RDF.type, GTFS.Agency))
    route = next(graph.subjects(RDF.type, GTFS.Route))
    trip = next(graph.subjects(RDF.type, GTFS.Trip))
    assert (agency, GTFS.operatesRoute, route) in graph
    assert (route, GTFS.isOperatedByAgency, agency) in graph
    assert (route, GTFS.hasTrip, trip) in graph
    assert len(set(graph.objects(trip, GTFS.runsOnCalendar))) == 1
    assert len(set(graph.objects(trip, GTFS.runsOnCalendarDate))) == 2
    assert len(set(graph.objects(trip, GTFS.hasShape))) == 2
    query = """
        PREFIX gtfs: <http://gtfs.simovi.org/schedule#>
        SELECT ?name ?trip WHERE {
          ?a gtfs:agency_name ?name; gtfs:operatesRoute/gtfs:hasTrip ?trip.
        }
    """
    assert [str(row.name) for row in graph.query(query)] == ["Operator"]


def test_translation_discriminator_and_stop_time_composite_key(tmp_path):
    graph = convert(tmp_path, {
        "agency.txt": "agency_id\nshared\n",
        "stops.txt": "stop_id\nshared\n",
        "stop_times.txt": "trip_id,stop_sequence\nT,1\nT,02\n",
        "translations.txt": (
            "table_name,field_name,language,translation,record_id,record_sub_id\n"
            "stops,stop_name,en,Station,shared,\n"
            "stop_times,stop_headsign,en,Downtown,T,2\n"
        ),
    })
    translation = subject(graph, GTFS.translation, Literal("Station", datatype=XSD.string))
    assert len(set(graph.objects(translation, GTFS.translatesStop))) == 1
    assert not list(graph.objects(translation, GTFS.translatesAgency))
    translation = subject(graph, GTFS.translation, Literal("Downtown", datatype=XSD.string))
    targets = list(graph.objects(translation, GTFS.translatesStopTime))
    assert len(targets) == 1
    assert graph.value(targets[0], GTFS.stop_sequence) == Literal(2)


def test_optional_id_singleton_and_full_row_keys(tmp_path):
    graph = convert(tmp_path, {
        "agency.txt": "agency_name\nOperator\n",
        "feed_info.txt": "feed_lang\nes\n",
        "fare_rules.txt": "fare_id,origin_id\nF,A\nF,B\n",
    })
    assert len(set(graph.subjects(RDF.type, GTFS.Agency))) == 1
    assert len(set(graph.subjects(RDF.type, GTFS.FeedInfo))) == 1
    assert len(set(graph.subjects(RDF.type, GTFS.FareRule))) == 2


def test_extension_columns_and_unresolved_references_are_reported(tmp_path, caplog):
    graph = convert(tmp_path, {
        "trips.txt": "trip_id,route_id,custom_column\nT,missing,001\n",
    })
    trip = next(graph.subjects(RDF.type, GTFS.Trip))
    assert graph.value(trip, GTFS.custom_column) == Literal("001", datatype=XSD.string)
    assert graph.value(trip, GTFS.route_id) == Literal("missing", datatype=XSD.string)
    assert not list(graph.objects(trip, GTFS.belongsToRoute))
    assert "extension columns" in caplog.text
    assert "no matching foreign-key target" in caplog.text


def test_geojson_features_and_geometry_are_preserved(tmp_path):
    collection = {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature", "id": "zone",
            "properties": {"stop_name": "Zone", "stop_desc": "Area"},
            "geometry": {"type": "Polygon", "coordinates": [[[1, 2], [3, 4], [1, 2]]]},
        }],
    }
    graph = convert(tmp_path, {
        "locations.geojson": json.dumps(collection),
        "stop_times.txt": "trip_id,stop_sequence,location_id\nT,1,zone\n",
    })
    location = next(graph.subjects(RDF.type, GTFS.Location))
    time = next(graph.subjects(RDF.type, GTFS.StopTime))
    assert (time, GTFS.atLocation, location) in graph
    properties = graph.value(location, GTFS.properties)
    assert graph.value(properties, GTFS.stop_name) == Literal("Zone")
    geometry = graph.value(location, GTFS.geometry)
    assert graph.value(geometry, GTFS.type) == Literal("Polygon")
    assert len(list(graph.items(graph.value(geometry, GTFS.coordinates)))) == 1


def test_remote_and_local_inputs_produce_equivalent_graphs(tmp_path, monkeypatch):
    path = archive(tmp_path, {"stops.txt": "stop_id,stop_name\nS,Central\n"})
    monkeypatch.setattr(converter, "urlopen", lambda url, timeout: io.BytesIO(path.read_bytes()))
    remote = converter.convert("https://example.org/feed.zip", tmp_path / "remote")
    local = converter.convert(str(path), tmp_path / "local")
    assert isomorphic(Graph().parse(remote), Graph().parse(local))
    assert remote.read_bytes() == local.read_bytes()


@pytest.mark.parametrize("contents, message", [
    ("stop_id,stop_lat\nS,banana\n", "Invalid decimal"),
    ("stop_id,location_type\nS,1.5\n", "Invalid integer"),
    ("stop_id,stop_url\nS,not-a-url\n", "absolute IRI"),
    ("stop_id,stop_id\nS,T\n", "duplicate column"),
    ("stop_id,stop_name\nS\n", "column count"),
    ("stop_id\nS\nS\n", "duplicate primary key"),
])
def test_failed_conversion_preserves_prior_output(tmp_path, contents, message):
    path = archive(tmp_path, {"stops.txt": contents})
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    output = output_dir / "feed.ttl"
    output.write_text("prior result")
    with pytest.raises(ValueError, match=message):
        converter.convert(str(path), output_dir, BASE)
    assert output.read_text() == "prior result"
    assert list(output_dir.iterdir()) == [output]


def test_zip_members_are_read_without_extraction(tmp_path):
    graph = convert(tmp_path, {"../../stops.txt": "stop_id\nS\n"})
    assert len(set(graph.subjects(RDF.type, GTFS.Stop))) == 1
    assert not (tmp_path.parent / "stops.txt").exists()


def test_unknown_or_empty_archives_are_rejected(tmp_path):
    path = archive(tmp_path, {"readme.txt": "not GTFS"})
    with pytest.raises(ValueError, match="no recognized"):
        converter.convert(str(path), tmp_path / "out")
