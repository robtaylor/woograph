"""JSON-LD utilities for entity ID generation and type mapping."""

import re
import unicodedata


# Map spaCy NER labels to schema.org types
_SPACY_TO_SCHEMA: dict[str, str] = {
    "PERSON": "Person",
    "ORG": "Organization",
    "GPE": "Place",
    "LOC": "Place",
    "FAC": "Place",
    "DATE": "Date",
    "EVENT": "Event",
    "WORK_OF_ART": "CreativeWork",
}

# Map spaCy NER labels to ID prefixes (lowercase schema type)
_SPACY_TO_PREFIX: dict[str, str] = {
    "PERSON": "person",
    "ORG": "organization",
    "GPE": "place",
    "LOC": "place",
    "FAC": "place",
    "DATE": "date",
    "EVENT": "event",
    "WORK_OF_ART": "creativework",
}


def slugify(text: str) -> str:
    """Convert text to a URL-safe slug for entity IDs.

    Lowercases, replaces non-alphanumeric characters with hyphens,
    collapses multiple hyphens, and strips leading/trailing hyphens.
    """
    if not text or not text.strip():
        return ""
    # Normalize unicode
    text = unicodedata.normalize("NFKD", text)
    # Lowercase
    text = text.lower()
    # Replace non-alphanumeric with hyphens
    text = re.sub(r"[^a-z0-9]+", "-", text)
    # Strip leading/trailing hyphens
    text = text.strip("-")
    return text


def make_entity_id(entity_type: str, name: str) -> str:
    """Generate canonical entity ID like 'entity:person-chester-nimitz'."""
    prefix = _SPACY_TO_PREFIX.get(entity_type, entity_type.lower())
    slug = slugify(name)
    return f"entity:{prefix}-{slug}"


def schema_type_for_spacy_label(label: str) -> str:
    """Map spaCy NER label to schema.org type.

    Returns 'Thing' for unknown labels.
    """
    return _SPACY_TO_SCHEMA.get(label, "Thing")
