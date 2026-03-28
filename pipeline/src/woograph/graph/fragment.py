"""JSON-LD fragment generation from extracted entities and relationships."""

from __future__ import annotations

from typing import TYPE_CHECKING

from woograph.extract.ner import Entity
from woograph.graph.jsonld import schema_type_for_spacy_label

if TYPE_CHECKING:
    from woograph.extract.relationships import Relationship


def create_fragment(
    source_id: str,
    source_title: str,
    entities: list[Entity],
    relationships: list[Relationship] | None = None,
    context_path: str = "../context.jsonld",
) -> dict:
    """Generate a JSON-LD fragment for a source.

    Maps Entity objects to JSON-LD format matching the schema in
    graph/context.jsonld. Each entity gets @id, @type, name, aliases
    (empty for now), and mentionedIn. Relationships are included when
    provided.

    Args:
        source_id: The source identifier (e.g. "source:nimitz-bio").
        source_title: Human-readable title for the source.
        entities: List of Entity objects from NER extraction.
        relationships: Optional list of Relationship objects.
        context_path: Relative path to the shared JSON-LD context file.

    Returns:
        Complete JSON-LD fragment dict.
    """
    entity_nodes = []
    for entity in entities:
        node = {
            "@id": entity.canonical_id,
            "@type": schema_type_for_spacy_label(entity.entity_type),
            "name": entity.name,
            "aliases": [],
            "mentionedIn": source_id,
        }
        entity_nodes.append(node)

    fragment: dict = {
        "@context": context_path,
        "@id": source_id,
        "name": source_title,
        "entities": entity_nodes,
    }

    if relationships:
        rel_nodes = []
        for rel in relationships:
            rel_nodes.append({
                "@type": "woo:Relationship",
                "subject": {"@id": rel.subject},
                "predicate": f"woo:{_camel_case(rel.predicate)}",
                "object": {"@id": rel.object},
                "confidence": rel.confidence,
                "extractedBy": rel.extracted_by,
            })
        fragment["relationships"] = rel_nodes

    return fragment


def _camel_case(snake: str) -> str:
    """Convert snake_case predicate to camelCase for JSON-LD."""
    parts = snake.split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])
