# pyright: reportMissingImports=false
"""
Utility for quick searching of Plex library.

API Info:
https://python-plexapi.readthedocs.io/
"""

import argparse

from collections import defaultdict
from typing import Any, Dict, List
from urllib.parse import urlparse

from ..bin.tomlr import load_rogkit_toml

from plexapi.server import PlexServer  # type: ignore[import]

# Load the configuration from TOML file
TOML = load_rogkit_toml()
PLEX_SERVER_URL = TOML.get("plex", {}).get("plex_server_url", None)
PLEX_SERVER_TOKEN = TOML.get("plex", {}).get("plex_server_token", None)
PLEX_SERVER_PORT = TOML.get("plex", {}).get("plex_server_port", 32400)


def _build_base_url(raw_url: str | None, default_port: int) -> str:
    """Normalise the configured Plex connection details into a base URL."""
    if not raw_url:
        raise RuntimeError(
            "Missing Plex server URL. Please set `plex.plex_server_url` in your rogkit config."
        )

    url = raw_url.strip()
    if "://" not in url:
        url = f"http://{url}"

    parsed = urlparse(url)

    if not parsed.hostname:
        raise ValueError(f"Invalid Plex server URL: {raw_url!r}")

    protocol = parsed.scheme or "http"
    port = parsed.port or default_port
    host = parsed.hostname

    netloc = f"{host}:{port}" if port else host
    return f"{protocol}://{netloc}"


def _truncate_summary(summary: str, max_length: int = 140) -> str:
    """Collapse whitespace and trim long summaries for compact CLI output."""
    squashed = " ".join(summary.split())
    if len(squashed) <= max_length:
        return squashed
    return f"{squashed[: max_length - 3]}..."


def _iter_grouped_results(groups: Dict[str, List[Any]], limit_per_group: int):
    first = True
    for group_name, items in groups.items():
        if not first:
            yield None
        first = False
        size = len(items)
        yield f"{group_name} ({size} result{'s' if size != 1 else ''}):"
        for item in items[:limit_per_group]:
            yield _format_result_line(item)


def _format_result_line(item: Any) -> str:
    """Return a human-readable, multi-line string for a single match."""
    media_type = getattr(item, "type", None) or "item"
    title = getattr(item, "title", None) or "<untitled>"

    if media_type == "episode":
        show = getattr(item, "grandparentTitle", None)
        season = getattr(item, "parentTitle", None)
        pieces = [p for p in [show, season] if p]
        if pieces:
            title = " · ".join(pieces) + f" – {title}"

    year = getattr(item, "year", None)
    rating = getattr(item, "rating", None)
    reason = getattr(item, "reasonTitle", None) or getattr(item, "reason", None)

    detail_fragments = []
    if year:
        detail_fragments.append(str(year))
    if rating:
        try:
            detail_fragments.append(f"{float(rating):.1f}")
        except (TypeError, ValueError):
            detail_fragments.append(str(rating))
    if reason:
        detail_fragments.append(f"match: {reason}")

    details = f" [{', '.join(detail_fragments)}]" if detail_fragments else ""

    summary = getattr(item, "summary", None)
    summary_line = f"\n    {_truncate_summary(summary)}" if summary else ""

    return f"  - {title} ({media_type}){details}{summary_line}"


def search_plex(query: str, *, limit: int = 5) -> Dict[str, List[Any]]:
    if not PLEX_SERVER_TOKEN:
        raise RuntimeError(
            "Missing Plex token. Please set `plex.plex_server_token` in your rogkit config."
        )

    base_url = _build_base_url(PLEX_SERVER_URL, PLEX_SERVER_PORT)

    plex = PlexServer(base_url, PLEX_SERVER_TOKEN)
    results = plex.search(query)

    if not results:
        print(f"No results found for {query!r}.")
        return {}

    grouped: Dict[str, List[Any]] = defaultdict(list)
    for item in results:
        hub = getattr(item, "type", None) or "Results"
        grouped[hub.capitalize()].append(item)

    for line in _iter_grouped_results(grouped, limit):
        if line is None:
            print()
        else:
            print(line)

    return grouped


def main():
    """CLI entry point for the Plex search utility."""

    parser = argparse.ArgumentParser(description="Search your Plex library.")
    parser.add_argument(
        "query",
        nargs="?",
        default="dylan",
        help="Search term to look for in Plex (default: %(default)s)",
    )
    parser.add_argument(
        "-n",
        "--limit",
        type=int,
        default=5,
        help="Maximum results to display per hub (default: %(default)s)",
    )

    args = parser.parse_args()
    search_plex(args.query, limit=args.limit)


if __name__ == "__main__":
    main()
