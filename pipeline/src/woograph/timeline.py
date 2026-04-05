"""Generate timeline data from the knowledge graph.

Parses Date entities (unstructured text) into ISO date ranges, cross-references
Events and Places via relationships, and collects source metadata + thumbnails
into a single timeline.json for the site's Timeline view.
"""

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# Month name → number
_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4,
    "jun": 6, "jul": 7, "aug": 8, "sep": 9, "sept": 9,
    "oct": 10, "nov": 11, "dec": 12,
}


def _parse_date_text(text: str) -> dict | None:
    """Parse a free-text date string into structured date info.

    Returns dict with keys: iso_start, iso_end, precision, year
    or None if unparseable.
    """
    t = text.strip().lower()

    # Skip obvious non-dates (publisher names, citations)
    if len(t) < 3 or t.isalpha() and len(t.split()) == 1:
        return None

    # Pattern: "Month Day, Year" or "Day Month Year"
    m = re.match(
        r"(\w+)\s+(\d{1,2}),?\s+(\d{4})", t,
    )
    if m:
        month_str, day, year = m.group(1), int(m.group(2)), int(m.group(3))
        month = _MONTHS.get(month_str)
        if month and 1 <= day <= 31 and 1800 <= year <= 2100:
            iso = f"{year:04d}-{month:02d}-{day:02d}"
            return {"iso_start": iso, "iso_end": iso, "precision": "day", "year": year}

    # Pattern: "Day Month Year" (European format)
    m = re.match(r"(\d{1,2})\s+(\w+),?\s+(\d{4})", t)
    if m:
        day, month_str, year = int(m.group(1)), m.group(2), int(m.group(3))
        month = _MONTHS.get(month_str)
        if month and 1 <= day <= 31 and 1800 <= year <= 2100:
            iso = f"{year:04d}-{month:02d}-{day:02d}"
            return {"iso_start": iso, "iso_end": iso, "precision": "day", "year": year}

    # Pattern: "Month Year" or "Month, Year"
    m = re.match(r"(\w+),?\s+(\d{4})$", t)
    if m:
        month_str, year = m.group(1), int(m.group(2))
        month = _MONTHS.get(month_str)
        if month and 1800 <= year <= 2100:
            return {
                "iso_start": f"{year:04d}-{month:02d}",
                "iso_end": f"{year:04d}-{month:02d}",
                "precision": "month",
                "year": year,
            }

    # Pattern: "Month and Month Year" (e.g. "june and july 1994")
    m = re.match(r"(\w+)\s+and\s+(\w+),?\s+(\d{4})", t)
    if m:
        m1, m2, year = _MONTHS.get(m.group(1)), _MONTHS.get(m.group(2)), int(m.group(3))
        if m1 and m2 and 1800 <= year <= 2100:
            return {
                "iso_start": f"{year:04d}-{min(m1, m2):02d}",
                "iso_end": f"{year:04d}-{max(m1, m2):02d}",
                "precision": "month",
                "year": year,
            }

    # Pattern: bare year or "the year YYYY"
    m = re.search(r"\b(\d{4})\b", t)
    if m:
        year = int(m.group(1))
        if 1800 <= year <= 2100:
            # Check for range: "1976 to 1979", "between 1978 and 1993"
            m2 = re.search(r"(\d{4})\s*(?:to|and|[-–—])\s*(\d{4})", t)
            if m2:
                y1, y2 = int(m2.group(1)), int(m2.group(2))
                if 1800 <= y1 <= 2100 and 1800 <= y2 <= 2100:
                    return {
                        "iso_start": f"{min(y1, y2):04d}",
                        "iso_end": f"{max(y1, y2):04d}",
                        "precision": "range",
                        "year": min(y1, y2),
                    }

            # Check for decade: "the early 1860's", "the late 1920's"
            m_decade = re.search(r"(early|mid|late)?\s*(\d{4})(?:'?s)", t)
            if m_decade:
                qualifier, decade_year = m_decade.group(1), int(m_decade.group(2))
                base = (decade_year // 10) * 10
                if qualifier == "early":
                    return {"iso_start": f"{base}", "iso_end": f"{base + 3}", "precision": "decade", "year": base}
                elif qualifier == "late":
                    return {"iso_start": f"{base + 7}", "iso_end": f"{base + 9}", "precision": "decade", "year": base + 7}
                elif qualifier == "mid":
                    return {"iso_start": f"{base + 4}", "iso_end": f"{base + 6}", "precision": "decade", "year": base + 4}
                else:
                    return {"iso_start": f"{base}", "iso_end": f"{base + 9}", "precision": "decade", "year": base}

            # Check for season: "the spring of 1976"
            season_months = {
                "spring": (3, 5), "summer": (6, 8),
                "autumn": (9, 11), "fall": (9, 11), "winter": (12, 2),
            }
            for season, (sm, em) in season_months.items():
                if season in t:
                    return {
                        "iso_start": f"{year:04d}-{sm:02d}",
                        "iso_end": f"{year:04d}-{em:02d}",
                        "precision": "season",
                        "year": year,
                    }

            # Plain year
            return {"iso_start": f"{year:04d}", "iso_end": f"{year:04d}", "precision": "year", "year": year}

    return None


def _extract_year_from_slug(slug: str) -> int | None:
    """Extract a 4-digit year from a source slug like 'pear-1979-...'."""
    m = re.search(r"-(\d{4})-", slug)
    if m:
        year = int(m.group(1))
        if 1800 <= year <= 2100:
            return year
    # Try at end: "wittenberge-ufo-2013"
    m = re.search(r"-(\d{4})$", slug)
    if m:
        year = int(m.group(1))
        if 1800 <= year <= 2100:
            return year
    return None


def _find_thumbnail(source_dir: Path, site_source_dir: Path | None = None) -> str | None:
    """Find a thumbnail image for a source directory.

    Checks the raw sources dir first, then the site/data/sources/ dir
    (which has deployed media like best_frame.png from video processing).
    """
    for d in [source_dir, site_source_dir]:
        if d is None or not d.exists():
            continue
        best = d / "best_frame.png"
        if best.exists():
            return "best_frame.png"
        pngs = sorted(d.glob("*.png"))
        if pngs:
            return pngs[0].name
    return None


def generate_timeline(
    global_path: Path,
    sources_dir: Path,
    output_path: Path,
    site_sources_dir: Path | None = None,
) -> dict:
    """Generate timeline.json from global.jsonld and source metadata.

    Args:
        global_path: Path to global.jsonld
        sources_dir: Path to sources/ directory (raw source data)
        output_path: Where to write timeline.json
        site_sources_dir: Optional path to site/data/sources/ (deployed media).
            Checked for thumbnails when sources_dir doesn't have them.

    Returns the generated timeline data dict.
    """
    with open(global_path) as f:
        graph = json.load(f)

    entities = graph.get("entities", [])
    relationships = graph.get("relationships", [])

    # Index entities by ID
    entity_by_id: dict[str, dict] = {}
    for e in entities:
        eid = e.get("@id", "")
        if eid:
            entity_by_id[eid] = e

    # Index relationships: subject → [(predicate, object)]
    rels_by_subject: dict[str, list[tuple[str, str]]] = {}
    rels_by_object: dict[str, list[tuple[str, str]]] = {}
    for r in relationships:
        subj = r.get("subject", {})
        obj = r.get("object", {})
        subj_id = subj.get("@id", "") if isinstance(subj, dict) else str(subj)
        obj_id = obj.get("@id", "") if isinstance(obj, dict) else str(obj)
        pred = r.get("predicate", "")
        if subj_id and obj_id:
            rels_by_subject.setdefault(subj_id, []).append((pred, obj_id))
            rels_by_object.setdefault(obj_id, []).append((pred, subj_id))

    # Load source metadata from both raw sources/ and site/data/sources/
    source_meta: dict[str, dict] = {}
    meta_dirs: list[tuple[Path, Path | None]] = []

    # Raw source directories
    for meta_path in sorted(sources_dir.glob("*/metadata.json")):
        slug = meta_path.parent.name
        site_slug_dir = site_sources_dir / slug if site_sources_dir else None
        meta_dirs.append((meta_path, site_slug_dir))

    # Site source directories (may have video sources not in raw sources/)
    if site_sources_dir and site_sources_dir.exists():
        for meta_path in sorted(site_sources_dir.glob("*/metadata.json")):
            slug = meta_path.parent.name
            if slug not in {p.parent.name for p, _ in meta_dirs}:
                meta_dirs.append((meta_path, meta_path.parent))

    for meta_path, site_slug_dir in meta_dirs:
        try:
            meta = json.loads(meta_path.read_text())
            slug = meta.get("source_slug", meta_path.parent.name)
            source_meta[slug] = meta
            # Check for thumbnail (raw sources dir + deployed site dir)
            thumb = _find_thumbnail(meta_path.parent, site_slug_dir)
            if thumb:
                meta["_thumbnail"] = thumb
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to read %s: %s", meta_path, exc)

    items: list[dict] = []
    seen_ids: set[str] = set()

    # 1. Parse Date entities
    date_entities = [e for e in entities if e.get("@type") == "Date"]
    parsed_count = 0
    for de in date_entities:
        eid = de["@id"]
        name = de.get("name", "")
        parsed = _parse_date_text(name)
        if not parsed:
            logger.debug("Unparseable date: %r", name)
            continue

        parsed_count += 1
        mentioned_in = de.get("mentionedIn", [])
        source_ids = [
            (s if isinstance(s, str) else s.get("@id", ""))
            for s in mentioned_in
        ]

        # Find connected events and places via relationships
        connected_events: list[str] = []
        connected_places: list[str] = []
        for pred, subj_id in rels_by_object.get(eid, []):
            ent = entity_by_id.get(subj_id, {})
            etype = ent.get("@type", "")
            if etype == "Event":
                connected_events.append(subj_id)
            elif etype == "Place":
                connected_places.append(subj_id)
            # Also check if the subject has occurredAt a Place
            for p2, o2 in rels_by_subject.get(subj_id, []):
                if "occurredAt" in p2 or "locatedIn" in p2:
                    o2_ent = entity_by_id.get(o2, {})
                    if o2_ent.get("@type") == "Place" and o2 not in connected_places:
                        connected_places.append(o2)

        # Find thumbnail from first video source
        thumbnail = None
        source_type = None
        for sid in source_ids:
            slug = sid.replace("source:", "")
            meta = source_meta.get(slug)
            if meta:
                source_type = meta.get("type")
                if meta.get("_thumbnail"):
                    thumbnail = f"data/sources/{slug}/{meta['_thumbnail']}"
                    break

        # Build a display label: prefer event name > source title > date text
        display_label = name
        if connected_events:
            event_ent = entity_by_id.get(connected_events[0], {})
            event_name = event_ent.get("name", "")
            if event_name:
                display_label = event_name
        elif source_ids:
            first_slug = source_ids[0].replace("source:", "")
            first_meta = source_meta.get(first_slug)
            if first_meta and first_meta.get("title"):
                display_label = first_meta["title"]

        items.append({
            "id": eid,
            "type": "date",
            "label": name,
            "display_label": display_label,
            "source_type": source_type,
            "thumbnail": thumbnail,
            "sources": source_ids,
            "events": connected_events,
            "places": connected_places,
            **parsed,
        })
        seen_ids.add(eid)

    logger.info("Parsed %d/%d Date entities", parsed_count, len(date_entities))

    # 2. Source-level entries (each source gets a timeline entry)
    for slug, meta in source_meta.items():
        source_id = f"source:{slug}"
        if source_id in seen_ids:
            continue

        # Try to get a year from the slug
        year = _extract_year_from_slug(slug)
        date_added = meta.get("date_added", "")

        if not year and date_added:
            # Fall back to date_added year
            try:
                year = int(date_added[:4])
            except (ValueError, IndexError):
                pass

        if not year:
            logger.debug("No year for source: %s", slug)
            continue

        thumbnail = None
        if meta.get("_thumbnail"):
            thumbnail = f"data/sources/{slug}/{meta['_thumbnail']}"

        # Find places connected to this source via mentionedIn relationships
        connected_places: list[str] = []
        for ent in entities:
            if ent.get("@type") == "Place":
                mi = ent.get("mentionedIn", [])
                mi_ids = [(s if isinstance(s, str) else s.get("@id", "")) for s in mi]
                if source_id in mi_ids:
                    connected_places.append(ent["@id"])

        items.append({
            "id": source_id,
            "type": "source",
            "label": meta.get("title", slug),
            "iso_start": f"{year:04d}",
            "iso_end": f"{year:04d}",
            "precision": "year",
            "year": year,
            "source_type": meta.get("type"),
            "thumbnail": thumbnail,
            "sources": [source_id],
            "events": [],
            "places": connected_places,
            "date_added": date_added,
            "tags": meta.get("tags", []),
            "description": meta.get("description", ""),
        })
        seen_ids.add(source_id)

    # Sort by year, then by iso_start
    items.sort(key=lambda x: (x.get("year", 9999), x.get("iso_start", "")))

    years = [i["year"] for i in items if i.get("year")]
    timeline_data = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "items": items,
        "spans": {
            "min_year": min(years) if years else 0,
            "max_year": max(years) if years else 0,
            "total_items": len(items),
            "by_precision": {},
        },
    }

    # Count by precision
    for item in items:
        p = item.get("precision", "unknown")
        timeline_data["spans"]["by_precision"][p] = (
            timeline_data["spans"]["by_precision"].get(p, 0) + 1
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(timeline_data, indent=2) + "\n")
    logger.info("Generated timeline: %d items → %s", len(items), output_path)

    return timeline_data
