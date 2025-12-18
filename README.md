# GTFS Reference & Ontology

A comprehensive project for the [General Transit Feed Specification (GTFS)](https://gtfs.org/) that provides:

- **Structured YAML Reference**: Machine-readable GTFS specification with complete field definitions
- **JSON Schema Validation**: Schema for validating YAML reference structure
- **RDF/OWL Ontology**: Semantic representation of GTFS static schedule data, enabling graph-based analysis, validation, and querying of public transit data

## Features

### YAML Reference

- **Complete Specification**: Structured YAML representation of the GTFS Schedule Reference (revision 2025-10-28)
- **Document Conventions**: Term definitions, presence conditions, field types, field signs, and dataset attributes
- **Dataset Files**: Complete listing of all GTFS files with presence requirements and descriptions
- **Field Definitions**: Detailed field definitions for `agency.txt`, `stops.txt`, and more
- **JSON Schema**: Validation schema for the YAML structure with enum constraints

### Ontology

- **Complete GTFS Coverage**: Mappings for all standard GTFS `schedule.txt` tables including `agency`, `stops`, `routes`, `trips`, `stop_times`, Fares V2, and more
- **SHACL Validation**: Built-in SHACL shapes to enforce GTFS constraints, data types, and enumerations (e.g., `route_type`, `pickup_type`)
- **Multilingual Support**: Ontology labels and comments provided in multiple languages via an overlay pattern:
  - English (`en`)
  - Spanish (`es`)
  - Portuguese (`pt`)
- **Semantic Linking**: Uses Object Properties to strictly link entities (e.g., `gtfs:route` links a `Trip` to a `Route`), improving upon simple foreign key strings

## Project Structure

```
├── assets/             # Reference materials
│   └── schedule.md     # GTFS Schedule Reference (markdown)
├── docs/               # Generated HTML documentation (Ontospy)
├── ontology/           # Ontology source files
│   ├── schedule.ttl    # Core structure and SHACL shapes
│   └── i18n/           # Localization overlays
│       ├── en.ttl
│       ├── es.ttl
│       └── pt.ttl
├── serializers/        # Reference (YAML/JSON) and converters
│   ├── schedule.yaml         # GTFS Schedule Reference (YAML)
│   ├── schedule.schema.json  # JSON Schema for validation
│   ├── schedule.json         # JSON representation (generated)
│   └── yaml2json.py          # Converter script (YAML to JSON)
├── main.py             # Script to generate documentation
└── README.md
```

## Getting Started

### Prerequisites

- [Python 3.12+](https://www.python.org/) & [uv](https://github.com/astral-sh/uv) (for generating docs)

### Using the YAML/JSON Reference

The YAML/JSON reference provides a structured, machine-readable format of the GTFS Schedule specification:

```bash
# View the YAML reference
cat serializers/schedule.yaml

# Convert YAML ➜ JSON (overwrites serializers/schedule.json)
uv run ./serializers/yaml2json.py

# View the JSON output
cat serializers/schedule.json

# Validate against the JSON Schema (requires a JSON Schema validator)
# Example using ajv-cli:
npm install -g ajv-cli
ajv validate -s serializers/schedule.schema.json -d serializers/schedule.json
```

The reference includes:

- **Document Conventions**: RFC 2119 keywords, term definitions, presence conditions, field types
- **Dataset Files**: All 33 GTFS files with presence requirements
- **File Requirements**: CSV formatting rules and best practices
- **Field Definitions**: Complete field specifications for agency.txt, stops.txt, and more

### Generating Ontology Documentation

We use [Ontospy](https://github.com/lambdamusic/Ontospy) to generate static HTML documentation for the ontology.

1.  **Install dependencies and run**:

    ```bash
    uv run python main.py
    ```

2.  **View Docs**:
    Open `docs/index.html` in your web browser.

## Namespace

- **Prefix**: `gtfs`
- **URI**: `http://ontology.gtfs.org/reference#`

```turtle
@prefix gtfs: <http://ontology.gtfs.org/reference#> .
```

## Contributing

### Adding a New Language

1.  Create a new `.ttl` file in `ontology/i18n/` (e.g., `fr.ttl`)
2.  Add `rdfs:label` and `rdfs:comment` annotations for existing classes and properties using the new language tag (e.g., `@fr`)
3.  Register the new file in `main.py` to include it in documentation generation

### Modifying the Ontology

- Edit `ontology/schedule.ttl` to add classes, properties, or SHACL shapes
- Verify changes by regenerating documentation

### Updating the YAML/JSON Reference

- Edit `serializers/schedule.yaml` to add or modify field definitions
- Update `serializers/schedule.schema.json` if structural changes are made
- Regenerate the JSON with:

  ```bash
  uv run ./serializers/yaml2json.py
  ```

- Ensure consistency with the source markdown in `assets/schedule.md`

## Tasks

- [ ] Complete YAML reference specification
- [ ] Generate Markdown documentation from YAML source
- [ ] Validate RDF triples and SHACL shapes
- [ ] Create database models from ontology
- [ ] Create ORM mappings from YAML/JSON reference
- [ ] Enhance GTFS ontology documentation and outreach
