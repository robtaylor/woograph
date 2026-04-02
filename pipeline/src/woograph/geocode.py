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
    re.compile(r"^[a-z](?!he\s)"),  # starts lowercase, but allow "the X" prefix
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

    Returns list of dicts with 'id' and 'name' keys.
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
        if entity_id and name:
            places.append({"id": entity_id, "name": name})

    logger.info("Found %d Place entities in %s", len(places), global_jsonld_path)
    return places


def geocode_place(name: str, session: requests.Session) -> dict | None:
    """Call Nominatim for a single place name.

    Returns dict with lat, lng, display_name, osm_type, confidence, or None.
    """
    params = {
        "q": name,
        "format": "jsonv2",
        "limit": 3,
        "addressdetails": 1,
        "accept-language": "en",
    }
    try:
        resp = session.get(NOMINATIM_URL, params=params, timeout=10)
        resp.raise_for_status()
        results = resp.json()
    except requests.RequestException as e:
        logger.warning("Nominatim request failed for %r: %s", name, e)
        return None

    if not results:
        return None

    # Pick the result with the highest importance score
    best = max(results, key=lambda r: float(r.get("importance", 0)))

    return {
        "lat": float(best["lat"]),
        "lng": float(best["lon"]),
        "display_name": best.get("display_name", ""),
        "osm_type": best.get("type", best.get("osm_type", "")),
        "confidence": round(float(best.get("importance", 0.5)), 4),
    }


def geocode_all(
    places: list[dict],
    cache_dir: Path,
    delay: float = 1.1,
    force: bool = False,
    dry_run: bool = False,
) -> tuple[dict, list[dict]]:
    """Geocode all places. Returns (successes, failures).

    successes: dict mapping entity_id -> geocode result
    failures: list of dicts with id, name, reason
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

    for i, place in enumerate(to_geocode):
        entity_id = place["id"]
        name = place["name"]
        cache_file = cache_dir / (entity_id.replace(":", "_").replace("/", "_") + ".json")

        if not force and cache_file.exists():
            try:
                cached = json.loads(cache_file.read_text())
                if cached is None:
                    failures.append({"id": entity_id, "name": name, "reason": "no_results_cached"})
                else:
                    successes[entity_id] = {"name": name, **cached}
                continue
            except (json.JSONDecodeError, KeyError):
                pass  # re-geocode on corrupt cache

        if dry_run:
            logger.info("[dry-run] Would geocode: %r", name)
            continue

        logger.info("Geocoding [%d/%d]: %r", i + 1, len(to_geocode), name)
        result = geocode_place(name, session)

        # Cache result (None = no results)
        cache_file.write_text(json.dumps(result, indent=2))

        if result:
            successes[entity_id] = {"name": name, **result}
        else:
            failures.append({"id": entity_id, "name": name, "reason": "no_results"})

        # Respect Nominatim rate limit
        if i < len(to_geocode) - 1:
            time.sleep(delay)

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
