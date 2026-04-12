"""
Environment variable viewer with filtering.

Displays environment variables as a sorted table. Supports filtering by
key name or value substring.

Usage:
    env                    # all variables, sorted
    env PATH               # keys containing "PATH" (case-insensitive)
    env --val python       # filter by value substring
    env PATH --val /usr    # filter by both key and value
    env --plain            # plain text output
    env --count            # print match count only
"""

from __future__ import annotations

import argparse
import os
from typing import Optional

try:
    from rich.console import Console
    from rich.table import Table
    from rich.text import Text

    console = Console()
    RICH_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover
    console = None  # type: ignore[assignment]
    RICH_AVAILABLE = False


def list_env(
    pattern: Optional[str] = None,
    val_pattern: Optional[str] = None,
) -> list[tuple[str, str]]:
    """Return sorted env var pairs, optionally filtered by key and/or value."""
    items = sorted(os.environ.items())
    if pattern:
        p = pattern.lower()
        items = [(k, v) for k, v in items if p in k.lower()]
    if val_pattern:
        vp = val_pattern.lower()
        items = [(k, v) for k, v in items if vp in v.lower()]
    return items


def render_env(items: list[tuple[str, str]], *, plain: bool = False) -> None:
    if not items:
        msg = "No matching environment variables."
        if RICH_AVAILABLE and not plain:
            console.print(Text(msg, style="yellow"))
        else:
            print(msg)
        return

    if RICH_AVAILABLE and not plain:
        table = Table(show_header=True, header_style="bold cyan", box=None, pad_edge=False)
        table.add_column("Variable", style="bold green", no_wrap=True)
        table.add_column("Value", overflow="fold")
        for key, value in items:
            table.add_row(key, value)
        console.print(table)
    else:
        width = max(len(k) for k, _ in items)
        for key, value in items:
            print(f"{key:<{width}}  {value}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Display environment variables with optional filtering."
    )
    parser.add_argument("pattern", nargs="?", help="Filter keys containing this string")
    parser.add_argument("--val", metavar="PATTERN", help="Filter values containing this string")
    parser.add_argument("--plain", action="store_true", help="Plain text output")
    parser.add_argument("--count", action="store_true", help="Print count of matching variables")
    args = parser.parse_args()

    items = list_env(pattern=args.pattern, val_pattern=args.val)

    if args.count:
        print(len(items))
        return 0

    render_env(items, plain=args.plain)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
