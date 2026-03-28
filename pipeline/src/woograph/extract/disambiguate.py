"""Entity disambiguation against the entity registry."""

import logging

import anthropic

from woograph.extract.ner import Entity
from woograph.graph.registry import EntityRegistry

logger = logging.getLogger(__name__)


def disambiguate_entities(
    new_entities: list[Entity],
    registry: EntityRegistry,
    source_context: str = "",
    client: anthropic.Anthropic | None = None,
) -> list[Entity]:
    """Disambiguate entities against the registry.

    For each entity:
    1. Exact match on canonical_id or name -> use registry entry
    2. Fuzzy match (check if name is alias of existing entity) -> ask Claude to confirm
    3. No match -> create new registry entry

    Returns entities with updated canonical_ids (may merge duplicates).
    """
    result: list[Entity] = []

    for entity in new_entities:
        # 1. Exact match by canonical_id
        existing = registry.lookup(entity.canonical_id)
        if existing is not None:
            result.append(entity)
            continue

        # 2. Exact match by name or alias
        by_name = registry.lookup_by_name(entity.name, entity.entity_type)
        if by_name is not None:
            # Find the canonical_id for this entry
            canonical_id = _find_canonical_id(registry, by_name)
            if canonical_id:
                entity.canonical_id = canonical_id
                result.append(entity)
                continue

        # 3. Fuzzy match - ask Claude to confirm if available
        fuzzy_matches = registry.find_fuzzy_matches(
            entity.name, entity.entity_type, threshold=0.7
        )

        if fuzzy_matches and client is not None:
            best_match = fuzzy_matches[0]
            is_same = _ask_claude_disambiguation(
                client,
                entity.name,
                best_match["name"],
                best_match.get("canonical_id", ""),
                source_context,
            )
            if is_same:
                entity.canonical_id = best_match["canonical_id"]
                # Add as alias
                registry.add_alias(best_match["canonical_id"], entity.name)
                result.append(entity)
                continue

        # 4. No match - create new registry entry
        registry.add_entity(
            entity.canonical_id,
            entity.name,
            entity.entity_type,
        )
        result.append(entity)

    return result


def _find_canonical_id(registry: EntityRegistry, entry: dict) -> str | None:
    """Find the canonical_id for a registry entry dict."""
    for cid, e in registry.data["entities"].items():
        if e is entry:
            return cid
    return None


def _ask_claude_disambiguation(
    client: anthropic.Anthropic,
    new_name: str,
    existing_name: str,
    existing_id: str,
    context: str,
) -> bool:
    """Ask Claude whether two entity names refer to the same entity."""
    prompt = (
        f"Is '{new_name}' in the context '{context}' the same entity as "
        f"'{existing_name}' ({existing_id})? "
        f"Answer only Yes or No."
    )
    try:
        response = client.messages.create(
            model="claude-3-5-haiku-latest",
            max_tokens=10,
            messages=[{"role": "user", "content": prompt}],
        )
        text_blocks = [b for b in response.content if hasattr(b, "text")]
        if not text_blocks:
            return False
        text: str = text_blocks[0].text  # type: ignore[union-attr]
        answer = text.strip().lower()
        return answer.startswith("yes")
    except Exception:
        logger.warning("Claude disambiguation call failed, treating as no match")
        return False
