#!/usr/bin/env python3
"""Claude Code token usage — daily totals and 5-minute rate window."""

import argparse
import glob
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path

from ..settings import get_invoking_cwd  # noqa: F401  (convention)

try:
    from rich.console import Console
    from rich.table import Table
    from rich.text import Text

    console = Console()
    RICH_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover
    console = None
    RICH_AVAILABLE = False

CLAUDE_PROJECTS_DIR = Path.home() / ".claude" / "projects"
RATE_WINDOW_MINUTES = 5


@dataclass
class TokenTotals:
    input: int = 0
    output: int = 0
    cache_read: int = 0
    cache_write: int = 0
    messages: int = 0

    @property
    def total(self) -> int:
        return self.input + self.output + self.cache_read + self.cache_write

    def add(self, usage: dict) -> None:
        self.input += usage.get("input_tokens", 0)
        self.output += usage.get("output_tokens", 0)
        self.cache_read += usage.get("cache_read_input_tokens", 0)
        self.cache_write += usage.get("cache_creation_input_tokens", 0)
        self.messages += 1


def _parse_ts(ts_str: str) -> datetime | None:
    try:
        return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def collect_usage(since: datetime) -> TokenTotals:
    totals = TokenTotals()
    pattern = str(CLAUDE_PROJECTS_DIR / "**" / "*.jsonl")
    for path in glob.glob(pattern, recursive=True):
        try:
            with open(path) as fh:
                for line in fh:
                    try:
                        d = json.loads(line)
                        ts = _parse_ts(d.get("timestamp", ""))
                        if ts is None or ts < since:
                            continue
                        msg = d.get("message", {})
                        if isinstance(msg, dict) and "usage" in msg:
                            totals.add(msg["usage"])
                    except (json.JSONDecodeError, KeyError):
                        continue
        except OSError:
            continue
    return totals


def _fmt(n: int) -> str:
    return f"{n:,}"


def _print_table(label: str, totals: TokenTotals, style_color: str) -> None:
    if RICH_AVAILABLE:
        table = Table(title=f"[bold {style_color}]{label}[/]", box=None, pad_edge=True, show_edge=False)
        table.add_column("Metric", style="dim", min_width=22)
        table.add_column("Tokens", justify="right", style=style_color)
        table.add_row("Input", _fmt(totals.input))
        table.add_row("Output", _fmt(totals.output))
        table.add_row("Cache read", _fmt(totals.cache_read))
        table.add_row("Cache write", _fmt(totals.cache_write))
        table.add_row("─" * 22, "─" * 10)
        table.add_row("[bold]Total[/]", f"[bold]{_fmt(totals.total)}[/]")
        table.add_row("Messages", _fmt(totals.messages))
        console.print(table)
    else:
        print(f"\n{label}")
        print(f"  Input:       {_fmt(totals.input)}")
        print(f"  Output:      {_fmt(totals.output)}")
        print(f"  Cache read:  {_fmt(totals.cache_read)}")
        print(f"  Cache write: {_fmt(totals.cache_write)}")
        print(f"  Total:       {_fmt(totals.total)}")
        print(f"  Messages:    {_fmt(totals.messages)}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Show Claude Code token usage: daily totals and 5-minute rate window."
    )
    parser.add_argument(
        "--window", type=int, default=RATE_WINDOW_MINUTES,
        metavar="N", help=f"Rate window in minutes (default: {RATE_WINDOW_MINUTES})"
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    now = datetime.now(tz=timezone.utc)

    # Daily window: from midnight UTC
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    # Rate window
    rate_start = now - timedelta(minutes=args.window)

    daily = collect_usage(since=today_start)
    rate = collect_usage(since=rate_start)

    if RICH_AVAILABLE:
        console.print()
    _print_table("Today's usage", daily, "cyan")
    if RICH_AVAILABLE:
        console.print()
    _print_table(f"Last {args.window} minutes", rate, "yellow")
    if RICH_AVAILABLE:
        console.print()

    if rate.messages >= 8:
        msg = f"⚠  {rate.messages} messages in the last {args.window} min — approaching rate limit."
        if RICH_AVAILABLE:
            console.print(Text(msg, style="bold red"))
        else:
            print(msg)


if __name__ == "__main__":
    main()
