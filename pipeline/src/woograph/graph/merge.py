"""Global graph assembly - merge per-source JSON-LD fragments into a single graph."""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


def merge_global_graph(fragments_dir: Path, context_path: Path) -> dict:
    """Merge all fragment .jsonld files into a global graph.

    1. Load all fragment .jsonld files from fragments_dir
    2. Collect all entities by canonical @id (deduplicate)
       - For duplicate entities, merge mentionedIn lists
    3. Collect all relationships (deduplicate by subject+predicate+object)
       - For duplicate relationships, keep highest confidence
       - Merge source references
    4. Build the global graph dict with shared @context
    5. Return the global graph

    Args:
        fragments_dir: Directory containing per-source .jsonld fragment files.
        context_path: Path to the shared JSON-LD context file.

    Returns:
        A complete global graph dict with embedded @context, entities, and
        relationships.
    """
    # Load the shared context
    if context_path.exists():
        context = json.loads(context_path.read_text())
        # Extract the inner @context object if present
        if "@context" in context:
            context = context["@context"]
    else:
        context = {}

    # Collect fragments
    fragment_files: list[Path] = []
    if fragments_dir.exists():
        fragment_files = sorted(fragments_dir.glob("*.jsonld"))

    # Entities keyed by @id for deduplication
    entities_by_id: dict[str, dict] = {}
    # Relationships keyed by (subject, predicate, object) for deduplication
    relationships_by_key: dict[tuple[str, str, str], dict] = {}

    for fpath in fragment_files:
        logger.info("Loading fragment: %s", fpath.name)
        fragment = json.loads(fpath.read_text())
        source_id = fragment.get("@id", "")

        # Process entities
        for entity in fragment.get("entities", []):
            eid = entity["@id"]
            # Normalize mentionedIn to a list
            mentioned = entity.get("mentionedIn", [])
            if isinstance(mentioned, str):
                mentioned = [mentioned]

            if eid in entities_by_id:
                # Merge: combine mentionedIn lists
                existing = entities_by_id[eid]
                existing_mentioned = existing.get("mentionedIn", [])
                merged_mentioned = list(dict.fromkeys(existing_mentioned + mentioned))
                existing["mentionedIn"] = merged_mentioned
            else:
                # First occurrence - store with mentionedIn as list
                merged_entity = dict(entity)
                merged_entity["mentionedIn"] = list(mentioned)
                entities_by_id[eid] = merged_entity

        # Process relationships
        for rel in fragment.get("relationships", []):
            subject_id = rel["subject"]["@id"]
            predicate = rel["predicate"]
            object_id = rel["object"]["@id"]
            key = (subject_id, predicate, object_id)

            if key in relationships_by_key:
                existing_rel = relationships_by_key[key]
                # Keep highest confidence
                if rel.get("confidence", 0) > existing_rel.get("confidence", 0):
                    existing_rel["confidence"] = rel["confidence"]
                    existing_rel["extractedBy"] = rel.get("extractedBy", "")
                # Merge sources
                existing_sources = existing_rel.get("sources", [])
                if source_id and source_id not in existing_sources:
                    existing_sources.append(source_id)
                existing_rel["sources"] = existing_sources
            else:
                merged_rel = dict(rel)
                merged_rel["sources"] = [source_id] if source_id else []
                relationships_by_key[key] = merged_rel

    # Remove @context references from individual entities (they used fragment-local paths)
    for entity in entities_by_id.values():
        entity.pop("@context", None)

    return {
        "@context": context,
        "entities": list(entities_by_id.values()),
        "relationships": list(relationships_by_key.values()),
    }


def generate_stats(global_graph: dict) -> dict:
    """Generate graph statistics.

    Args:
        global_graph: The merged global graph dict.

    Returns:
        Dict with total_entities, total_relationships, total_sources,
        entities_by_type (counts per @type), and last_updated (ISO timestamp).
    """
    entities = global_graph.get("entities", [])
    relationships = global_graph.get("relationships", [])

    # Count unique sources from all mentionedIn lists
    all_sources: set[str] = set()
    for entity in entities:
        mentioned = entity.get("mentionedIn", [])
        if isinstance(mentioned, list):
            all_sources.update(mentioned)
        elif isinstance(mentioned, str):
            all_sources.add(mentioned)

    # Count entities by type
    entities_by_type: dict[str, int] = defaultdict(int)
    for entity in entities:
        etype = entity.get("@type", "Thing")
        entities_by_type[etype] += 1

    return {
        "total_entities": len(entities),
        "total_relationships": len(relationships),
        "total_sources": len(all_sources),
        "entities_by_type": dict(entities_by_type),
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }
