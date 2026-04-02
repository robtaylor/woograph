"""Geocode Place entities using OpenStreetMap Nominatim."""

import json
import logging
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

# Nominatim API endpoint
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "WooGraph/0.1 (https://github.com/robtaylor/woograph)"

# If the top-2 Nominatim candidates are within this importance delta, use LLM to pick
AMBIGUITY_THRESHOLD = 0.15

# Patterns for names that are almost certainly not real places
_NOISE_PATTERNS = [
    re.compile(r"[&|>{}<$\\]"),             # special/code chars
    re.compile(r"^\d+$"),                   # purely numeric
    re.compile(r"^[A-Z]{1,2}$"),           # single/double letter codes
    re.compile(r"^\W+$"),                   # only punctuation/whitespace
    re.compile(r"[,;]\s*$"),               # trailing punctuation
    re.compile(r"^\("),                     # starts with paren
    re.compile(r"\b(Table|Figure|Fig)\s", re.IGNORECASE),
    re.compile(r"^\d+(st|nd|rd|th)\s", re.IGNORECASE),
    re.compile(r"\[\["),                    # Wikipedia footnote refs [[25]]
    re.compile(r"\n"),                      # multiline OCR artifacts
    re.compile(r"\(\d+"),                   # citation-like: "(1958" etc.
    re.compile(r"^\s*(the\s+)?[A-Z][a-z]+-[A-Z][a-z]+\b"),  # physics names: Einstein-Podolski
    re.compile(r"\b(www\.|http|\.edu|\.com)\b", re.IGNORECASE),  # URLs
    re.compile(r"[;:()/].*[;:()/]"),       # multiple special chars (OCR garbage)
    re.compile(r"\s{2,}"),                  # multiple spaces (OCR spacing artifact)
    re.compile(r"^[a-z](?!he\s)"),         # starts lowercase (allow "the X" prefix)
    re.compile(r"\d.*[a-zA-Z].*\d"),       # digits-letters-digits mix (OCR)
]

# Common English words that spaCy sometimes tags as GPE/LOC but aren't places
_COMMON_NON_PLACES = frozenset({
    "alternatively", "bayesian", "logistic", "baseline",
    "random", "normal", "primary", "secondary", "general",
    "standard", "statistical", "experimental", "theoretical",
    "local", "remote", "global", "national", "international",
    "east", "west", "north", "south", "central",
    "early", "late", "mid", "modern", "ancient",
    "various", "several", "many", "few", "multiple",
    # Abstract concepts wrongly tagged as places
    "pharmacology", "consciousness", "space", "alchemy", "divinity",
    "healing", "psychotherapy", "anesthesia", "anomaly", "mass",
    "automatic", "reference", "perspective", "addenda", "calibrations",
    "checksum", "sigma", "consequence", "notwithstanding", "superficially",
    "strands", "ideas", "dialectica", "quanta",
})


def is_geocodable(name: str) -> bool:
    """Return True if the name is worth sending to Nominatim."""
    if not name or len(name) < 3:
        return False

    if name.lower() in _COMMON_NON_PLACES:
        return False

    for pattern in _NOISE_PATTERNS:
        if pattern.search(name):
            return False

    # Must have at least one alphabetic character
    if not any(c.isalpha() for c in name):
        return False

    return True


def load_place_entities(global_jsonld_path: Path) -> list[dict]:
    """Extract Place entities from global.jsonld.

    Returns list of dicts with 'id', 'name', and 'context_snippets' keys.
    """
    with global_jsonld_path.open() as f:
        graph = json.load(f)

    places = []
    for entity in graph.get("entities", []):
        etype = entity.get("@type", "")
        if etype not in ("Place", "GPE", "LOC", "FAC"):
            continue
        entity_id = entity.get("@id", "")
        name = entity.get("name", "")
        if not entity_id or not name:
            continue

        # Collect context snippets (up to 3, truncated)
        raw_snippets = entity.get("contextSnippets", [])
        snippets = [s[:200] for s in raw_snippets[:3] if isinstance(s, str)]

        places.append({"id": entity_id, "name": name, "context_snippets": snippets})

    logger.info("Found %d Place entities in %s", len(places), global_jsonld_path)
    return places


def geocode_place(name: str, session: requests.Session) -> tuple[dict | None, list[dict]]:
    """Call Nominatim for a single place name.

    Returns (best_result, all_candidates).
    best_result is the highest-importance candidate, or None if no results.
    all_candidates is the full list (up to 5) for disambiguation.
    """
    params = {
        "q": name,
        "format": "jsonv2",
        "limit": 5,
        "addressdetails": 1,
        "accept-language": "en",
    }
    try:
        resp = session.get(NOMINATIM_URL, params=params, timeout=10)
        resp.raise_for_status()
        results = resp.json()
    except requests.RequestException as e:
        logger.warning("Nominatim request failed for %r: %s", name, e)
        return None, []

    if not results:
        return None, []

    candidates = [
        {
            "lat": float(r["lat"]),
            "lng": float(r["lon"]),
            "display_name": r.get("display_name", ""),
            "osm_type": r.get("type", r.get("osm_type", "")),
            "confidence": round(float(r.get("importance", 0.5)), 4),
        }
        for r in results
    ]

    # Sort descending by importance
    candidates.sort(key=lambda c: c["confidence"], reverse=True)

    return candidates[0], candidates


