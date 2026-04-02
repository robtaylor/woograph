"""WooGraph CLI entry point."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import click
import yaml
from dotenv import load_dotenv

from woograph.convert.account import convert_account
from woograph.convert.pdf import convert_pdf
from woograph.convert.web import convert_url
from woograph.extract.disambiguate import disambiguate_entities
from woograph.extract.ner import extract_entities
from woograph.extract.relationships import (
    chunk_text_with_entities,
    extract_relationships,
)
from woograph.graph.fragment import create_fragment
from woograph.graph.merge import generate_stats, merge_global_graph
from woograph.graph.registry import EntityRegistry
from woograph.llm import load_llm_config
from woograph.utils.cache import LLMCache
from woograph.utils.validate import validate_submission

logger = logging.getLogger(__name__)


def _default_repo_root() -> Path:
    """Return the default repo root (parent of pipeline/)."""
    return Path(__file__).resolve().parent.parent.parent.parent


@click.group()
@click.option(
    "--repo-root",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=None,
    help="Root of the woograph repository. Defaults to parent of pipeline/.",
)
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging.")
@click.pass_context
def main(ctx: click.Context, repo_root: Path | None, verbose: bool) -> None:
    """WooGraph - Collaborative knowledge graph builder."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )
    # Load .env from repo root
    resolved_root = repo_root or _default_repo_root()
    load_dotenv(resolved_root / ".env")

    ctx.ensure_object(dict)
    ctx.obj["repo_root"] = resolved_root


