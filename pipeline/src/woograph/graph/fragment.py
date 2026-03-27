"""JSON-LD fragment generation from extracted entities."""

from woograph.extract.ner import Entity
from woograph.graph.jsonld import schema_type_for_spacy_label


def create_fragment(
    source_id: str,
    source_title: str,
    entities: list[Entity],
    context_path: str = "../context.jsonld",
) -> dict:
    """Generate a JSON-LD fragment for a source.

    Maps Entity objects to JSON-LD format matching the schema in
    graph/context.jsonld. Each entity gets @id, @type, name, aliases
    (empty for now), and mentionedIn. No relationships yet (Phase 3).

    Args:
        source_id: The source identifier (e.g. "source:nimitz-bio").
        source_title: Human-readable title for the source.
        entities: List of Entity objects from NER extraction.
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

    fragment = {
        "@context": context_path,
        "@id": source_id,
        "name": source_title,
        "entities": entity_nodes,
    }
    return fragment
