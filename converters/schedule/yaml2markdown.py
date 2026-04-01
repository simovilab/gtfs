"""Convert GTFS YAML specification to Markdown documentation using Jinja2 templates."""

import yaml
from jinja2 import Environment, FileSystemLoader
from pathlib import Path
from datetime import datetime


def format_date(date_string):
    """Convert YYYY-MM-DD date string to 'Month DD, YYYY' format."""
    date_obj = datetime.strptime(date_string, "%Y-%m-%d")
    return date_obj.strftime("%B %d, %Y")


def generate_schedule_markdown():
    """Generate schedule.md from YAML data and Jinja2 template."""

    # Define paths
    base_dir = Path(__file__).parent.parent
    yaml_path = base_dir / "serializers" / "schedule.yaml"
    template_dir = base_dir / "converters" / "templates"
    output_path = base_dir / "documentation" / "schedule.md"

    # Load YAML data
    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    # Set up Jinja2 environment
    env = Environment(loader=FileSystemLoader(template_dir))
    env.filters["format_date"] = format_date
    template = env.get_template("schedule.md.jinja")

    # Render template with data
    rendered = template.render(**data)

    # Write output
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(rendered)

    print(f"Generated {output_path}")


if __name__ == "__main__":
    generate_schedule_markdown()
