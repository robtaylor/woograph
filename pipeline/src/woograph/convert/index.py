"""Index page discovery: crawl a link-list/directory page and enumerate content URLs."""

import logging
import time
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)

_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# URL path segments that indicate non-content pages to skip
_SKIP_PATTERNS = {
    "/login", "/logout", "/register", "/signup", "/sign-up",
    "/admin", "/wp-admin", "/wp-login",
    "/feed", "/rss", "/sitemap",
    "/search", "/tag/", "/tags/", "/category/", "/categories/",
    "/author/", "/user/",
    "#",
}


@dataclass
class PageInfo:
    url: str
    title: str


def _fetch_html(url: str, timeout: int = 30) -> str | None:
    """Fetch a URL and return raw HTML, or None on failure."""
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": _BROWSER_UA},
            timeout=timeout,
            allow_redirects=True,
        )
        if resp.ok:
            return resp.text
        logger.warning("HTTP %s fetching %s", resp.status_code, url)
    except requests.RequestException as exc:
        logger.warning("Failed to fetch %s: %s", url, exc)
    return None


def _is_content_url(url: str, base_domain: str) -> bool:
    """Return True if the URL looks like a content page on the same domain."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False
    if parsed.netloc and parsed.netloc != base_domain:
        return False
    path = parsed.path.lower()
    for skip in _SKIP_PATTERNS:
        if skip in path:
            return False
    return True


def _extract_links(html: str, base_url: str, base_domain: str) -> list[PageInfo]:
    """Extract content links from an HTML page."""
    soup = BeautifulSoup(html, "html.parser")
    seen: set[str] = set()
    pages: list[PageInfo] = []

    for tag in soup.find_all("a", href=True):
        if not isinstance(tag, Tag):
            continue
        href = str(tag["href"]).strip()
        if not href or href.startswith("javascript:"):
            continue
        absolute = urljoin(base_url, href).split("#")[0]
        if not absolute or absolute == base_url:
            continue
        if absolute in seen:
            continue
        if not _is_content_url(absolute, base_domain):
            continue
        seen.add(absolute)
        title = tag.get_text(strip=True) or absolute
        pages.append(PageInfo(url=absolute, title=title))

    return pages


def _find_next_page(html: str, base_url: str) -> str | None:
    """Try to find a 'next page' URL using common pagination patterns."""
    soup = BeautifulSoup(html, "html.parser")

    # 1. <link rel="next">
    tag = soup.find("link", rel="next")
    if isinstance(tag, Tag) and tag.get("href"):
        return urljoin(base_url, str(tag["href"]))

    # 2. <a rel="next">
    tag = soup.find("a", rel="next")
    if isinstance(tag, Tag) and tag.get("href"):
        return urljoin(base_url, str(tag["href"]))

    # 3. Anchor with common "next" text
    for candidate in soup.find_all("a", href=True):
        if not isinstance(candidate, Tag):
            continue
        label = candidate.get_text(strip=True).lower()
        if label in ("next", "next page", "»", "›", "→"):
            href = urljoin(base_url, str(candidate["href"]))
            if href != base_url:
                return href

    return None


def discover_index(
    url: str,
    max_pages: int = 5000,
    page_delay: float = 1.0,
) -> list[PageInfo]:
    """Crawl an index/directory URL and return a list of content page URLs.

    Follows pagination (rel=next, common "Next" links) up to max_pages total
    discovered content URLs. Does not recurse into discovered pages.

    Args:
        url: The index page URL to crawl.
        max_pages: Hard cap on total content URLs returned.
        page_delay: Seconds to wait between pagination requests (rate limiting).

    Returns:
        List of PageInfo(url, title) for discovered content pages.
    """
    parsed = urlparse(url)
    base_domain = parsed.netloc
    current_url: str | None = url
    all_pages: list[PageInfo] = []
    visited_index_pages: set[str] = set()
    pagination_count = 0

    while current_url and len(all_pages) < max_pages:
        if current_url in visited_index_pages:
            break
        visited_index_pages.add(current_url)

        logger.info("Fetching index page %d: %s", pagination_count + 1, current_url)
        html = _fetch_html(current_url)
        if html is None:
            break

        links = _extract_links(html, current_url, base_domain)
        existing = {p.url for p in all_pages}
        new_links = [p for p in links if p.url not in existing and p.url != url]
        logger.info("  Found %d new content links", len(new_links))
        all_pages.extend(new_links)

        next_url = _find_next_page(html, current_url)
        pagination_count += 1

        if next_url and next_url not in visited_index_pages:
            logger.info("  Pagination: following next page → %s", next_url)
            time.sleep(page_delay)
            current_url = next_url
        else:
            break

    result = all_pages[:max_pages]
    logger.info(
        "Index discovery complete: %d pages found across %d index page(s)",
        len(result),
        pagination_count,
    )
    return result
