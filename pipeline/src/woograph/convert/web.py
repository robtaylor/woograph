"""Web content extraction using trafilatura."""

import logging
from pathlib import Path

import trafilatura

logger = logging.getLogger(__name__)


def convert_url(url: str, output_dir: Path) -> Path:
    """Download and extract content from a URL using trafilatura.

    Fetches the web page, extracts the main text content, and saves
    it as markdown in output_dir/content.md.

    Args:
        url: The URL to fetch and extract content from.
        output_dir: Directory to write the output file.

    Returns:
        Path to the generated content.md file.

    Raises:
        ValueError: If the URL is empty.
        RuntimeError: If the content cannot be fetched or extracted.
    """
    if not url:
        raise ValueError("URL must not be empty")

    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Fetching URL: %s", url)

    downloaded = trafilatura.fetch_url(url)
    if downloaded is None:
        raise RuntimeError(f"Failed to fetch URL: {url}")

    extracted = trafilatura.extract(
        downloaded,
        output_format="txt",
        include_links=True,
        include_tables=True,
    )
    if extracted is None:
        raise RuntimeError(
            f"Failed to extract content from URL: {url}"
        )

    # Wrap in a simple markdown structure
    md_text = f"<!-- Source: {url} -->\n\n{extracted}\n"

    content_path = output_dir / "content.md"
    content_path.write_text(md_text)

    logger.info("URL extracted: %d chars from %s", len(extracted), url)
    return content_path
