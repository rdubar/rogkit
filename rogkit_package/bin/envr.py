"""
Environment variable viewer with secret masking.

Displays environment variables as a sorted table. Values for keys whose names
look like secrets (API_KEY, *_TOKEN, *_PASSWORD, etc.) are masked by default
so the output is safe to paste into an LLM or share. Pass --show to reveal.

Usage:
    env                    # all variables, secrets masked
    env --show             # all variables, real values
    env --keys-only        # just key names, one per line
    env PATH               # keys containing "PATH" (case-insensitive)
    env --val python       # filter by real value substring
    env --plain            # plain text output
    env --count            # print match count only
"""

from __future__ import annotations

import argparse
import os
from typing import Optional

from ._envsec import is_secret_key, mask

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


def apply_mask(items: list[tuple[str, str]], *, show: bool) -> list[tuple[str, str]]:
    """Mask values for secret-looking keys unless show=True."""
    if show:
        return items
    return [(k, mask(v) if is_secret_key(k) else v) for k, v in items]


def render_env(items: list[tuple[str, str]], *, plain: bool = False) -> None:
    """Render env var key/value pairs as a table or plain rows."""
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
        description="Display environment variables. Secret-looking values are masked unless --show is given.",
    )
    parser.add_argument("pattern", nargs="?", help="Filter keys containing this string")
    parser.add_argument("--val", metavar="PATTERN", help="Filter values containing this string")
    parser.add_argument("-s", "--show", action="store_true", help="Show real values (default: mask secrets)")
    parser.add_argument("-k", "--keys-only", action="store_true", help="Print only key names, one per line")
    parser.add_argument("--plain", action="store_true", help="Plain text output")
    parser.add_argument("--count", action="store_true", help="Print count of matching variables")
    args = parser.parse_args()

    items = list_env(pattern=args.pattern, val_pattern=args.val)

    if args.count:
        print(len(items))
        return 0

    if args.keys_only:
        for key, _ in items:
            print(key)
        return 0

    render_env(apply_mask(items, show=args.show), plain=args.plain)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
