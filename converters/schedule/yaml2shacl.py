"""Builds SHACL shapes for the GTFS Schedule ontology from the YAML sources
of truth.

For every GTFS file (class) a sh:NodeShape is generated with:
  - one sh:property shape per field, carrying the constraints of its field
    type (serializers/schedule/fieldtypes.yaml), sh:in for enum options and
    sh:minCount 1 when the field is Required;
  - one sh:or implication per record-scoped presence rule
    (the `rules` entries in schedule.yaml): sh:or( NOT condition, consequence );
  - sh:description annotations for dataset-scoped rules, which cannot be
    expressed in SHACL core (phase 2: SHACL-SPARQL).

Usage:
    uv run python converters/schedule/yaml2shacl.py
"""

import re
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader
from pyshacl import validate as shacl_validate
from rdflib import Graph

from yaml2ttl import class_name, ttl_escape, type_list

BASE_DIR = Path(__file__).resolve().parents[2]
TEMPLATE_DIR = BASE_DIR / "converters" / "schedule" / "templates"
YAML_PATH = BASE_DIR / "serializers" / "schedule" / "schedule.yaml"
FIELDTYPES_PATH = BASE_DIR / "serializers" / "schedule" / "fieldtypes.yaml"
OUTPUT_PATH = BASE_DIR / "ontologies" / "schedule" / "shapes.ttl"

IND = "    "


# ---------------
# Value rendering
# ---------------