def _is_ambiguous(candidates: list[dict]) -> bool:
    """Return True if top-2 results are too close to call by importance alone."""
    if len(candidates) < 2:
        return False
    delta = candidates[0]["confidence"] - candidates[1]["confidence"]
    return delta < AMBIGUITY_THRESHOLD


def disambiguate_with_llm(
    name: str,
    context_snippets: list[str],
    candidates: list[dict],
    llm_config,
) -> dict:
    """Use LLM to pick the correct candidate given context.

    Returns the chosen candidate dict.
    """
    from woograph.llm.client import create_completion

    candidate_lines = "\n".join(
        f"{i + 1}. {c['display_name']} (importance: {c['confidence']:.2f})"
        for i, c in enumerate(candidates[:5])
    )

    context_text = ""
    if context_snippets:
        joined = "\n---\n".join(context_snippets)
        context_text = f"\n\nContext from the source documents where this place is mentioned:\n{joined}"

    prompt = (
        f"A text about parapsychology and consciousness research mentions the place \"{name}\"."
        f"{context_text}\n\n"
        f"Nominatim found these possible matches:\n{candidate_lines}\n\n"
        f"Which number (1-{min(len(candidates), 5)}) best matches the place mentioned in the text? "
        f"Reply with just the number."
    )

    response = create_completion(llm_config, prompt, max_tokens=10)
    if response:
        match = re.search(r"\d", response.strip())
        if match:
            idx = int(match.group()) - 1
            if 0 <= idx < len(candidates):
                logger.info(
                    "LLM chose candidate %d for %r: %s",
                    idx + 1, name, candidates[idx]["display_name"]
                )
                return candidates[idx]

    # Fall back to highest importance
    return candidates[0]


def geocode_all(
    places: list[dict],
    cache_dir: Path,
    delay: float = 1.1,
    force: bool = False,
    dry_run: bool = False,
    llm_config=None,
) -> tuple[dict, list[dict]]:
    """Geocode all places. Returns (successes, failures).

    successes: dict mapping entity_id -> geocode result
    failures: list of dicts with id, name, reason

    When llm_config is provided, ambiguous results are automatically
    disambiguated using the LLM.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)

    successes: dict = {}
    failures: list[dict] = []

    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT

    geocodable = [(p, is_geocodable(p["name"])) for p in places]
    skipped_noise = sum(1 for _, ok in geocodable if not ok)
    to_geocode = [p for p, ok in geocodable if ok]

    logger.info(
        "Total places: %d | To geocode: %d | Skipped (noise): %d",
        len(places), len(to_geocode), skipped_noise,
    )

    # Track noise as failures
    for p, ok in geocodable:
        if not ok:
            failures.append({"id": p["id"], "name": p["name"], "reason": "noise_filtered"})

    disambiguated_count = 0

    for i, place in enumerate(to_geocode):
        entity_id = place["id"]
        name = place["name"]
        context_snippets = place.get("context_snippets", [])
        cache_file = cache_dir / (entity_id.replace(":", "_").replace("/", "_") + ".json")

        if not force and cache_file.exists():
            try:
                cached = json.loads(cache_file.read_text())
                if cached is None:
                    failures.append({"id": entity_id, "name": name, "reason": "no_results_cached"})
                else:
                    # Support both old format (flat dict) and new format (with method key)
                    raw = cached["result"] if isinstance(cached, dict) and "result" in cached else cached
                    if not isinstance(raw, dict):
                        failures.append({"id": entity_id, "name": name, "reason": "cache_corrupt"})
                        continue
                    successes[entity_id] = {"name": name, **raw}
                continue
            except (json.JSONDecodeError, KeyError):
                pass  # re-geocode on corrupt cache

        if dry_run:
            logger.info("[dry-run] Would geocode: %r", name)
            continue

        logger.info("Geocoding [%d/%d]: %r", i + 1, len(to_geocode), name)
        best, candidates = geocode_place(name, session)

        if not candidates:
            cache_file.write_text(json.dumps(None))
            failures.append({"id": entity_id, "name": name, "reason": "no_results"})
        else:
            method = "importance"
            chosen = best

            if llm_config and _is_ambiguous(candidates):
                logger.info(
                    "Ambiguous (%d candidates, delta=%.2f), using LLM for %r",
                    len(candidates),
                    candidates[0]["confidence"] - candidates[1]["confidence"],
                    name,
                )
                chosen = disambiguate_with_llm(name, context_snippets, candidates, llm_config)
                method = "llm"
                disambiguated_count += 1

            # Cache with metadata
            assert chosen is not None  # candidates is non-empty here
            cache_data = {"result": chosen, "method": method, "candidates_count": len(candidates)}
            cache_file.write_text(json.dumps(cache_data, indent=2))
            successes[entity_id] = {"name": name, **chosen}

        # Respect Nominatim rate limit
        if i < len(to_geocode) - 1:
            time.sleep(delay)

    if disambiguated_count:
        logger.info("LLM-disambiguated %d ambiguous places", disambiguated_count)

    return successes, failures


def write_geocoded_json(
    successes: dict,
    failures: list[dict],
    total: int,
    output_path: Path,
) -> None:
    """Write geocoded.json to site/data/."""
    output = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "places": successes,
        "failures": failures,
        "stats": {
            "total": total,
            "geocoded": len(successes),
            "failed": len(failures),
        },
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2, ensure_ascii=False))
    logger.info(
        "Wrote %s: %d geocoded, %d failed",
        output_path, len(successes), len(failures),
    )
