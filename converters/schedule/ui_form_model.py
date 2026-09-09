#!/usr/bin/env python3
"""Derive the editor's form model from schedule.ui.schema.json.

The browser form is generated from this model rather than from a hand-written
list of inputs, so the schema stays the single source of truth for the
annotation vocabulary: adding a component to the enum, or a rule to
`validation`, makes it appear in the editor without touching the front-end.

Only the shape of each input is derived here. Full JSON Schema validation is
still run by ui_coverage.py in CI, which is the actual gate.
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


def build(schema: dict) -> dict:
    defs = schema["definitions"]
    annotation = defs["annotation"]["properties"]
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

    # component -> extra properties the schema conditionally requires
    requires: dict[str, list[str]] = {}
    for clause in defs["annotation"].get("allOf", []):
        const = (
            clause.get("if", {}).get("properties", {}).get("component", {}).get("const")
        )
        if const:
            requires[const] = clause.get("then", {}).get("required", [])

    i18n_entry = defs["i18nEntry"]

    return {
        "components": annotation["component"]["enum"],
        "componentRequires": requires,
        "annotationRequired": defs["annotation"]["required"],
        "langs": list(annotation["i18n"]["properties"].keys()),
        "langsRequired": annotation["i18n"]["required"],
        "i18nFields": [
            {"name": k, "required": k in i18n_entry["required"]}
            for k in i18n_entry["properties"]
        ],
        "keyPattern": schema["properties"]["fields"]["propertyNames"]["pattern"],
        "refPattern": annotation["references"]["pattern"],
        "rules": rules,
        "ruleDependencies": defs["validation"].get("dependencies", {}),
        "severities": defs["severityWrapper"]["properties"]["severity"]["enum"],
    }


def load(path: Path) -> dict:
    return build(json.loads(path.read_text(encoding="utf-8")))


if __name__ == "__main__":
    here = Path(__file__).resolve().parents[2]
    print(json.dumps(load(here / "serializers/schedule/schedule.ui.schema.json"), indent=2))
