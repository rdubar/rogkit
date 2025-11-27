#!/usr/bin/env python3
"""CLI utility and helper functions to extract readable text from a URL."""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from dataclasses import dataclass
from typing import Iterable

import requests
from bs4 import BeautifulSoup
from requests import RequestException
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
from urllib.parse import urlencode, urlparse, parse_qsl, urlunparse

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
DEFAULT_TIMEOUT = 10
DEFAULT_RETRIES = 3
DEFAULT_BACKOFF = 0.5


class ScrapeError(Exception):
    """Raised when fetching or parsing fails."""


@dataclass
class ScrapeResult:
    url: str
    text: str
    title: str | None
    description: str | None
    links: list["Link"]


@dataclass
class Link:
    text: str
    href: str


def fix_url(url: str) -> str:
    """Ensure the URL has a scheme (defaults to https)."""
    if url.startswith(("http://", "https://")):
        return url
    return f"https://{url}"


def build_session(
    retries: int = DEFAULT_RETRIES,
    backoff: float = DEFAULT_BACKOFF,
    user_agent: str = DEFAULT_USER_AGENT,
) -> requests.Session:
    """Create a requests session with retry/backoff and a browser-like UA."""
    session = requests.Session()
    retry = Retry(
        total=retries,
        status_forcelist=(429, 500, 502, 503, 504),
        backoff_factor=backoff,
        allowed_methods=("GET", "HEAD"),
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update({"User-Agent": user_agent})
    return session


def _normalize_text(text: str) -> str:
    """Normalize whitespace for readable output."""
    lines: Iterable[str] = (line.strip() for line in text.splitlines())
    chunks: Iterable[str] = (phrase.strip() for line in lines for phrase in line.split("  "))
    return "\n".join(chunk for chunk in chunks if chunk)


def _extract_links(soup: BeautifulSoup, base_url: str) -> list[Link]:
    """Extract anchor tags as absolute URLs with cleaned text."""
    from urllib.parse import urljoin

    links: list[Link] = []
    seen: set[str] = set()  # de-dupe by href
    for anchor in soup.find_all("a", href=True):
        raw_href = anchor.get("href")
        if not raw_href:
            continue
        href = urljoin(base_url, raw_href)
        text = anchor.get_text(strip=True) or href
        if href in seen:
            continue
        seen.add(href)
        links.append(Link(text=text, href=href))
    return links


def parse_html(html: str | bytes, url: str) -> ScrapeResult:
    """Extract readable text and basic metadata from HTML."""
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    title = soup.title.string.strip() if soup.title and soup.title.string else None

    meta_tag = soup.find("meta", attrs={"name": "description"}) or soup.find(
        "meta", attrs={"property": "og:description"}
    )
    description = None
    if meta_tag:
        description = meta_tag.get("content") or meta_tag.get("value")
        if description:
            description = description.strip() or None

    text = _normalize_text(soup.get_text())
    links = _extract_links(soup, url)
    return ScrapeResult(url=url, text=text, title=title, description=description, links=links)


def scrape(
    url: str,
    session: requests.Session | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    pages: int = 1,
) -> ScrapeResult:
    """Fetch a URL and return cleaned text plus metadata."""
    fixed_url = fix_url(url)
    sess = session or build_session()

    def fetch_once(target_url: str) -> ScrapeResult:
        try:
            response = sess.get(target_url, timeout=timeout)
            response.raise_for_status()
        except RequestException as exc:
            raise ScrapeError(f"Error fetching {target_url}: {exc}") from exc
        return parse_html(response.content, target_url)

    if pages <= 1:
        return fetch_once(fixed_url)

    combined_links: dict[str, Link] = {}
    texts: list[str] = []
    description: str | None = None
    title: str | None = None

    for page_index in range(1, pages + 1):
        page_url = _with_page_param(fixed_url, page_index)
        result = fetch_once(page_url)
        if page_index == 1:
            title = result.title
            description = result.description
        texts.append(result.text)
        for link in result.links:
            combined_links.setdefault(link.href, link)

    return ScrapeResult(
        url=fixed_url,
        text="\n\n".join(texts),
        title=title,
        description=description,
        links=list(combined_links.values()),
    )


def _with_page_param(url: str, page_number: int) -> str:
    """Return URL with ?page=<n> set/replaced."""
    parsed = urlparse(url)
    query_params = dict(parse_qsl(parsed.query))
    query_params["page"] = str(page_number)
    new_query = urlencode(query_params)
    return urlunparse(parsed._replace(query=new_query))


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract readable text from a web page.")
    parser.add_argument("url", help="URL to fetch")
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT, help="User-Agent string to present")
    parser.add_argument("--retries", type=int, default=DEFAULT_RETRIES, help="Number of retry attempts")
    parser.add_argument("--backoff", type=float, default=DEFAULT_BACKOFF, help="Retry backoff factor")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="Request timeout in seconds")
    parser.add_argument("--pages", type=int, default=1, help="Number of paginated pages to fetch (uses ?page=N)")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output JSON containing text, title, and description",
    )
    parser.add_argument(
        "--include-meta",
        action="store_true",
        help="Include title/description in plain text output",
    )
    parser.add_argument(
        "--urls",
        action="store_true",
        help="Output extracted links in markdown format instead of page text",
    )
    args = parser.parse_args()

    session = build_session(retries=args.retries, backoff=args.backoff, user_agent=args.user_agent)

    try:
        result = scrape(args.url, session=session, timeout=args.timeout, pages=args.pages)
    except ScrapeError as exc:
        print(exc, file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(dataclasses.asdict(result), ensure_ascii=False, indent=2))
    else:
        if args.urls:
            for link in result.links:
                print(f"- [{link.text}]({link.href})")
        else:
            if args.include_meta:
                if result.title:
                    print(f"Title: {result.title}\n")
                if result.description:
                    print(f"Description: {result.description}\n")
            print(result.text)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
