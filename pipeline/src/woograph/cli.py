"""WooGraph CLI entry point."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import click
import yaml
from dotenv import load_dotenv

from woograph.convert.account import convert_account
from woograph.convert.index import discover_index
from woograph.convert.pdf import convert_pdf
from woograph.convert.web import convert_url
from woograph.convert.video import convert_video
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

R2_WORKER_URL = "https://woograph-upload.robtaylor.workers.dev"


def _upload_videos_to_r2(output_dir: Path) -> dict[str, str]:
    """Upload .mp4 files from output_dir to R2, return {stem: url} mapping."""
    import requests as _requests

    mp4_files = sorted(output_dir.glob("*.mp4"))
    if not mp4_files:
        return {}

    urls: dict[str, str] = {}
    for mp4 in mp4_files:
        try:
            with mp4.open("rb") as f:
                resp = _requests.post(
                    f"{R2_WORKER_URL}/upload?filename={mp4.name}",
                    data=f,
                    headers={"Content-Type": "video/mp4"},
                    timeout=120,
                )
            if resp.ok:
                data = resp.json()
                urls[mp4.stem] = data["url"]
                logger.info("Uploaded %s to R2: %s", mp4.name, data["url"])
            else:
                logger.warning("R2 upload failed for %s: HTTP %s", mp4.name, resp.status_code)
        except Exception:
            logger.warning("R2 upload failed for %s", mp4.name, exc_info=True)
    return urls


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
                # Download PDF from URL with browser headers
                import requests as _requests
                from woograph.convert.web import _BROWSER_HEADERS
                pdf_path = output_dir / (slug + ".pdf")
                logger.info("Downloading PDF: %s", pdf_url)
                resp = _requests.get(
                    pdf_url, headers=_BROWSER_HEADERS, timeout=60, allow_redirects=True
                )
                if not resp.ok:
                    archive_url = f"https://web.archive.org/web/{pdf_url}"
                    logger.warning(
                        "HTTP %s for PDF %s — trying Wayback Machine: %s",
                        resp.status_code, pdf_url, archive_url,
                    )
                    resp = _requests.get(
                        archive_url, headers=_BROWSER_HEADERS, timeout=60, allow_redirects=True
                    )
                    if not resp.ok:
                        raise RuntimeError(
                            f"HTTP {resp.status_code} downloading PDF {pdf_url} "
                            f"(Wayback Machine also failed)"
                        )
                pdf_path.write_bytes(resp.content)
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
            file_name = source.get("file", "")
            video_url = source.get("url", "")
            if video_url:
                import requests as _requests
                from woograph.convert.web import _BROWSER_HEADERS
                video_path = output_dir / (slug + Path(video_url).suffix or ".mp4")
                logger.info("Downloading video: %s", video_url)
                resp = _requests.get(
                    video_url, headers=_BROWSER_HEADERS, timeout=120,
                    allow_redirects=True, stream=True,
                )
                resp.raise_for_status()
                with video_path.open("wb") as vf:
                    for chunk in resp.iter_content(chunk_size=8192):
                        vf.write(chunk)
            elif file_name:
                video_path = repo_root / "submissions" / "files" / file_name
            else:
                click.echo("Error: Video requires either 'file' or 'url'", err=True)
                raise SystemExit(1)
            if not video_path.exists():
                click.echo(f"Error: Video file not found: {video_path}", err=True)
                raise SystemExit(1)
            video_opts = source.get("processing", {})
            convert_video(
                video_path,
                output_dir,
                scale=video_opts.get("scale", 2),
                max_frames=video_opts.get("max_frames", 0),
                frame_step=video_opts.get("frame_step", 1),
                padding_factor=video_opts.get("padding_factor", 2.0),
                psf_sigma=video_opts.get("psf_sigma", 1.5),
                deconv_iterations=video_opts.get("deconv_iterations", 15),
                save_crops=video_opts.get("save_crops", False),
            )
            content_path = output_dir / "content.md"
            # Merge video processing metadata into source metadata
            video_meta_path = output_dir / "metadata.json"
            if video_meta_path.exists():
                video_meta = json.loads(video_meta_path.read_text())
                source["video_metadata"] = {
                    k: v for k, v in video_meta.items()
                    if k not in ("shifts", "sharpness_weights", "video_path")
                }
            # Upload videos to R2 (too large for GitHub Pages)
            r2_urls = _upload_videos_to_r2(output_dir)
            if r2_urls:
                source.setdefault("video_metadata", {})["r2_urls"] = r2_urls
                logger.info("Uploaded %d videos to R2", len(r2_urls))

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
    metadata: dict = {
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
    if source_type == "video" and "video_metadata" in source:
        metadata["video_metadata"] = source["video_metadata"]
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


@main.command("discover-index")
@click.argument("submission_yaml", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--max-pages", default=5000, show_default=True, help="Maximum pages to discover.")
@click.option("--delay", default=1.0, show_default=True, help="Seconds between pagination requests.")
@click.pass_context
def discover_index_cmd(ctx: click.Context, submission_yaml: Path, max_pages: int, delay: float) -> None:
    """Crawl an index-type submission and write a JSON plan of discovered URLs.

    Writes graph/index-plans/{slug}.json with the list of pages found.
    """
    repo_root: Path = ctx.obj["repo_root"]

    with submission_yaml.open() as f:
        submission = yaml.safe_load(f)

    source = submission.get("source", {})
    source_type = source.get("type", "")
    if source_type != "index":
        click.echo(f"Error: submission type is '{source_type}', expected 'index'", err=True)
        raise SystemExit(1)

    url = source.get("url", "")
    if not url:
        click.echo("Error: no URL in submission", err=True)
        raise SystemExit(1)

    cap = source.get("max_pages", max_pages)
    slug = submission_yaml.stem
    title = source.get("title", slug)

    click.echo(f"Discovering index: {url} (cap={cap})")
    pages = discover_index(url, max_pages=cap, page_delay=delay)

    plan = {
        "slug": slug,
        "title": title,
        "index_url": url,
        "discovered_at": datetime.now(timezone.utc).isoformat(),
        "total": len(pages),
        "pages": [{"url": p.url, "title": p.title} for p in pages],
    }

    plans_dir = repo_root / "graph" / "index-plans"
    plans_dir.mkdir(parents=True, exist_ok=True)
    plan_path = plans_dir / f"{slug}.json"
    plan_path.write_text(json.dumps(plan, indent=2) + "\n")

    click.echo(f"Found {len(pages)} pages → {plan_path}")


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


@main.command("graph-preview")
@click.argument(
    "fragment_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.option("--max-nodes", default=25, show_default=True, help="Max nodes to render")
@click.option("--min-confidence", default=0.5, show_default=True, help="Min edge confidence")
def graph_preview(fragment_path: Path, max_nodes: int, min_confidence: float) -> None:
    """Generate a Mermaid graph diagram from a JSON-LD fragment file."""
    import re

    with fragment_path.open() as f:
        fragment = json.load(f)

    entities = fragment.get("entities", [])
    relationships = fragment.get("relationships", [])

    # Index entity names by @id
    id_to_name: dict[str, str] = {}
    id_to_type: dict[str, str] = {}
    for ent in entities:
        eid = ent.get("@id", "")
        if eid and ent.get("@type") != "woo:Source":
            id_to_name[eid] = ent.get("name", eid.split(":")[-1])
            id_to_type[eid] = ent.get("@type", "")

    # Filter to meaningful relationships only
    meaningful = [
        r for r in relationships
        if r.get("@type") == "woo:Relationship"
        and r.get("predicate", "") != "woo:mentionedIn"
        and r.get("confidence", 0) >= min_confidence
    ]

    # Compute degree for each entity
    degree: dict[str, int] = {}
    for rel in meaningful:
        src = rel.get("subject", {}).get("@id", "")
        tgt = rel.get("object", {}).get("@id", "")
        if src in id_to_name:
            degree[src] = degree.get(src, 0) + 1
        if tgt in id_to_name:
            degree[tgt] = degree.get(tgt, 0) + 1

    # Pick top-N nodes
    top_ids = set(
        n for n, _ in sorted(degree.items(), key=lambda x: -x[1])[:max_nodes]
    )

    # Keep only edges where both ends are in top_ids
    edges = [
        r for r in meaningful
        if r.get("subject", {}).get("@id", "") in top_ids
        and r.get("object", {}).get("@id", "") in top_ids
    ]

    if not edges:
        click.echo("No relationships to render.")
        return

    def mermaid_id(raw: str) -> str:
        """Sanitize an entity @id into a valid Mermaid node ID."""
        return re.sub(r"[^a-zA-Z0-9_]", "_", raw)

    def short_label(name: str, etype: str) -> str:
        type_abbrev = {"Person": "👤", "Place": "📍", "Organization": "🏛", "CreativeWork": "📄", "Event": "📅", "Date": "🗓"}
        icon = type_abbrev.get(etype, "")
        # Truncate long names
        label = name if len(name) <= 30 else name[:27] + "…"
        return f"{icon} {label}".strip()

    def short_pred(predicate: str) -> str:
        return predicate.split(":")[-1]

    lines = ["```mermaid", "graph LR"]

    # Emit node definitions
    seen_nodes: set[str] = set()
    for rel in edges:
        for eid in [rel["subject"]["@id"], rel["object"]["@id"]]:
            if eid not in seen_nodes and eid in id_to_name:
                nid = mermaid_id(eid)
                label = short_label(id_to_name[eid], id_to_type.get(eid, ""))
                lines.append(f'    {nid}["{label}"]')
                seen_nodes.add(eid)

    # Emit edges
    for rel in edges:
        src_id = mermaid_id(rel["subject"]["@id"])
        tgt_id = mermaid_id(rel["object"]["@id"])
        pred = short_pred(rel.get("predicate", ""))
        lines.append(f"    {src_id} -->|{pred}| {tgt_id}")

    lines.append("```")
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

    common_words = {
        "east", "west", "north", "south", "new", "old",
        "general", "special", "local", "remote", "total", "standard",
        "statistical", "manuscript", "symposia", "symposium",
        "baseline", "random", "normal", "primary", "secondary",
        "analysis", "method", "methods", "model", "models",
        "theory", "experiment", "experiments", "result", "results",
        "data", "system", "process", "field", "fields", "effect",
        "effects", "series", "trial", "trials", "operator", "operators",
        "appendix", "abstract", "summary", "review", "note", "notes",
        "letter", "comment", "comments", "reply", "response",
        "proceedings", "conference", "workshop", "seminar",
    }

    def is_noise(entity: dict) -> bool:
        if entity.get("@type") == "woo:Source":
            return False
        name = entity.get("name", "")
        if len(name) <= 3:
            return True
        alpha_ratio = sum(c.isalpha() or c.isspace() for c in name) / max(len(name), 1)
        if alpha_ratio < 0.5:
            return True
        if name.lower() in common_words:
            return True
        # Vague dates without a year
        if entity.get("@type") == "Date" and not re.search(r"\b(1[5-9]\d{2}|20[0-2]\d)\b", name):
            return True
        # Trailing comma (citation artifact)
        if name.endswith(","):
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


@main.command(name="merge-people")
@click.option("--dry-run", is_flag=True, help="Show merges without applying")
@click.pass_context
def merge_people(ctx: click.Context, dry_run: bool) -> None:
    """Use LLM to merge Person entities: normalize names, remove non-people."""
    import re
    from collections import defaultdict
    from concurrent.futures import ThreadPoolExecutor, as_completed

    from woograph.llm.client import create_completion, load_llm_config

    repo_root: Path = ctx.obj["repo_root"]
    global_path = repo_root / "graph" / "global.jsonld"

    if not global_path.exists():
        click.echo("No global.jsonld found. Run 'woograph merge' first.")
        raise SystemExit(1)

    llm_config = load_llm_config()
    if not llm_config:
        click.echo("No LLM API key found.")
        raise SystemExit(1)

    graph = json.loads(global_path.read_text())
    entities = graph["entities"]
    relationships = graph["relationships"]

    people = [e for e in entities if e.get("@type") == "Person"]
    click.echo(f"Person entities: {len(people)}")

    # --- 1. Remove initials-only (no surname) ---
    initials_only = {
        e["@id"] for e in people
        if re.match(r"^([A-Z]\.?\s*)+$", e["name"].strip())
    }
    click.echo(f"Initials-only (removing): {len(initials_only)}")

    # --- 2. Group by surname for merging ---
    surname_groups: dict[str, list[dict]] = defaultdict(list)
    for e in people:
        if e["@id"] in initials_only:
            continue
        parts = e["name"].split()
        if parts:
            surname = parts[-1]
            # Only group if surname looks real (capitalized, >2 chars)
            if len(surname) > 2 and surname[0].isupper() and surname[1:].islower():
                surname_groups[surname].append(e)

    # Only process groups with multiple variants
    merge_groups = {k: v for k, v in surname_groups.items() if len(v) > 1}
    click.echo(f"Surnames with multiple variants: {len(merge_groups)}")

    # --- 3. Send to LLM for merge decisions ---
    id_mapping: dict[str, str] = {}  # old_id → canonical_id
    canonical_names: dict[str, str] = {}  # canonical_id → best name
    not_people: set[str] = set()

    def process_surname_group(surname: str, group: list[dict]) -> dict:
        variants = "\n".join(f"- {e['name']}" for e in group)
        prompt = (
            f"These are all entities extracted from academic papers that share "
            f"the surname '{surname}'.\n\n"
            f"Variants:\n{variants}\n\n"
            f"For each variant, determine:\n"
            f"1. Is it actually a person's name? (NOT_PERSON if it's a place, "
            f"organization, citation fragment, or noise)\n"
            f"2. Which variants refer to the same person? Group them.\n"
            f"3. What is the best canonical form of each person's name? "
            f"(Prefer full first name over initials, e.g., 'Brenda J. Dunne' "
            f"over 'B. J. Dunne')\n\n"
            f"Return JSON: {{\"groups\": [[\"variant1\", \"variant2\"], ...], "
            f"\"canonical\": {{\"variant\": \"canonical form\"}}, "
            f"\"not_people\": [\"variant\", ...]}}"
        )
        response = create_completion(llm_config, prompt, max_tokens=2048, json_mode=True)
        if not response:
            return {"surname": surname, "groups": [], "canonical": {}, "not_people": []}
        try:
            result = json.loads(response)
            result["surname"] = surname
            return result
        except json.JSONDecodeError:
            return {"surname": surname, "groups": [], "canonical": {}, "not_people": []}

    click.echo(f"Sending {len(merge_groups)} surname groups to LLM...")

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(process_surname_group, surname, group): surname
            for surname, group in merge_groups.items()
        }
        done = 0
        for future in as_completed(futures):
            done += 1
            surname = futures[future]
            try:
                result = future.result()
                # Process not_people
                for name in result.get("not_people", []):
                    for e in merge_groups.get(result["surname"], []):
                        if e["name"] == name:
                            not_people.add(e["@id"])

                # Process merge groups
                canonical_map = result.get("canonical", {})
                for group_variants in result.get("groups", []):
                    if len(group_variants) < 2:
                        continue
                    # Find the canonical name for this group
                    canonical = None
                    for v in group_variants:
                        if v in canonical_map:
                            canonical = canonical_map[v]
                            break
                    if not canonical:
                        # Pick the longest variant as canonical
                        canonical = max(group_variants, key=len)

                    # Find entity IDs for these variants
                    group_entities = merge_groups.get(result["surname"], [])
                    variant_entities = [e for e in group_entities if e["name"] in group_variants]
                    if len(variant_entities) < 2:
                        continue

                    # First entity becomes canonical
                    canon_entity = variant_entities[0]
                    canonical_names[canon_entity["@id"]] = canonical
                    for e in variant_entities[1:]:
                        id_mapping[e["@id"]] = canon_entity["@id"]

                if done % 10 == 0:
                    click.echo(f"  {done}/{len(merge_groups)} groups processed")
            except Exception as exc:
                click.echo(f"  Failed for {surname}: {exc}")

    total_merges = len(id_mapping)
    click.echo("\nResults:")
    click.echo(f"  Not people: {len(not_people)}")
    click.echo(f"  Merge mappings: {total_merges}")
    click.echo(f"  Name normalizations: {len(canonical_names)}")

    if dry_run:
        for old_id, new_id in sorted(id_mapping.items()):
            old_name = next((e["name"] for e in entities if e["@id"] == old_id), old_id)
            new_name = canonical_names.get(new_id, next((e["name"] for e in entities if e["@id"] == new_id), new_id))
            click.echo(f"  MERGE: '{old_name}' → '{new_name}'")
        for eid in sorted(not_people):
            name = next((e["name"] for e in entities if e["@id"] == eid), eid)
            click.echo(f"  REMOVE: '{name}'")
        return

    # --- 4. Apply merges ---
    remove_ids = initials_only | not_people | set(id_mapping.keys())

    # Update canonical names
    for e in entities:
        if e["@id"] in canonical_names:
            e["name"] = canonical_names[e["@id"]]

    # Filter entities
    clean_entities = [e for e in entities if e["@id"] not in remove_ids]

    # Rewrite relationships
    clean_rels = []
    seen_keys: set[tuple] = set()
    for r in relationships:
        sid = r["subject"]["@id"] if isinstance(r["subject"], dict) else r["subject"]
        oid = r["object"]["@id"] if isinstance(r["object"], dict) else r["object"]
        # Skip if either end is removed (not merged, just removed)
        if sid in (initials_only | not_people) or oid in (initials_only | not_people):
            continue
        # Remap merged IDs
        sid = id_mapping.get(sid, sid)
        oid = id_mapping.get(oid, oid)
        if sid == oid:
            continue
        key = (sid, r.get("predicate", ""), oid)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        r_copy = dict(r)
        r_copy["subject"] = {"@id": sid}
        r_copy["object"] = {"@id": oid}
        clean_rels.append(r_copy)

    graph["entities"] = clean_entities
    graph["relationships"] = clean_rels
    global_path.write_text(json.dumps(graph, indent=2) + "\n")

    from woograph.graph.merge import generate_stats
    stats = generate_stats(graph)
    stats_path = repo_root / "graph" / "stats.json"
    stats_path.write_text(json.dumps(stats, indent=2) + "\n")

    click.echo(
        f"Merged graph: {stats['total_entities']} entities, "
        f"{stats['total_relationships']} relationships"
    )


@main.command(name="merge-orgs")
@click.option("--dry-run", is_flag=True, help="Show merges without applying")
@click.option("--batch-size", default=30, help="Orgs per LLM call")
@click.pass_context
def merge_orgs(ctx: click.Context, dry_run: bool, batch_size: int) -> None:
    """Use LLM to merge Organization entities: normalize names, remove non-orgs."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    from woograph.llm.client import create_completion, load_llm_config

    repo_root: Path = ctx.obj["repo_root"]
    global_path = repo_root / "graph" / "global.jsonld"

    if not global_path.exists():
        click.echo("No global.jsonld found.")
        raise SystemExit(1)

    llm_config = load_llm_config()
    if not llm_config:
        click.echo("No LLM API key found.")
        raise SystemExit(1)

    graph = json.loads(global_path.read_text())
    entities = graph["entities"]
    relationships = graph["relationships"]

    orgs = [e for e in entities if e.get("@type") == "Organization"]
    click.echo(f"Organization entities: {len(orgs)}")

    # Send in batches - LLM identifies noise and merge groups
    batches = [orgs[i:i + batch_size] for i in range(0, len(orgs), batch_size)]
    not_orgs: set[str] = set()
    id_mapping: dict[str, str] = {}
    canonical_names: dict[str, str] = {}

    def process_batch(batch: list[dict]) -> dict:
        org_list = "\n".join(f"- {e['name']}" for e in batch)
        prompt = (
            "These are entities tagged as 'Organization' extracted from academic papers "
            "about consciousness research, parapsychology, and physics.\n\n"
            f"Entities:\n{org_list}\n\n"
            "For each entity, determine:\n"
            "1. NOT_ORG: Not actually an organization (e.g., citation fragments like "
            "'B. J. & Jahn', experiment labels like 'All Local Data', generic phrases, "
            "OCR noise, or items that are really journals/publications/concepts)\n"
            "2. MERGE: Which entities refer to the same organization? "
            "E.g., 'Journal of Scientific Exploration' and 'J. Scientific Exploration' "
            "and 'Journal ofScientific Exploration' are the same.\n"
            "3. CANONICAL: The best normalized name for each group.\n\n"
            "Return JSON: {\"not_orgs\": [\"name\", ...], "
            "\"merge_groups\": [[\"name1\", \"name2\"], ...], "
            "\"canonical\": {\"name\": \"canonical form\"}}"
        )
        response = create_completion(llm_config, prompt, max_tokens=4096, json_mode=True)
        if not response:
            return {"not_orgs": [], "merge_groups": [], "canonical": {}}
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            return {"not_orgs": [], "merge_groups": [], "canonical": {}}

    click.echo(f"Sending {len(batches)} batches to LLM...")

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(process_batch, batch): i for i, batch in enumerate(batches)}
        for future in as_completed(futures):
            batch_idx = futures[future]
            try:
                result = future.result()
                batch = batches[batch_idx]
                name_to_entity = {e["name"]: e for e in batch}

                for name in result.get("not_orgs", []):
                    if name in name_to_entity:
                        not_orgs.add(name_to_entity[name]["@id"])

                for group in result.get("merge_groups", []):
                    if len(group) < 2:
                        continue
                    group_entities = [name_to_entity[n] for n in group if n in name_to_entity]
                    if len(group_entities) < 2:
                        continue
                    canon = group_entities[0]
                    canon_name = result.get("canonical", {}).get(group[0], group[0])
                    canonical_names[canon["@id"]] = canon_name
                    for e in group_entities[1:]:
                        id_mapping[e["@id"]] = canon["@id"]

                if (batch_idx + 1) % 10 == 0:
                    click.echo(f"  {batch_idx + 1}/{len(batches)} batches processed")
            except Exception as exc:
                click.echo(f"  Batch {batch_idx + 1} failed: {exc}")

    click.echo("\nResults:")
    click.echo(f"  Not organizations: {len(not_orgs)}")
    click.echo(f"  Merge mappings: {len(id_mapping)}")
    click.echo(f"  Name normalizations: {len(canonical_names)}")

    if dry_run:
        return

    # Apply
    remove_ids = not_orgs | set(id_mapping.keys())
    for e in entities:
        if e["@id"] in canonical_names:
            e["name"] = canonical_names[e["@id"]]

    clean_entities = [e for e in entities if e["@id"] not in remove_ids]

    clean_rels = []
    seen_keys: set[tuple] = set()
    for r in relationships:
        sid = r["subject"]["@id"] if isinstance(r["subject"], dict) else r["subject"]
        oid = r["object"]["@id"] if isinstance(r["object"], dict) else r["object"]
        if sid in not_orgs or oid in not_orgs:
            continue
        sid = id_mapping.get(sid, sid)
        oid = id_mapping.get(oid, oid)
        if sid == oid:
            continue
        key = (sid, r.get("predicate", ""), oid)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        r_copy = dict(r)
        r_copy["subject"] = {"@id": sid}
        r_copy["object"] = {"@id": oid}
        clean_rels.append(r_copy)

    graph["entities"] = clean_entities
    graph["relationships"] = clean_rels
    global_path.write_text(json.dumps(graph, indent=2) + "\n")

    from woograph.graph.merge import generate_stats
    stats = generate_stats(graph)
    stats_path = repo_root / "graph" / "stats.json"
    stats_path.write_text(json.dumps(stats, indent=2) + "\n")

    click.echo(
        f"Merged graph: {stats['total_entities']} entities, "
        f"{stats['total_relationships']} relationships"
    )


