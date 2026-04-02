"""spaCy NER entity extraction pipeline."""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

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

# Patterns that indicate a reference/citation rather than a real entity
_REFERENCE_PATTERNS = [
    re.compile(r"^\d+[\s,]*\d*\s*[\^]"),       # "65, 72^Gildenberg"
    re.compile(r"^\[\d+\]"),                     # "[123]"
    re.compile(r"^p\.\s*\d+"),                   # "p. 42"
    re.compile(r"^\d+[-–]\d+$"),                 # "65-72" (page ranges)
    re.compile(r"^\(?\d{1,3}\)$"),               # "(42)" or "42"
    re.compile(r"\^"),                            # anything with a caret
    re.compile(r"^[A-Z]{1,3}$"),                 # "TX", "US", "NY" (state/country codes)
    re.compile(r"^\d+$"),                         # pure numbers
    re.compile(r"^https?://"),                    # URLs
    re.compile(r"[\\${}]"),                       # LaTeX markers: \psi, $x$, {lm}
    re.compile(r"\|.*\|"),                        # table fragments: |39|2|0.777|
    re.compile(r"^[\d\s.,;:()/\-–]+$"),          # purely numeric/punctuation strings
    re.compile(r"^(br|nbsp)>"),                   # HTML artifacts
    re.compile(r"^(Fig|Std|Dev|Int|Sec|Ref|Eq)\.?$", re.IGNORECASE),  # abbreviations
    re.compile(r"^(al|ed|eds|vol|nos?)\.?$", re.IGNORECASE),  # citation abbreviations
    re.compile(r"^(Table|Figure|Fig)\s", re.IGNORECASE),  # "Table 5", "Figure 3a"
    re.compile(r"^(many|several|some|few|various)\s", re.IGNORECASE),  # "many years", "several weeks"
    re.compile(r"^(late|early|mid)\s+(19|20)\d\d", re.IGNORECASE),  # "late 1995", "early 2000s"
    re.compile(r"century$", re.IGNORECASE),  # "21st century", "first century"
    re.compile(r"^\d+(st|nd|rd|th)\s", re.IGNORECASE),  # "21st century"
    re.compile(r"years?\s+ago", re.IGNORECASE),  # "some years ago"
]

# Noise entities loaded from config file (fallback to empty set)
_noise_entities: frozenset[str] | None = None


def _get_noise_entities(noise_file: Path | None = None) -> frozenset[str]:
    """Load noise entity terms from config file.

    Searches for graph/entities/noise-terms.txt relative to the repo root.
    Falls back to an empty set if not found.
    """
    global _noise_entities  # noqa: PLW0603
    if _noise_entities is not None:
        return _noise_entities

    if noise_file is None:
        # Walk up from this file to find repo root
        candidate = Path(__file__).resolve().parent.parent.parent.parent.parent
        noise_file = candidate / "graph" / "entities" / "noise-terms.txt"

    terms: set[str] = set()
    if noise_file.exists():
        for line in noise_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                terms.add(line.lower())
        logger.info("Loaded %d noise terms from %s", len(terms), noise_file)

    _noise_entities = frozenset(terms)
    return _noise_entities

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

        # Filter very short entities (<=3 chars)
        if len(name) <= 3:
            continue

        # Filter reference/citation patterns
        if any(p.search(name) for p in _REFERENCE_PATTERNS):
            continue

        # Filter known noise entities
        if name.lower() in _get_noise_entities():
            continue

        # Filter entities that are mostly non-alpha (OCR garbage)
        alpha_ratio = sum(c.isalpha() or c.isspace() for c in name) / max(len(name), 1)
        if alpha_ratio < 0.5:
            continue

        # Date filtering: only keep dates with actual years (4-digit numbers)
        if ent.label_ == "DATE":
            if not re.search(r"\b(1[5-9]\d{2}|20[0-2]\d)\b", name):
                continue
            # Normalize: strip surrounding text, keep just the date part
            date_match = re.search(
                r"((?:January|February|March|April|May|June|July|August|"
                r"September|October|November|December|Jan|Feb|Mar|Apr|"
                r"Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.?\s+\d{1,2},?\s+\d{4}"
                r"|\d{4}[-/]\d{1,2}[-/]\d{1,2}"
                r"|\d{1,2}\s+(?:January|February|March|April|May|June|July|August|"
                r"September|October|November|December)\s+\d{4}"
                r"|\b(?:19|20)\d{2}\b)", name
            )
            if date_match:
                name = date_match.group(0)

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
