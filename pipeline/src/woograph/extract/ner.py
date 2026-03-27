"""spaCy NER entity extraction pipeline."""

import logging
import re
from dataclasses import dataclass, field

import spacy
from spacy.language import Language

from woograph.graph.jsonld import make_entity_id

logger = logging.getLogger(__name__)

# Entity types we care about
ENTITY_TYPES = frozenset(
    {"PERSON", "ORG", "GPE", "LOC", "DATE", "EVENT", "WORK_OF_ART", "FAC"}
)

# Context window size (characters on each side of a mention)
CONTEXT_WINDOW = 100

# Module-level model cache
_nlp: Language | None = None


def _get_nlp() -> Language:
    """Load and cache the spaCy model."""
    global _nlp  # noqa: PLW0603
    if _nlp is None:
        logger.info("Loading spaCy model en_core_web_sm")
        _nlp = spacy.load("en_core_web_sm")
    return _nlp


@dataclass
class Entity:
    """A named entity extracted from text."""

    name: str
    entity_type: str  # PERSON, ORG, GPE, LOC, DATE, EVENT, WORK_OF_ART, FAC
    canonical_id: str  # e.g. "entity:person-chester-nimitz"
    spans: list[tuple[int, int]] = field(default_factory=list)
    context_snippets: list[str] = field(default_factory=list)
    mention_count: int = 1


def _strip_markdown(text: str) -> str:
    """Remove markdown formatting from text while preserving character positions."""
    # Remove bold/italic markers
    text = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", text)
    # Remove underline markers
    text = re.sub(r"_{1,3}([^_]+)_{1,3}", r"\1", text)
    # Remove headings markers
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    # Remove link syntax [text](url) -> text
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    # Remove image syntax ![alt](url) -> alt
    text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", text)
    # Remove inline code backticks
    text = re.sub(r"`([^`]+)`", r"\1", text)
    return text


def _get_context_snippet(text: str, start: int, end: int) -> str:
    """Extract a context snippet around a span."""
    ctx_start = max(0, start - CONTEXT_WINDOW)
    ctx_end = min(len(text), end + CONTEXT_WINDOW)
    snippet = text[ctx_start:ctx_end].strip()
    if ctx_start > 0:
        snippet = "..." + snippet
    if ctx_end < len(text):
        snippet = snippet + "..."
    return snippet


def extract_entities(markdown_text: str, source_id: str) -> list[Entity]:
    """Run spaCy NER on markdown text.

    Loads en_core_web_sm model (cached at module level), strips markdown
    formatting before NER, extracts entities of supported types,
    deduplicates by name+type, generates canonical IDs, and collects
    context snippets.

    Args:
        markdown_text: The markdown text to extract entities from.
        source_id: Identifier for the source document.

    Returns:
        List of deduplicated Entity objects.
    """
    if not markdown_text.strip():
        return []

    clean_text = _strip_markdown(markdown_text)
    nlp = _get_nlp()
    doc = nlp(clean_text)

    # Collect raw entities, grouping by (normalized_name, entity_type)
    # Key: (name, type) -> accumulated data
    grouped: dict[tuple[str, str], dict] = {}

    for ent in doc.ents:
        if ent.label_ not in ENTITY_TYPES:
            continue

        name = ent.text.strip()

        # Filter very short entities (1 char)
        if len(name) <= 1:
            continue

        key = (name, ent.label_)
        if key not in grouped:
            grouped[key] = {
                "spans": [],
                "snippets": [],
                "count": 0,
            }
        grouped[key]["spans"].append((ent.start_char, ent.end_char))
        grouped[key]["snippets"].append(
            _get_context_snippet(clean_text, ent.start_char, ent.end_char)
        )
        grouped[key]["count"] += 1

    # Build Entity objects
    entities = []
    for (name, entity_type), data in grouped.items():
        canonical_id = make_entity_id(entity_type, name)
        entities.append(
            Entity(
                name=name,
                entity_type=entity_type,
                canonical_id=canonical_id,
                spans=data["spans"],
                context_snippets=data["snippets"],
                mention_count=data["count"],
            )
        )

    logger.info(
        "Extracted %d entities from source %s", len(entities), source_id
    )
    return entities
