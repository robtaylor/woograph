"""Submission YAML validation against JSON Schema."""

import logging
from pathlib import Path

import jsonschema
import jsonschema.validators
import yaml

logger = logging.getLogger(__name__)


def validate_submission(yaml_path: Path, schema_path: Path) -> list[str]:
    """Validate a submission YAML file against the schema.

    Performs both JSON Schema validation and additional semantic checks
    (e.g., file exists for PDF type, URL present for url/video types).

    Args:
        yaml_path: Path to the submission YAML file.
        schema_path: Path to the JSON Schema YAML file.

    Returns:
        List of validation error messages. Empty list means valid.
    """
    errors: list[str] = []

    # Load the submission YAML
    try:
        with yaml_path.open() as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        return [f"Invalid YAML: {exc}"]
    except Exception as exc:
        return [f"Cannot read file: {exc}"]

    if data is None:
        return ["Empty YAML file"]

    # Load the schema
    try:
        with schema_path.open() as f:
            schema = yaml.safe_load(f)
    except Exception as exc:
        return [f"Cannot read schema: {exc}"]

    # JSON Schema validation
    # Support both Draft-07 and Draft 2020-12 schemas
    validator_cls = jsonschema.validators.validator_for(schema)
    validator = validator_cls(schema)
    for error in sorted(validator.iter_errors(data), key=lambda e: list(e.path)):
        path = ".".join(str(p) for p in error.absolute_path)
        if path:
            errors.append(f"{path}: {error.message}")
        else:
            errors.append(error.message)

    # If schema validation failed, skip semantic checks
    if errors:
        return errors

    # Semantic checks based on source type
    source = data.get("source", {})
    source_type = source.get("type", "")

    if source_type == "pdf":
        file_name = source.get("file")
        pdf_url = source.get("url")
        if not file_name and not pdf_url:
            errors.append("PDF type requires 'file' or 'url' field")
        elif file_name:
            # Check if the file exists relative to submissions/files/
            submissions_dir = yaml_path.parent
            pdf_path = submissions_dir / "files" / file_name
            if not pdf_path.exists():
                errors.append(
                    f"PDF file not found: {file_name} "
                    f"(expected at {pdf_path})"
                )

    elif source_type in ("url", "video"):
        url = source.get("url")
        if not url:
            errors.append(f"{source_type} type requires 'url' field")

    elif source_type == "account":
        # Check for companion .md file
        companion_md = yaml_path.with_suffix(".md")
        if not companion_md.exists():
            errors.append(
                f"Account type requires companion markdown file: "
                f"{companion_md.name}"
            )

    return errors
