"""Web content extraction using trafilatura."""

import logging
from pathlib import Path

import requests
import trafilatura

logger = logging.getLogger(__name__)

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


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

    resp = requests.get(
        url,
        headers=_BROWSER_HEADERS,
        timeout=30,
        allow_redirects=True,
    )
    if not resp.ok:
        raise RuntimeError(f"not a 200 response: {resp.status_code} for URL {url}")

    extracted = trafilatura.extract(
        resp.text,
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