@main.command(name="llm-clean-places")
@click.option("--batch-size", default=80, help="Place entities per LLM call")
@click.option("--dry-run", is_flag=True, help="Show what would be removed without modifying")
@click.pass_context
def llm_clean_places(ctx: click.Context, batch_size: int, dry_run: bool) -> None:
    """Use LLM to remove non-place entities from the Place type in the global graph.

    Identifies person surnames, abstract concepts, OCR noise, and other
    misclassified entities that spaCy tagged as GPE/LOC/FAC but aren't
    real geographic locations.
    """
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

    places = [e for e in entities if e.get("@type") == "Place"]
    click.echo(f"Place entities: {len(places)}")

    if not places:
        click.echo("No Place entities found.")
        return

    batches = [places[i:i + batch_size] for i in range(0, len(places), batch_size)]
    not_place_ids: set[str] = set()

    def classify_batch(batch: list[dict]) -> set[str]:
        entity_list = "\n".join(f"- {e['name']}" for e in batch)
        prompt = (
            "You are classifying named entities extracted by spaCy NER from academic papers "
            "about parapsychology, consciousness research, and physics.\n\n"
            "spaCy tagged each of the following as a geographic place (GPE/LOC/FAC). "
            "For each name, classify it as PLACE (real geographic location: country, city, "
            "region, building, landmark, body of water, etc.) or NOT_PLACE (person surname, "
            "abstract concept, academic term, OCR artifact, organization name, "
            "or anything else that isn't a real geographic place).\n\n"
            "Names to classify:\n"
            f"{entity_list}\n\n"
            "Return a JSON object with the name as key and \"PLACE\" or \"NOT_PLACE\" as value.\n"
            "Examples of NOT_PLACE: Honorton (surname), Rhines (surname), Bayesian (concept), "
            "Pharmacology (field), Schocken (publisher surname), Lavoisier (person name).\n"
            "Examples of PLACE: Princeton, New Jersey, London, the White House, the Nile, USSR."
        )
        response = create_completion(llm_config, prompt, max_tokens=4096, json_mode=True)
        if not response:
            return set()
        try:
            result = json.loads(response)
            return {
                e["@id"] for e in batch
                if result.get(e["name"], "PLACE") == "NOT_PLACE"
            }
        except (json.JSONDecodeError, KeyError):
            return set()

    click.echo(f"Sending {len(batches)} batches to {llm_config.provider}:{llm_config.model}...")

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(classify_batch, batch): i for i, batch in enumerate(batches)}
        for future in as_completed(futures):
            batch_idx = futures[future]
            try:
                batch_not_place = future.result()
                not_place_ids.update(batch_not_place)
                click.echo(f"  Batch {batch_idx + 1}/{len(batches)}: {len(batch_not_place)} non-places")
            except Exception as exc:
                click.echo(f"  Batch {batch_idx + 1}/{len(batches)}: failed ({exc})")

    click.echo(f"\nLLM identified {len(not_place_ids)}/{len(places)} non-place entities")

    if dry_run:
        for e in places:
            if e["@id"] in not_place_ids:
                click.echo(f"  REMOVE: {e['name']}")
        return

    clean_entities = [e for e in entities if e["@id"] not in not_place_ids]
    clean_rels = [
        r for r in relationships
        if (r["subject"]["@id"] if isinstance(r["subject"], dict) else r["subject"]) not in not_place_ids
        and (r["object"]["@id"] if isinstance(r["object"], dict) else r["object"]) not in not_place_ids
    ]

    graph["entities"] = clean_entities
    graph["relationships"] = clean_rels
    global_path.write_text(json.dumps(graph, indent=2) + "\n")

    from woograph.graph.merge import generate_stats
    stats = generate_stats(graph)
    stats_path = repo_root / "graph" / "stats.json"
    stats_path.write_text(json.dumps(stats, indent=2) + "\n")

    click.echo(
        f"Cleaned graph: {stats['total_entities']} entities "
        f"(removed {len(not_place_ids)} non-places), "
        f"{stats['total_relationships']} relationships"
    )