@main.command()
@click.argument(
    "submission_yaml",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.pass_context
def validate(ctx: click.Context, submission_yaml: Path) -> None:
    """Validate a submission YAML against the schema."""
    repo_root: Path = ctx.obj["repo_root"]
    schema_path = repo_root / "submissions" / "_schema.yaml"

    if not schema_path.exists():
        click.echo(f"Error: Schema file not found at {schema_path}", err=True)
        raise SystemExit(1)

    errors = validate_submission(submission_yaml, schema_path)
    if errors:
        click.echo(f"Validation failed for {submission_yaml.name}:")
        for error in errors:
            click.echo(f"  - {error}")
        raise SystemExit(1)
    else:
        click.echo(f"Validation passed: {submission_yaml.name}")


@main.command()
@click.argument(
    "submission_yaml",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.pass_context
def process(ctx: click.Context, submission_yaml: Path) -> None:
    """Process a submission: convert source to markdown and store in sources/."""
    repo_root: Path = ctx.obj["repo_root"]
    schema_path = repo_root / "submissions" / "_schema.yaml"

    # Validate first if schema exists
    if schema_path.exists():
        errors = validate_submission(submission_yaml, schema_path)
        if errors:
            click.echo(f"Validation failed for {submission_yaml.name}:")
            for error in errors:
                click.echo(f"  - {error}")
            raise SystemExit(1)

    # Load submission YAML
    with submission_yaml.open() as f:
        submission = yaml.safe_load(f)

    source = submission.get("source", {})
    source_type = source.get("type", "")
    title = source.get("title", "unknown")

    # Derive slug from the YAML filename (without extension)
    slug = submission_yaml.stem
    output_dir = repo_root / "sources" / slug
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Processing submission: %s (type=%s)", title, source_type)

    try:
        if source_type == "pdf":
            file_name = source.get("file", "")
            pdf_url = source.get("url", "")
            if pdf_url:
                # Download PDF from URL
                import urllib.request
                pdf_path = output_dir / (slug + ".pdf")
                logger.info("Downloading PDF: %s", pdf_url)
                urllib.request.urlretrieve(pdf_url, pdf_path)
            elif file_name:
                pdf_path = repo_root / "submissions" / "files" / file_name
            else:
                click.echo("Error: PDF requires either 'file' or 'url'", err=True)
                raise SystemExit(1)
            if not pdf_path.exists():
                click.echo(f"Error: PDF file not found: {pdf_path}", err=True)
                raise SystemExit(1)
            content_path = convert_pdf(pdf_path, output_dir)

        elif source_type == "url":
            url = source.get("url", "")
            if not url:
                click.echo("Error: No URL provided for url-type submission", err=True)
                raise SystemExit(1)
            content_path = convert_url(url, output_dir)

        elif source_type == "account":
            # Companion .md file should be alongside the YAML
            account_md = submission_yaml.with_suffix(".md")
            if not account_md.exists():
                click.echo(
                    f"Error: Companion markdown not found: {account_md}", err=True
                )
                raise SystemExit(1)
            content_path = convert_account(account_md, output_dir)

        elif source_type == "video":
            # Video processing is deferred; just store metadata
            click.echo("Video processing not yet implemented. Storing metadata only.")
            content_path = output_dir / "content.md"
            content_path.write_text(
                f"# {title}\n\nVideo source: {source.get('url', 'N/A')}\n\n"
                f"*Video transcription not yet implemented.*\n"
            )

        else:
            click.echo(f"Error: Unknown source type: {source_type}", err=True)
            raise SystemExit(1)

    except SystemExit:
        raise
    except Exception:
        logger.exception("Failed to process submission %s", submission_yaml.name)
        click.echo(f"Error: Processing failed for {submission_yaml.name}", err=True)
        raise SystemExit(1)

    # Write metadata.json alongside the content
    metadata = {
        "source_slug": slug,
        "title": title,
        "type": source_type,
        "author": source.get("author", ""),
        "date_added": source.get("date_added", ""),
        "tags": source.get("tags", []),
        "description": source.get("description", ""),
        "content_file": str(content_path.relative_to(output_dir)),
        "processed_at": datetime.now(timezone.utc).isoformat(),
    }
    metadata_path = output_dir / "metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n")

    # Run NER extraction on the converted markdown
    md_content = content_path.read_text()
    source_id = f"source:{slug}"
    entities = extract_entities(md_content, source_id)
    logger.info("Extracted %d entities from %s", len(entities), slug)

    # Disambiguate entities against the registry
    registry_path = repo_root / "graph" / "entities" / "registry.json"
    registry = EntityRegistry(registry_path)

    llm_config = load_llm_config()
    if llm_config:
        logger.info(
            "Using LLM provider: %s (model: %s)",
            llm_config.provider,
            llm_config.model,
        )
    else:
        logger.warning("No LLM API key found, skipping LLM-based extraction")

    entities = disambiguate_entities(
        entities, registry, source_context=title, llm_config=llm_config
    )
    registry.save()

    # Extract relationships (only if LLM config available)
    relationships = []
    if llm_config is not None:
        cache_dir = repo_root / "graph" / ".cache" / "llm"
        cache = LLMCache(cache_dir)
        chunks = chunk_text_with_entities(md_content, entities)
        relationships = extract_relationships(
            chunks, source_id, llm_config=llm_config, cache=cache
        )
        logger.info("Extracted %d relationships from %s", len(relationships), slug)

    # Generate and save JSON-LD fragment
    fragment = create_fragment(
        source_id, title, entities, relationships=relationships or None
    )
    fragments_dir = repo_root / "graph" / "fragments"
    fragments_dir.mkdir(parents=True, exist_ok=True)
    fragment_path = fragments_dir / f"{slug}.jsonld"
    fragment_path.write_text(json.dumps(fragment, indent=2) + "\n")

    click.echo(f"Processed: {slug}")
    click.echo(f"  Content: {content_path}")
    click.echo(f"  Metadata: {metadata_path}")
    click.echo(f"  Entities: {len(entities)}")
    click.echo(f"  Relationships: {len(relationships)}")
    click.echo(f"  Fragment: {fragment_path}")


@main.command()
@click.argument(
    "fragment_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
def report(fragment_path: Path) -> None:
    """Generate a markdown extraction report from a JSON-LD fragment file."""
    from collections import Counter

    with fragment_path.open() as f:
        fragment = json.load(f)

    source_name = fragment.get("name", fragment_path.stem)
    entities = fragment.get("entities", [])
    relationships = fragment.get("relationships", [])

    # Count entities by type (exclude woo:Source entries)
    type_counts: Counter[str] = Counter()
    entity_mentions: Counter[str] = Counter()
    for ent in entities:
        etype = ent.get("@type", "unknown")
        if etype == "woo:Source":
            continue
        type_counts[etype] += 1
        name = ent.get("name", "")
        if name:
            entity_mentions[name] += 1

    total_entities = sum(type_counts.values())
    total_relationships = len(
        [r for r in relationships if r.get("@type") == "woo:Relationship"]
    )

    # Build type summary string
    type_parts = [f"{count} {etype}" for etype, count in type_counts.most_common()]
    type_summary = ", ".join(type_parts) if type_parts else "none"

    # Top entities by mention count
    top_entities = entity_mentions.most_common(5)
    top_str = ", ".join(f"{name} ({count})" for name, count in top_entities)

    # Sample relationships (non-mentionedIn, highest confidence)
    sample_rels = sorted(
        [
            r
            for r in relationships
            if r.get("@type") == "woo:Relationship"
            and r.get("predicate", "") != "woo:mentionedIn"
        ],
        key=lambda r: r.get("confidence", 0),
        reverse=True,
    )[:3]

    # Low-confidence relationships
    low_conf = [
        r
        for r in relationships
        if r.get("@type") == "woo:Relationship"
        and r.get("confidence", 1.0) < 0.5
    ]

    lines: list[str] = []
    lines.append(f"### {source_name}")
    lines.append(f"- **Entities**: {total_entities} ({type_summary})")
    lines.append(f"- **Relationships**: {total_relationships}")
    if top_str:
        lines.append(f"- **Top entities**: {top_str}")
    if sample_rels:
        lines.append("- **Sample relationships**:")
        for rel in sample_rels:
            subj = (
                rel.get("subject", {})
                .get("@id", "?")
                .split(":")[-1]
                .replace("-", " ")
            )
            pred = rel.get("predicate", "?").split(":")[-1]
            obj = (
                rel.get("object", {})
                .get("@id", "?")
                .split(":")[-1]
                .replace("-", " ")
            )
            conf = rel.get("confidence", 0)
            lines.append(f"  - {subj} -> {pred} -> {obj} ({conf:.2f})")
    if low_conf:
        lines.append(
            f"- **Warning**: {len(low_conf)} low-confidence relationships (<0.5)"
        )

    click.echo("\n".join(lines))


@main.command()
@click.pass_context
def merge(ctx: click.Context) -> None:
    """Merge all graph fragments into global.jsonld."""
    repo_root: Path = ctx.obj["repo_root"]
    fragments_dir = repo_root / "graph" / "fragments"
    context_path = repo_root / "graph" / "context.jsonld"

    global_graph = merge_global_graph(fragments_dir, context_path)

    # Write global.jsonld
    global_path = repo_root / "graph" / "global.jsonld"
    global_path.parent.mkdir(parents=True, exist_ok=True)
    global_path.write_text(json.dumps(global_graph, indent=2) + "\n")

    # Generate and write stats
    stats = generate_stats(global_graph)
    stats_path = repo_root / "graph" / "stats.json"
    stats_path.write_text(json.dumps(stats, indent=2) + "\n")

    click.echo(
        f"Global graph: {stats['total_entities']} entities, "
        f"{stats['total_relationships']} relationships "
        f"from {stats['total_sources']} sources"
    )


@main.command()
@click.pass_context
def clean(ctx: click.Context) -> None:
    """Clean the global graph: deduplicate types, remove noise entities."""
    import re
    from collections import Counter

    repo_root: Path = ctx.obj["repo_root"]
    global_path = repo_root / "graph" / "global.jsonld"

    if not global_path.exists():
        click.echo("No global.jsonld found. Run 'woograph merge' first.")
        raise SystemExit(1)

    graph = json.loads(global_path.read_text())
    entities = graph.get("entities", [])
    relationships = graph.get("relationships", [])

    orig_entities = len(entities)
    orig_rels = len(relationships)

    # --- 1. Remove noise entities ---
    noise_patterns = [
        re.compile(r"[\\${}]"),                   # LaTeX
        re.compile(r"\|.*\|"),                     # table fragments
        re.compile(r"^[\d\s.,;:()/\-–]+$"),        # purely numeric
        re.compile(r"^(br|nbsp)>"),                # HTML artifacts
    ]

    def is_noise(entity: dict) -> bool:
        if entity.get("@type") == "woo:Source":
            return False
        name = entity.get("name", "")
        if len(name) <= 3:
            return True
        alpha_ratio = sum(c.isalpha() or c.isspace() for c in name) / max(len(name), 1)
        if alpha_ratio < 0.5:
            return True
        return any(p.search(name) for p in noise_patterns)

    noise_ids: set[str] = set()
    clean_entities: list[dict] = []
    for e in entities:
        if is_noise(e):
            noise_ids.add(e["@id"])
        else:
            clean_entities.append(e)

    # Remove relationships involving noise entities
    clean_rels: list[dict] = []
    for r in relationships:
        sid = r["subject"]["@id"] if isinstance(r["subject"], dict) else r["subject"]
        oid = r["object"]["@id"] if isinstance(r["object"], dict) else r["object"]
        if sid not in noise_ids and oid not in noise_ids:
            clean_rels.append(r)

    click.echo(f"Noise removal: {len(noise_ids)} entities, {orig_rels - len(clean_rels)} relationships removed")

    # --- 2. Type deduplication ---
    # Entities with same name but different types → keep the most common type
    name_type_counts: dict[str, Counter] = {}
    for e in clean_entities:
        if e.get("@type") == "woo:Source":
            continue
        name = e["name"]
        if name not in name_type_counts:
            name_type_counts[name] = Counter()
        name_type_counts[name][e["@type"]] += 1

    # Build mapping: for each name, pick the best type
    # Priority: Person > Organization > Place > Event > CreativeWork > Date > Thing
    type_priority = {"Person": 6, "Organization": 5, "Place": 4, "Event": 3, "CreativeWork": 2, "Date": 1, "Thing": 0}
    best_type: dict[str, str] = {}
    for name, counts in name_type_counts.items():
        if len(counts) > 1:
            # Pick by frequency, then by priority
            best = max(counts.keys(), key=lambda t: (counts[t], type_priority.get(t, 0)))
            best_type[name] = best

    # Deduplicate: merge same-name entities into one with best type
    seen_names: dict[str, dict] = {}
    deduped_entities: list[dict] = []
    merged_ids: dict[str, str] = {}  # old_id → canonical_id

    for e in clean_entities:
        if e.get("@type") == "woo:Source":
            deduped_entities.append(e)
            continue

        name = e["name"]
        if name in best_type:
            e["@type"] = best_type[name]

        if name in seen_names:
            # Merge mentionedIn
            existing = seen_names[name]
            existing_mentions = existing.get("mentionedIn", [])
            new_mentions = e.get("mentionedIn", [])
            if isinstance(existing_mentions, str):
                existing_mentions = [existing_mentions]
            if isinstance(new_mentions, str):
                new_mentions = [new_mentions]
            merged = list(set(existing_mentions + new_mentions))
            existing["mentionedIn"] = merged if len(merged) > 1 else merged[0] if merged else ""
            # Track ID mapping for relationship rewriting
            merged_ids[e["@id"]] = existing["@id"]
        else:
            seen_names[name] = e
            deduped_entities.append(e)

    # Rewrite relationship IDs for merged entities
    deduped_rels: list[dict] = []
    seen_rel_keys: set[tuple] = set()
    for r in clean_rels:
        sid = r["subject"]["@id"] if isinstance(r["subject"], dict) else r["subject"]
        oid = r["object"]["@id"] if isinstance(r["object"], dict) else r["object"]
        sid = merged_ids.get(sid, sid)
        oid = merged_ids.get(oid, oid)
        # Skip self-loops created by merging
        if sid == oid:
            continue
        pred = r.get("predicate", "")
        key = (sid, pred, oid)
        if key in seen_rel_keys:
            continue
        seen_rel_keys.add(key)
        r_copy = dict(r)
        r_copy["subject"] = {"@id": sid}
        r_copy["object"] = {"@id": oid}
        deduped_rels.append(r_copy)

    type_merges = len(merged_ids)
    click.echo(f"Type dedup: {type_merges} entities merged, {len(clean_rels) - len(deduped_rels)} duplicate relationships removed")

    # --- 3. Remove orphan entities (no visible edges after Source/mentionedIn filtering) ---
    source_entity_ids = {e["@id"] for e in deduped_entities if e.get("@type") == "woo:Source"}
    linked_ids: set[str] = set()
    for r in deduped_rels:
        pred = r.get("predicate", "")
        if pred == "woo:mentionedIn":
            continue
        sid = r["subject"]["@id"] if isinstance(r["subject"], dict) else r["subject"]
        oid = r["object"]["@id"] if isinstance(r["object"], dict) else r["object"]
        if sid in source_entity_ids or oid in source_entity_ids:
            continue
        linked_ids.add(sid)
        linked_ids.add(oid)

    orphan_ids: set[str] = set()
    final_entities: list[dict] = []
    for e in deduped_entities:
        if e.get("@type") == "woo:Source" or e["@id"] in linked_ids:
            final_entities.append(e)
        else:
            orphan_ids.add(e["@id"])

    final_rels = [
        r for r in deduped_rels
        if (r["subject"]["@id"] if isinstance(r["subject"], dict) else r["subject"]) not in orphan_ids
        and (r["object"]["@id"] if isinstance(r["object"], dict) else r["object"]) not in orphan_ids
    ]

    click.echo(f"Orphan removal: {len(orphan_ids)} disconnected entities removed")

    # --- Write cleaned graph ---
    graph["entities"] = final_entities
    graph["relationships"] = final_rels
    global_path.write_text(json.dumps(graph, indent=2) + "\n")

    # Update stats
    from woograph.graph.merge import generate_stats
    stats = generate_stats(graph)
    stats_path = repo_root / "graph" / "stats.json"
    stats_path.write_text(json.dumps(stats, indent=2) + "\n")

    click.echo(
        f"Cleaned graph: {stats['total_entities']} entities "
        f"(was {orig_entities}), "
        f"{stats['total_relationships']} relationships "
        f"(was {orig_rels})"
    )


@main.command(name="llm-clean")
@click.option("--batch-size", default=50, help="Entities per LLM call")
@click.option("--dry-run", is_flag=True, help="Show what would be removed without modifying")
@click.pass_context
def llm_clean(ctx: click.Context, batch_size: int, dry_run: bool) -> None:
    """Use LLM to identify and remove noise entities from the global graph."""
    import re
    from concurrent.futures import ThreadPoolExecutor, as_completed

    from woograph.llm.client import create_completion, load_llm_config

    repo_root: Path = ctx.obj["repo_root"]
    global_path = repo_root / "graph" / "global.jsonld"

    if not global_path.exists():
        click.echo("No global.jsonld found. Run 'woograph merge' first.")
        raise SystemExit(1)

    llm_config = load_llm_config()
    if not llm_config:
        click.echo("No LLM API key found. Set DEEPSEEK_API_KEY or similar.")
        raise SystemExit(1)

    graph = json.loads(global_path.read_text())
    entities = graph.get("entities", [])
    relationships = graph.get("relationships", [])

    # Find suspicious entities
    suspicious: list[dict] = []
    for e in entities:
        if e.get("@type") == "woo:Source":
            continue
        name = e.get("name", "")
        is_suspect = False
        # Short names
        if len(name) <= 5:
            is_suspect = True
        # Names ending in punctuation
        elif name[-1] in ".,;:!?)":
            is_suspect = True
        # Abbreviation-like: all caps, or initials with dots
        elif re.match(r"^[A-Z][A-Z.]+$", name):
            is_suspect = True
        # Contains digits mixed with letters (OCR artifacts)
        elif re.search(r"\d", name) and re.search(r"[a-zA-Z]", name) and len(name) < 15:
            is_suspect = True
        if is_suspect:
            suspicious.append(e)

    click.echo(f"Found {len(suspicious)} suspicious entities to check")

    if not suspicious:
        click.echo("Nothing to clean!")
        return

    # Send in batches to LLM
    noise_ids: set[str] = set()
    batches = [suspicious[i:i + batch_size] for i in range(0, len(suspicious), batch_size)]

    def classify_batch(batch: list[dict]) -> set[str]:
        entity_list = "\n".join(
            f"- {e['@type']}: {e['name']}" for e in batch
        )
        prompt = (
            "You are classifying named entities extracted from academic research papers "
            "about consciousness, parapsychology, physics, and related topics.\n\n"
            "For each entity below, classify it as KEEP (real entity) or NOISE "
            "(OCR artifact, abbreviation, citation fragment, table data, or nonsense).\n\n"
            "Entities:\n"
            f"{entity_list}\n\n"
            "Return a JSON object with entity names as keys and \"KEEP\" or \"NOISE\" as values. "
            "Examples of NOISE: random abbreviations, partial words, citation fragments, "
            "degree abbreviations (Ph.D., M.A.), single letters, journal volume numbers.\n"
            "Examples of KEEP: person names, place names, organization names, real events, "
            "real publications, scientific concepts."
        )
        response = create_completion(llm_config, prompt, max_tokens=4096, json_mode=True)
        if not response:
            return set()
        try:
            result = json.loads(response)
            return {
                e["@id"] for e in batch
                if result.get(e["name"], "KEEP") == "NOISE"
            }
        except (json.JSONDecodeError, KeyError):
            return set()

    click.echo(f"Sending {len(batches)} batches to {llm_config.provider}:{llm_config.model}...")

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(classify_batch, batch): i for i, batch in enumerate(batches)}
        for future in as_completed(futures):
            batch_idx = futures[future]
            try:
                batch_noise = future.result()
                noise_ids.update(batch_noise)
                click.echo(f"  Batch {batch_idx + 1}/{len(batches)}: {len(batch_noise)} noise entities")
            except Exception as exc:
                click.echo(f"  Batch {batch_idx + 1}/{len(batches)}: failed ({exc})")

    click.echo(f"\nLLM identified {len(noise_ids)} noise entities")

    if dry_run:
        for e in entities:
            if e["@id"] in noise_ids:
                click.echo(f"  REMOVE: {e['@type']:15} {e['name']}")
        return

    # Remove noise entities and their relationships
    clean_entities = [e for e in entities if e["@id"] not in noise_ids]
    clean_rels = [
        r for r in relationships
        if (r["subject"]["@id"] if isinstance(r["subject"], dict) else r["subject"]) not in noise_ids
        and (r["object"]["@id"] if isinstance(r["object"], dict) else r["object"]) not in noise_ids
    ]

    graph["entities"] = clean_entities
    graph["relationships"] = clean_rels
    global_path.write_text(json.dumps(graph, indent=2) + "\n")

    from woograph.graph.merge import generate_stats
    stats = generate_stats(graph)
    stats_path = repo_root / "graph" / "stats.json"
    stats_path.write_text(json.dumps(stats, indent=2) + "\n")

    click.echo(
        f"LLM-cleaned graph: {stats['total_entities']} entities "
        f"(removed {len(noise_ids)}), "
        f"{stats['total_relationships']} relationships"
    )
