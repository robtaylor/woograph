"""JSON-LD fragment generation from extracted entities and relationships."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from woograph.extract.ner import Entity
from woograph.graph.jsonld import make_entity_id, schema_type_for_spacy_label

if TYPE_CHECKING:
    from woograph.extract.relationships import Relationship

logger = logging.getLogger(__name__)


def _find_topic_entity(
    source_title: str, entities: list[Entity],
) -> Entity | None:
    """Find or identify the primary topic entity from the source title.

    Looks for an entity whose name closely matches the source title
    (after stripping common prefixes like "Wikipedia:").
    """
    # Strip common prefixes
    title = source_title
    for prefix in ("Wikipedia:", "Wikipedia -", "PDF:", "URL:"):
        if title.startswith(prefix):
            title = title[len(prefix):]
    title = title.strip()

    # Try exact match first
    title_lower = title.lower()
    for entity in entities:
        if entity.name.lower() == title_lower:
            return entity

    # Try substring match (title contains entity name or vice versa)
    best_match: Entity | None = None
    best_score = 0
    for entity in entities:
        name_lower = entity.name.lower()
        if name_lower in title_lower or title_lower in name_lower:
            score = len(entity.name)
            if score > best_score:
                best_score = score
                best_match = entity

    return best_match


def create_fragment(
    source_id: str,
    source_title: str,
    entities: list[Entity],
    relationships: list[Relationship] | None = None,
    context_path: str = "../context.jsonld",
) -> dict:
    """Generate a JSON-LD fragment for a source.

    Creates:
    - A source node (type woo:Source) for the source itself
    - Entity nodes for all extracted entities
    - mentioned_in relationships from each entity to the source
    - related_to relationships from orphan entities to the topic entity
    - LLM-extracted relationships (when provided)
    """
    # Source node
    source_node = {
        "@id": source_id,
        "@type": "woo:Source",
        "name": source_title,
    }

    # Entity nodes
    entity_nodes: list[dict] = [source_node]
    entity_ids: set[str] = set()
    for entity in entities:
        entity_ids.add(entity.canonical_id)
        node = {
            "@id": entity.canonical_id,
            "@type": schema_type_for_spacy_label(entity.entity_type),
            "name": entity.name,
            "aliases": [],
            "mentionedIn": source_id,
        }
        entity_nodes.append(node)

    # Build relationships
    rel_nodes: list[dict] = []

    # 1. mentioned_in: every entity → source
    for entity in entities:
        rel_nodes.append({
            "@type": "woo:Relationship",
            "subject": {"@id": entity.canonical_id},
            "predicate": "woo:mentionedIn",
            "object": {"@id": source_id},
            "confidence": 1.0,
            "extractedBy": "pipeline",
        })

    # 2. LLM-extracted relationships
    linked_entity_ids: set[str] = set()
    if relationships:
        for rel in relationships:
            rel_nodes.append({
                "@type": "woo:Relationship",
                "subject": {"@id": rel.subject},
                "predicate": f"woo:{_camel_case(rel.predicate)}",
                "object": {"@id": rel.object},
                "confidence": rel.confidence,
                "extractedBy": rel.extracted_by,
            })
            linked_entity_ids.add(rel.subject)
            linked_entity_ids.add(rel.object)

    # 3. related_to: orphan entities → topic entity
    #    If no topic entity found, create one from the source title
    topic = _find_topic_entity(source_title, entities)
    if topic:
        target_id = topic.canonical_id
        logger.info("Topic entity found: %s (%s)", topic.name, target_id)
    else:
        # Create a synthetic topic entity from the title
        clean_title = source_title
        for prefix in ("PEAR:", "JFK:", "PDF:", "Wikipedia:"):
            if clean_title.startswith(prefix):
                clean_title = clean_title[len(prefix):].strip()
        # Strip leading years
        clean_title = re.sub(r"^\d{4}[-\s]+", "", clean_title).strip()
        target_id = make_entity_id("EVENT", clean_title)
        entity_nodes.append({
            "@id": target_id,
            "@type": "Event",
            "name": clean_title,
            "aliases": [],
            "mentionedIn": source_id,
        })
        entity_ids.add(target_id)
        rel_nodes.append({
            "@type": "woo:Relationship",
            "subject": {"@id": target_id},
            "predicate": "woo:mentionedIn",
            "object": {"@id": source_id},
            "confidence": 1.0,
            "extractedBy": "pipeline",
        })
        logger.info("Created topic entity: %s (%s)", clean_title, target_id)

    for entity in entities:
        if entity.canonical_id == target_id:
            continue
        if entity.canonical_id not in linked_entity_ids:
            rel_nodes.append({
                "@type": "woo:Relationship",
                "subject": {"@id": entity.canonical_id},
                "predicate": "woo:relatedTo",
                "object": {"@id": target_id},
                "confidence": 0.3,
                "extractedBy": "pipeline",
            })

    fragment: dict = {
        "@context": context_path,
        "@id": source_id,
        "name": source_title,
        "entities": entity_nodes,
        "relationships": rel_nodes,
    }

    return fragment


def _camel_case(snake: str) -> str:
    """Convert snake_case predicate to camelCase for JSON-LD."""
    parts = snake.split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])
