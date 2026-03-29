"""LLM-based relationship extraction between entities."""

import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from woograph.extract.ner import Entity
from woograph.llm.client import LLMConfig, create_completion
from woograph.utils.cache import LLMCache

# Default concurrency - conservative to avoid rate limits
DEFAULT_CONCURRENCY = 3

logger = logging.getLogger(__name__)

PREDICATES = [
    "participated_in",
    "member_of",
    "located_in",
    "occurred_at",
    "created_by",
    "related_to",
    "preceded",
    "followed",
    "caused",
    "part_of",
    "commanded",
    "worked_for",
    "allied_with",
    "opposed",
    "authored",
    "founded",
    "born_in",
    "died_in",
]


@dataclass
class Relationship:
    """A relationship between two entities extracted by Claude."""

    subject: str  # canonical entity ID
    predicate: str  # relationship type from PREDICATES
    object: str  # canonical entity ID
    confidence: float
    extracted_by: str  # e.g. "deepseek:deepseek-chat"
    source_id: str


def chunk_text_with_entities(
    text: str,
    entities: list[Entity],
    max_chunk_tokens: int = 500,
) -> list[dict]:
    """Split text into chunks, each annotated with entities found in that chunk.

    Only returns chunks with 2+ entities (need at least 2 for a relationship).
    Approximates tokens as len(text) / 4.
    """
    max_chunk_chars = max_chunk_tokens * 4
    chunks: list[dict] = []

    # Split text into roughly equal chunks
    if len(text) <= max_chunk_chars:
        text_chunks = [text]
    else:
        text_chunks = []
        start = 0
        while start < len(text):
            end = min(start + max_chunk_chars, len(text))
            # Try to break on sentence boundary
            if end < len(text):
                last_period = text.rfind(".", start, end)
                if last_period > start + max_chunk_chars // 2:
                    end = last_period + 1
            text_chunks.append(text[start:end])
            start = end

    for chunk_text in text_chunks:
        # Find entities whose names appear in this chunk
        chunk_entities = []
        chunk_lower = chunk_text.lower()
        for entity in entities:
            if entity.name.lower() in chunk_lower:
                chunk_entities.append(entity)

        if len(chunk_entities) >= 2:
            chunks.append({"text": chunk_text, "entities": chunk_entities})

    return chunks


def _build_prompt(chunk: dict) -> str:
    """Build the extraction prompt for a chunk."""
    entity_lines = []
    for e in chunk["entities"]:
        entity_lines.append(f"- {e.entity_type}: {e.name}")
    entities_str = "\n".join(entity_lines)
    predicates_str = ", ".join(PREDICATES)

    return (
        f"Given these entities extracted from a document:\n"
        f"{entities_str}\n\n"
        f"And this text excerpt:\n"
        f'"{chunk["text"]}"\n\n'
        f"Extract relationships as a JSON array. Each relationship should have:\n"
        f'- "subject": entity name (must be one from the list above)\n'
        f'- "predicate": one of [{predicates_str}]\n'
        f'- "object": entity name (must be one from the list above)\n'
        f'- "confidence": float 0.0-1.0\n\n'
        f"Extract ONLY relationships that are explicitly stated in the text. "
        f"Do not infer or guess relationships.\n\n"
        f"Return ONLY a JSON array. If no relationships found, return []."
    )


def _parse_response(
    response_text: str,
    chunk_entities: list[Entity],
    source_id: str,
    extracted_by: str = "unknown",
) -> list[Relationship]:
    """Parse LLM JSON response into Relationship objects."""
    # Build name -> canonical_id mapping
    name_to_id: dict[str, str] = {}
    for e in chunk_entities:
        name_to_id[e.name] = e.canonical_id
        name_to_id[e.name.lower()] = e.canonical_id

    try:
        raw = json.loads(response_text)
    except json.JSONDecodeError:
        logger.warning("Failed to parse LLM response as JSON")
        return []

    if not isinstance(raw, list):
        logger.warning("LLM response is not a JSON array")
        return []

    relationships: list[Relationship] = []
    for item in raw:
        subject_name = item.get("subject", "")
        object_name = item.get("object", "")
        predicate = item.get("predicate", "")
        confidence = item.get("confidence", 0.0)

        # Validate predicate
        if predicate not in PREDICATES:
            logger.debug("Skipping unknown predicate: %s", predicate)
            continue

        # Map names to canonical IDs
        subject_id = name_to_id.get(subject_name) or name_to_id.get(
            subject_name.lower()
        )
        object_id = name_to_id.get(object_name) or name_to_id.get(
            object_name.lower()
        )

        if not subject_id or not object_id:
            logger.debug(
                "Skipping relationship with unknown entity: %s -> %s",
                subject_name,
                object_name,
            )
            continue

        relationships.append(
            Relationship(
                subject=subject_id,
                predicate=predicate,
                object=object_id,
                confidence=float(confidence),
                extracted_by=extracted_by,
                source_id=source_id,
            )
        )

    return relationships


def extract_relationships(
    chunks: list[dict],
    source_id: str,
    llm_config: LLMConfig | None = None,
    cache: LLMCache | None = None,
) -> list[Relationship]:
    """Send each chunk to an LLM to extract relationships.

    For each chunk:
    - Build prompt with entity list + text excerpt
    - Check cache first (by hash of chunk text + entity list)
    - Request JSON output with subject/predicate/object/confidence
    - Parse response, map entity names back to canonical IDs
    - Handle API errors gracefully (retry once, then skip chunk)
    """
    if llm_config is None:
        logger.warning("No LLM config provided, skipping relationship extraction")
        return []

    all_relationships: list[Relationship] = []
    provider_label = f"{llm_config.provider}:{llm_config.model}"
    concurrency = int(os.environ.get("WOOGRAPH_LLM_CONCURRENCY", DEFAULT_CONCURRENCY))

    # Separate cached vs uncached chunks
    uncached_chunks: list[dict] = []
    for chunk in chunks:
        entity_names = sorted(e.name for e in chunk["entities"])
        cache_key_parts = (chunk["text"], str(entity_names))

        if cache is not None:
            cached = cache.get(*cache_key_parts)
            if cached is not None:
                rels = _parse_response(
                    json.dumps(cached), chunk["entities"], source_id,
                    extracted_by=provider_label,
                )
                all_relationships.extend(rels)
                continue

        uncached_chunks.append(chunk)

    if not uncached_chunks:
        return all_relationships

    logger.info(
        "Processing %d chunks (%d cached) with concurrency=%d",
        len(uncached_chunks), len(chunks) - len(uncached_chunks), concurrency,
    )

    def _process_chunk(chunk: dict) -> list[Relationship]:
        prompt = _build_prompt(chunk)
        response_text = create_completion(llm_config, prompt, max_tokens=1024, json_mode=True)

        if response_text is None:
            return []

        # Cache the raw response
        try:
            parsed_json = json.loads(response_text)
            if cache is not None:
                cache.put(parsed_json, chunk["text"], str(sorted(e.name for e in chunk["entities"])))
        except json.JSONDecodeError:
            pass

        return _parse_response(
            response_text, chunk["entities"], source_id,
            extracted_by=provider_label,
        )

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = {executor.submit(_process_chunk, chunk): i for i, chunk in enumerate(uncached_chunks)}
        for future in as_completed(futures):
            try:
                rels = future.result()
                all_relationships.extend(rels)
            except Exception as exc:
                logger.warning("Chunk processing failed: %s", exc)

    return all_relationships