@main.command()
@click.option("--dry-run", is_flag=True, help="Show what would be geocoded without calling API")
@click.option("--force", is_flag=True, help="Re-geocode even if cache exists")
@click.option("--delay", default=1.1, type=float, help="Delay between Nominatim requests (seconds)")
@click.pass_context
def geocode(ctx: click.Context, dry_run: bool, force: bool, delay: float) -> None:
    """Geocode Place entities using OpenStreetMap Nominatim.

    Ambiguous results (where top candidates have similar importance scores)
    are automatically disambiguated using the LLM with context from the source
    documents.
    """
    from woograph.geocode import (
        geocode_all,
        load_place_entities,
        write_geocoded_json,
    )

    repo_root: Path = ctx.obj["repo_root"]
    global_path = repo_root / "graph" / "global.jsonld"

    if not global_path.exists():
        click.echo("No global.jsonld found. Run 'woograph merge' first.")
        raise SystemExit(1)

    # Load LLM config for disambiguation (optional — falls back to importance ranking)
    llm_config = load_llm_config()
    if llm_config:
        click.echo(f"LLM disambiguation enabled ({llm_config.provider}:{llm_config.model})")
    else:
        click.echo("No LLM API key found — disambiguation disabled, using importance ranking only")

    places = load_place_entities(global_path)
    click.echo(f"Found {len(places)} Place entities")

    cache_dir = repo_root / "pipeline" / ".geocache"
    successes, failures = geocode_all(
        places, cache_dir=cache_dir, delay=delay, force=force,
        dry_run=dry_run, llm_config=llm_config,
    )

    if dry_run:
        noise = [f for f in failures if f["reason"] == "noise_filtered"]
        click.echo(f"Would geocode: {len(places) - len(noise)} places")
        click.echo(f"Would skip (noise): {len(noise)} places")
        click.echo("Noise examples:")
        for f in noise[:10]:
            click.echo(f"  {f['name']!r}")
        return

    output_path = repo_root / "site" / "data" / "geocoded.json"
    write_geocoded_json(successes, failures, len(places), output_path)

    click.echo(
        f"Geocoded: {len(successes)}/{len(places)} places "
        f"({len(failures)} failed) → {output_path}"
    )
