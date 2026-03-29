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
            pdf_path = repo_root / "submissions" / "files" / file_name
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
