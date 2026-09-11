#!/usr/bin/env python3
"""Derive the browser form model and the reference catalog for the editor.

Two things the composites page needs in order to edit the file rather than
only display it:

    form      the vocabulary — entities, cardinalities, modes, languages,
              patterns — read out of composites.schema.json so it is never
              written twice. Adding an entity to the schema adds it to the
              form.
    catalog   every reference that could be typed, resolved once at build
              time. The editor offers them as a pick list, and the page can
              re-resolve an edited document without asking the server.

The catalog is what lets the whole page re-render from an unsaved draft: a
reference the reader just typed is looked up here, exactly as the Python
resolver would have looked it up in the reference files.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# rt_spec knows how to walk the protobuf message graph. Imported by path
# because these converters are run as scripts rather than as a package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "realtime"))
import rt_spec  # noqa: E402

LANGS = ("es", "en", "pt")


def _trim(entry: dict) -> dict:
    """Drop empty values. The catalog is embedded in the page, and 869 entries
    carrying empty labels and null components is a third of its size."""
    return {k: v for k, v in entry.items() if v not in (None, "", {}, [], False)}

# How deep to walk the protobuf messages when enumerating realtime paths.
# Four covers everything the proposal reaches (Alert.header_text.translation.text)
# without letting a self-referential message run away.
MAX_RT_DEPTH = 4


def _enum(schema: dict, *path: str) -> list:
    node = schema
    for step in path:
        node = node[step]
    return node.get("enum") or ([node["const"]] if "const" in node else [])


def form_model(schema: dict) -> dict:
    """The vocabulary the form draws from, read out of the schema."""
    d = schema["definitions"]
    composite = d["composite"]["properties"]
    prop = d["prop"]["properties"]

    return {
        "entities": composite["entity"]["enum"],
        "cardinalities": composite["cardinality"]["enum"],
        "modes": prop["mode"]["enum"],
        "langs": list(LANGS),
        "langsRequired": d["i18nBlock"]["required"],
        # Patterns are echoed to the browser so it rejects the same strings the
        # schema would, instead of a looser guess at them.
        "refPatterns": [b["pattern"] for b in d["ref"]["oneOf"]],
        "namePattern": prop["name"]["pattern"],
        "compositeNamePattern": schema["properties"]["composites"]["propertyNames"]["pattern"],
        "viewNamePattern": schema["properties"]["views"]["propertyNames"]["pattern"],
        "derivedNamePattern": schema["properties"]["derived_sources"]["propertyNames"]["pattern"],
        "pathPattern": d["view"]["properties"]["path"]["pattern"],
        "freshnessPattern": prop["freshness"]["pattern"],
        # Emission order, so a rewritten entry keeps the file's own shape.
        "compositeKeys": list(composite),
        "propKeys": list(prop),
        "paramKeys": list(d["param"]["properties"]),
        "viewKeys": list(d["view"]["properties"]),
        "derivedKeys": list(d["derivedSource"]["properties"]),
    }


def schedule_catalog(spec: dict, annotations: dict) -> dict[str, dict]:
    """Every GTFS Schedule field, with whatever schedule.ui.yaml says about it."""
    out = {}
    for entry in spec.get("field_definitions", {}).get("files", []):
        table = entry["file"].rsplit(".", 1)[0]
        for field in entry.get("fields") or []:
            path = f"{table}.{field['name']}"
            note = annotations.get(path) or {}
            out[f"schedule:{path}"] = _trim({
                "feed": "schedule",
                "path": path,
                "group": table,
                "type": field.get("type", ""),
                "presence": field.get("presence", ""),
                "component": note.get("component"),
                "annotated": bool(note),
                "label": _trim({l: (note.get("i18n", {}).get(l) or {}).get("label", "")
                                for l in LANGS}),
            })
    return out


def realtime_catalog(spec: dict, annotations: dict) -> dict[str, dict]:
    """Every walkable realtime path, so arrival.time and departure.time both exist.

    Many paths reach one field definition, and the annotation belongs to the
    definition — so `key` says which one, and every path that reaches it
    carries the same annotation. That is what makes the two pages agree about
    whether a displayed realtime field is annotated.

    A message already on the current path is not descended into again; without
    that guard a self-referential message would enumerate forever.
    """
    idx = rt_spec.index(spec)
    out: dict[str, dict] = {}

    def walk(element: dict, prefix: str, depth: int, seen: frozenset) -> None:
        if element.get("data_type") != "message" or depth > MAX_RT_DEPTH:
            return
        near = idx["positions"].get(element["name"], [None])[0]
        for field in element.get("fields") or []:
            path = f"{prefix}.{field['name']}"
            key = f"{element['name']}.{field['name']}"
            type_name, data_type = rt_spec.field_type(field)
            note = annotations.get(key) or {}
            out[f"realtime:{path}"] = _trim({
                "feed": "realtime",
                "path": path,
                "key": key,
                "group": prefix.split(".", 1)[0],
                "type": type_name,
                "presence": field.get("presence", ""),
                "cardinality": field.get("cardinality", ""),
                "origin": note.get("origin"),
                "component": note.get("component"),
                "annotated": bool(note),
                "label": _trim({l: (note.get("i18n", {}).get(l) or {}).get("label", "")
                                for l in LANGS}),
            })
            if data_type == "message" and type_name not in seen:
                nested = rt_spec.element_at(idx, type_name, near)
                if nested:
                    walk(nested, path, depth + 1, seen | {type_name})

    for element in rt_spec.messages(idx):
        walk(element, element["name"], 1, frozenset({element["name"]}))
    return out


def derived_catalog(document: dict) -> dict[str, dict]:
    """The artifacts declared in the file itself, which may change as it is edited."""
    return {
        f"derived:{name}": _trim({
            "feed": "derived",
            "path": name,
            "group": "derived",
            "type": "derived",
            "from": artifact.get("from", []),
            "label": _trim({l: (artifact.get("i18n", {}).get(l) or {}).get("label", "")
                            for l in LANGS}),
        })
        for name, artifact in (document.get("derived_sources") or {}).items()
    }


def build(schema_path: Path, spec: dict, realtime: dict, annotations: dict,
          realtime_annotations: dict, document: dict) -> dict:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    return {
        "form": form_model(schema),
        # Derived entries are rebuilt in the browser as the reader edits
        # derived_sources, so these are only the starting set.
        "catalog": schedule_catalog(spec, annotations)
                   | realtime_catalog(realtime, realtime_annotations)
                   | derived_catalog(document),
    }
