#!/usr/bin/env python3
"""Derive the editor's form model from an annotation schema.

The browser form is generated from this model rather than from a hand-written
list of inputs, so the schema stays the single source of truth for the
annotation vocabulary: adding a component to the enum, or a rule to
`validation`, makes it appear in the editor without touching the front-end.

Nothing here names a specific feed. The same function reads
schedule.ui.schema.json and realtime.ui.schema.json, which is what lets one
explorer front-end serve both: the two vocabularies differ (Realtime has an
`origin`, no currency rules) and the difference arrives as data.

Only the shape of each input is derived here. Full JSON Schema validation is
still run by the coverage scripts in CI, which are the actual gate.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SEVERITY_REF = "#/definitions/severityWrapper"


def _deref(node: dict, schema: dict) -> dict:
    """Resolve a local $ref one level deep."""
    ref = node.get("$ref")
    if not ref or not ref.startswith("#/"):
        return node
    target: Any = schema
    for part in ref[2:].split("/"):
        target = target[part]
    return target


def _accepts_severity(node: dict) -> bool:
    """True when the rule may be written in {value, severity, notice} long form."""
    return any(b.get("$ref") == SEVERITY_REF for b in node.get("oneOf", []))


def _scalar_branch(node: dict) -> dict:
    """Strip the severityWrapper alternative, leaving the rule's own shape."""
    branches = [b for b in node.get("oneOf", []) if b.get("$ref") != SEVERITY_REF]
    if not branches:
        return node
    if len(branches) == 1:
        inner = branches[0]
        # `decimals` nests a second oneOf inside its scalar branch.
        return _scalar_branch(inner) if "oneOf" in inner else inner
    return {"oneOf": branches}


def _kind(node: dict) -> dict:
    """Map a JSON Schema fragment to an input kind the front-end knows how to draw.

    Kinds: boolean, number, integer, text, choice, pair.
    """
    if "enum" in node:
        return {"kind": "choice", "choices": [str(v) for v in node["enum"]]}

    if "oneOf" in node:
        choices: list[str] = []
        for branch in node["oneOf"]:
            if "const" in branch:
                choices.append(str(branch["const"]))
            elif branch.get("type") == "boolean":
                choices += ["true", "false"]
            elif "enum" in branch:
                choices += [str(v) for v in branch["enum"]]
            else:
                # A free-form branch alongside constants: fall back to text so
                # the value is never silently constrained to the constants.
                return {"kind": "text"}
        return {"kind": "choice", "choices": choices}

    t = node.get("type")
    if t == "boolean":
        return {"kind": "choice", "choices": ["true", "false"]}
    if t == "array":
        return {"kind": "pair"}
    if t in ("number", "integer"):
        return {"kind": t}
    return {"kind": "text", "pattern": node.get("pattern")}


def _top_fields(annotation: dict, schema: dict) -> list[dict]:
    """The annotation's own scalar properties, in schema order.

    Everything except `validation` and `i18n`, which the form draws as their
    own sections. Deriving the list rather than hard-coding component/group/
    references is what lets the Realtime schema add `origin` and have it
    appear in the form with no front-end change.
    """
    out = []
    for name, node in annotation["properties"].items():
        if name in ("validation", "i18n"):
            continue
        resolved = _deref(node, schema)
        out.append({
            "name": name,
            **_kind(resolved),
            "required": name in annotation["required"],
            "doc": node.get("description", ""),
        })
    return out


def _conditionals(annotation: dict) -> list[dict]:
    """`if/then` clauses read as "when <field> is <value>, require <these>".

    The schema expresses them as JSON Schema conditionals; the form needs them
    as a rule it can evaluate while someone types.
    """
    out = []
    for clause in annotation.get("allOf", []):
        properties = clause.get("if", {}).get("properties", {})
        required = clause.get("then", {}).get("required", [])
        for field, test in properties.items():
            if "const" in test and required:
                out.append({"field": field, "value": test["const"], "require": required})
    return out


def _ref_fields(annotation: dict, validation: dict, pattern: str) -> dict[str, list[str]]:
    """Which inputs hold a '<file>.<field>' reference, so the form can check them.

    Matched by pattern rather than by name: any rule that constrains its value
    to the reference shape is one the form should check the shape of.
    """
    def matches(node: dict) -> bool:
        return _scalar_branch(node).get("pattern") == pattern

    return {
        "annotation": [n for n, node in annotation["properties"].items()
                       if n not in ("validation", "i18n") and matches(node)],
        "validation": [n for n, node in validation.items() if matches(node)],
    }


def build(schema: dict) -> dict:
    defs = schema["definitions"]
    annotation = defs["annotation"]
    validation = defs["validation"]["properties"]

    rules = []
    for name, node in validation.items():
        if name == "bounding_box":
            rules.append(
                {
                    "name": name,
                    "kind": "region",
                    "severity": True,
                    "doc": node.get("description", ""),
                }
            )
            continue
        resolved = _scalar_branch(node)
        rules.append(
            {
                "name": name,
                **_kind(resolved),
                "severity": _accepts_severity(node),
                "doc": node.get("description", ""),
            }
        )

    i18n_entry = defs["i18nEntry"]
    i18n = annotation["properties"]["i18n"]
    ref_pattern = annotation["properties"]["references"]["pattern"]

    return {
        "topFields": _top_fields(annotation, schema),
        "conditionals": _conditionals(annotation),
        "annotationRequired": annotation["required"],
        "langs": list(i18n["properties"].keys()),
        "langsRequired": i18n["required"],
        "i18nFields": [
            {"name": k, "required": k in i18n_entry["required"]}
            for k in i18n_entry["properties"]
        ],
        "keyPattern": schema["properties"]["fields"]["propertyNames"]["pattern"],
        "refPattern": ref_pattern,
        "refFields": _ref_fields(annotation, validation, ref_pattern),
        "rules": rules,
        "ruleDependencies": defs["validation"].get("dependencies", {}),
        "severities": defs["severityWrapper"]["properties"]["severity"]["enum"],
    }


def load(path: Path) -> dict:
    return build(json.loads(path.read_text(encoding="utf-8")))


if __name__ == "__main__":
    here = Path(__file__).resolve().parents[2]
    print(json.dumps(load(here / "serializers/schedule/schedule.ui.schema.json"), indent=2))
