"""
Command-line argument parser for media library CLI.

Handles search, display, sorting, database management, and Plex operations.
"""

from __future__ import annotations

import argparse
from typing import Iterable, Optional


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    """Parse command-line arguments for the `media` utility."""
    parser = argparse.ArgumentParser(
        description="Inspect the Plex Media Server SQLite database."
    )
    parser.add_argument(
        "search",
        nargs="*",
        help="Search the Plex library (title, parent, grandparent) using built-in formatting.",
    )
    parser.add_argument(
        "-q",
        "--query",
        help="SQL to execute against the Plex database (read-only).",
    )
    parser.add_argument(
        "-l",
        "--limit",
        type=int,
        default=20,
        help="Maximum rows to display when running a query (0 for no limit).",
    )
    parser.add_argument(
        "-n",
        "--number",
        type=int,
        default=10,
        help="Maximum items to display with the built-in search formatter.",
    )
    parser.add_argument(
        "-a",
        "--all",
        action="store_true",
        help="Show all results instead of limiting to --number.",
    )
    parser.add_argument(
        "-L",
        "--length",
        type=int,
        default=40,
        help="Title column width when using the built-in search formatter.",
    )
    parser.add_argument(
        "-i",
        "--info",
        action="store_true",
        help="Include item summaries when using the built-in search formatter.",
    )
    parser.add_argument(
        "-p",
        "--path",
        action="store_true",
        help="Include file paths when using the built-in search formatter.",
    )
    parser.add_argument(
        "--sort",
        choices=("added", "title", "year"),
        default="added",
        help="Sort order for built-in search results (default: added).",
    )
    parser.add_argument(
        "--reverse",
        "-r",
        action="store_true",
        help="Reverse the sort order for built-in search results.",
    )
    parser.add_argument(
        "--deep",
        "-d_",
        action="store_true",
        help="Include summary, path, and tag matching (slower search; tried automatically if cache search has no matches).",
    )
    parser.add_argument(
        "--zed",
        "-z",
        action="store_true",
        help="Show all matches sorted by year.",
    )
    parser.add_argument(
        "--list-paths",
        action="store_true",
        help="Print all candidate database paths and whether they exist.",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="Refresh the Plex database and merge extra media sources into the cache.",
    )
    parser.add_argument(
        "--update-plex",
        action="store_true",
        help="Refresh the Plex database snapshot without merging extras.",
    )
    parser.add_argument(
        "--rsync",
        action="store_true",
        help="Prefer rsync for remote Plex database transfers when available.",
    )
    parser.add_argument(
        "--show-path",
        action="store_true",
        help="Print the detected Plex database path and exit.",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show aggregate stats (count, total runtime, total size) for the displayed items.",
    )
    parser.add_argument(
        "--people",
        action="store_true",
        help="Search actors/directors via the live Plex database.",
    )
    parser.add_argument(
        "--daemon",
        action="store_true",
        help="Run the media daemon in the foreground, serving subsequent CLI requests.",
    )
    parser.add_argument(
        "--stop-daemon",
        action="store_true",
        help="Ask the running media daemon to exit.",
    )
    parser.add_argument(
        "--no-daemon",
        action="store_true",
        help="Run locally without attempting to use the background daemon.",
    )
    return parser.parse_args(list(argv) if argv is not None else None)