def ttl_value(value) -> str:
    """Render a rule/option value as a Turtle literal (plain int or string)."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return f'"{ttl_escape(value)}"'


def ttl_in(values: list) -> str:
    return f"sh:in ( {' '.join(ttl_value(v) for v in values)} )"


def parse_option_value(raw: str):
    """Parse an enum option value: "0 or empty" / "0 (or empty)" -> 0,
    "1" -> 1, "agency" -> "agency"."""
    match = re.match(r"^\s*(-?\d+)", str(raw))
    if match:
        return int(match.group(1))
    return str(raw).strip()


def enum_values(field: dict) -> list:
    values = []
    for option in field.get("options", []):
        if "category" in option:
            values.extend(parse_option_value(v["value"]) for v in option["values"])
        else:
            values.append(parse_option_value(option["value"]))
    return values


# -------------------------
# Field type -> constraints
# -------------------------


def type_constraint_terms(type_name: str, type_map: dict, warnings: list) -> list:
    """SHACL constraint terms (predicate-object strings) for one field type."""
    spec = type_map.get(type_name)
    if spec is None:
        warnings.append(f"unknown field type: {type_name!r}")
        return []
    if "or" in spec:
        branches = [
            f"[ {' ; '.join(type_constraint_terms(t, type_map, warnings))} ]"
            for t in spec["or"]
        ]
        return [f"sh:or ( {' '.join(branches)} )"]
    terms = []
    if "nodeKind" in spec:
        terms.append(f"sh:nodeKind {spec['nodeKind']}")
    if "datatype" in spec:
        terms.append(f"sh:datatype {spec['datatype']}")
    if "pattern" in spec:
        terms.append(f'sh:pattern "{ttl_escape(spec["pattern"])}"')
    for key in ("minInclusive", "maxInclusive", "minExclusive", "maxExclusive"):
        if key in spec:
            terms.append(f"sh:{key} {spec[key]}")
    if "notEquals" in spec:
        terms.append(f"sh:not [ sh:hasValue {ttl_value(spec['notEquals'])} ]")
    return terms


def field_property_shape(field: dict, type_map: dict, warnings: list) -> str:
    """Render the sh:property shape of one field."""
    terms = [f"sh:path gtfs:{field['name']}", "sh:maxCount 1"]
    if field.get("presence") == "Required":
        terms.append("sh:minCount 1")

    types = type_list(field["type"])
    if len(types) == 1 and types[0] == "Enum":
        values = enum_values(field)
        if values:
            datatype = (
                "xsd:integer"
                if all(isinstance(v, int) for v in values)
                else "xsd:string"
            )
            terms.append(f"sh:datatype {datatype}")
            terms.append(ttl_in(values))
        else:
            warnings.append(f"enum without options: {field['name']}")
    elif len(types) == 1:
        terms.extend(type_constraint_terms(types[0], type_map, warnings))
    else:
        branches = [
            f"[ {' ; '.join(type_constraint_terms(t, type_map, warnings))} ]"
            for t in types
        ]
        terms.append(f"sh:or ( {' '.join(branches)} )")

    description = field.get("presence", "")
    conditions = field.get("conditions", [])
    if isinstance(conditions, str):
        conditions = [conditions]
    if conditions:
        description += ". " + " ".join(conditions)
    if description:
        terms.append(f'sh:description """{ttl_escape(description)}"""')

    body = f" ;\n{IND * 2}".join(terms)
    return f"{IND}# {field['name']} ({field.get('presence', '')})\n{IND}sh:property [\n{IND * 2}{body}\n{IND}]"


# ----------------------------
# Rules -> sh:or implications
# ----------------------------


def negated_condition(cond: dict, warnings: list) -> list:
    """SHACL branches equivalent to NOT condition (one branch per sub-condition
    of an `all` conjunction, per De Morgan)."""
    if "all" in cond:
        branches = []
        for sub in cond["all"]:
            branches.extend(negated_condition(sub, warnings))
        return branches

    field = cond.get("field")
    path = f"sh:path gtfs:{field}"
    if "equals" in cond or "in" in cond:
        values = cond["in"] if "in" in cond else [cond["equals"]]
        empty_counts = "empty_means" in cond and cond["empty_means"] in values
        terms = [path]
        if empty_counts:
            terms.append("sh:minCount 1")  # absence would satisfy the condition
        terms.append(f"sh:not [ {ttl_in(values)} ]")
        return [f"[ sh:property [ {' ; '.join(terms)} ] ]"]
    if cond.get("present"):
        return [f"[ sh:property [ {path} ; sh:maxCount 0 ] ]"]
    if cond.get("empty"):
        return [f"[ sh:property [ {path} ; sh:minCount 1 ] ]"]
    if "equals_field" in cond:
        return [f"[ sh:property [ {path} ; sh:disjoint gtfs:{cond['equals_field']} ] ]"]
    if "not_equals_field" in cond:
        return [f"[ sh:property [ {path} ; sh:equals gtfs:{cond['not_equals_field']} ] ]"]
    warnings.append(f"cannot negate condition: {cond}")
    return []


def rule_consequence(field_name: str, rule: dict, warnings: list) -> str | None:
    path = f"sh:path gtfs:{field_name}"
    then = rule["then"]
    if then == "required":
        return f"[ sh:property [ {path} ; sh:minCount 1 ] ]"
    if then == "forbidden":
        if "values" in rule:
            return f"[ sh:property [ {path} ; sh:not [ {ttl_in(rule['values'])} ] ] ]"
        if "except_values" in rule:
            return f"[ sh:property [ {path} ; {ttl_in(rule['except_values'])} ] ]"
        return f"[ sh:property [ {path} ; sh:maxCount 0 ] ]"
    if then in ("optional", "recommended"):
        return None  # no constraint; prose stays in sh:description
    warnings.append(f"unknown consequence: {then}")
    return None


def summarize(cond: dict) -> str:
    if "all" in cond:
        return " and ".join(summarize(c) for c in cond["all"])
    field = cond.get("field", "?")
    if "in" in cond:
        return f"{field} in {cond['in']}"
    if "equals" in cond:
        return f"{field} = {cond['equals']}"
    if cond.get("present"):
        return f"{field} is defined"
    if cond.get("empty"):
        return f"{field} is empty"
    if "equals_field" in cond:
        return f"{field} = {cond['equals_field']}"
    if "not_equals_field" in cond:
        return f"{field} != {cond['not_equals_field']}"
    return cond.get("note", "?")


def rule_clause(field_name: str, rule: dict, warnings: list) -> str | None:
    """Render one rule as an sh:or implication (or a dataset-scope note)."""
    when = rule["when"]
    summary = f"{field_name}: {rule['then']} when {summarize(when)}"

    if when.get("scope") == "dataset":
        note = when.get("note", "")
        text = ttl_escape(
            f"Dataset-scoped rule (not enforced in SHACL core, phase 2): "
            f"{field_name} {rule['then']} when: {note}"
        )
        return f'{IND}sh:description """{text}"""'

    consequence = rule_consequence(field_name, rule, warnings)
    if consequence is None:
        return None
    branches = negated_condition(when, warnings) + [consequence]
    body = f"\n{IND * 2}".join(branches)
    return f"{IND}# rule: {summary}\n{IND}sh:or (\n{IND * 2}{body}\n{IND})"


# -------------
# Build process
# -------------


def build_shapes(data: dict, type_map: dict, warnings: list) -> list:
    shapes = []
    for file in data["field_definitions"]["files"]:
        target = class_name(file["file"])
        clauses = []
        for field in file.get("fields", []):
            clauses.append(field_property_shape(field, type_map, warnings))
            for rule in field.get("rules", []):
                clause = rule_clause(field["name"], rule, warnings)
                if clause:
                    clauses.append(clause)
        shapes.append(
            {
                "file": file["file"],
                "name": f"{target}Shape",
                "target": target,
                "clauses": " ;\n\n".join(clauses),
            }
        )
    return shapes


def render(shapes: list) -> str:
    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
    return env.get_template("shapes.ttl.jinja").render(shapes=shapes)


def validate(path: Path) -> int:
    """Syntax-check and meta-validate the shapes graph with pySHACL."""
    shapes_graph = Graph()
    shapes_graph.parse(path, format="turtle")
    conforms, _, report_text = shacl_validate(
        Graph(), shacl_graph=shapes_graph, meta_shacl=True
    )
    if not conforms:
        raise ValueError(f"Shapes graph is not valid SHACL:\n{report_text}")
    return len(shapes_graph)


def main() -> None:
    with open(YAML_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    with open(FIELDTYPES_PATH, encoding="utf-8") as f:
        type_map = {t["name"]: t for t in yaml.safe_load(f)["types"]}

    warnings: list = []
    shapes = build_shapes(data, type_map, warnings)
    OUTPUT_PATH.write_text(render(shapes), encoding="utf-8")
    for warning in warnings:
        print(f"WARNING: {warning}")
    triples = validate(OUTPUT_PATH)
    print(
        f"Wrote {OUTPUT_PATH.relative_to(BASE_DIR)} "
        f"({len(shapes)} node shapes, {triples} triples)"
    )


if __name__ == "__main__":
    main()
