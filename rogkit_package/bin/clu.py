#!/usr/bin/env python3
"""Claude Code token usage — daily totals and 5-minute rate window.

TODO: experimental — numbers may be unreliable. Verify against Anthropic's
official usage reporting before trusting output.
"""

import argparse
import glob
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path

from ..settings import get_invoking_cwd  # noqa: F401  (convention)

try:
    from rich.console import Console
    from rich.table import Table
    from rich.text import Text
    from rich.bar import Bar

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


def collect_hourly(since: datetime) -> dict[int, TokenTotals]:
    """Return a dict of hour (0-23 local) → TokenTotals for today."""
    by_hour: dict[int, TokenTotals] = defaultdict(TokenTotals)
    pattern = str(CLAUDE_PROJECTS_DIR / "**" / "*.jsonl")
    local_tz = datetime.now().astimezone().tzinfo
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
                            hour = ts.astimezone(local_tz).hour
                            by_hour[hour].add(msg["usage"])
                    except (json.JSONDecodeError, KeyError):
                        continue
        except OSError:
            continue
    return by_hour


def _fmt(n: int) -> str:
    return f"{n:,}"


def _print_brief(daily: TokenTotals, rate: TokenTotals, window: int) -> None:
    warn = " ⚠" if rate.messages >= 8 else ""
    line = (
        f"Today: {_fmt(daily.total)} tokens / {daily.messages} msgs  |  "
        f"Last {window}m: {_fmt(rate.total)} tokens / {rate.messages} msgs{warn}"
    )
    if RICH_AVAILABLE:
        style = "bold red" if rate.messages >= 8 else "cyan"
        console.print(Text(line, style=style))
    else:
        print(line)


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


def _print_hourly(by_hour: dict[int, TokenTotals], current_hour: int) -> None:
    if not by_hour:
        return
    max_msgs = max((t.messages for t in by_hour.values()), default=1)
    if RICH_AVAILABLE:
        table = Table(title="[bold green]Hourly activity (today)[/]", box=None, pad_edge=True, show_edge=False)
        table.add_column("Hour", style="dim", min_width=6)
        table.add_column("Msgs", justify="right", min_width=5)
        table.add_column("Activity", min_width=30)
        for hour in range(current_hour + 1):
            t = by_hour.get(hour, TokenTotals())
            bar_width = int((t.messages / max_msgs) * 28) if max_msgs else 0
            bar = "█" * bar_width
            marker = " ◀" if hour == current_hour else ""
            table.add_row(f"{hour:02d}:00", str(t.messages), f"[cyan]{bar}[/]{marker}")
        console.print(table)
    else:
        print("\nHourly activity (today)")
        for hour in range(current_hour + 1):
            t = by_hour.get(hour, TokenTotals())
            bar = "█" * int((t.messages / max_msgs) * 20) if max_msgs else ""
            print(f"  {hour:02d}:00  {t.messages:3d}  {bar}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Show Claude Code token usage: daily totals and 5-minute rate window."
    )
    parser.add_argument(
        "-b", "--brief", action="store_true",
        help="One-line summary"
    )
    parser.add_argument(
        "-x", "--extra", action="store_true",
        help="Show hourly activity breakdown"
    )
    parser.add_argument(
        "--window", type=int, default=RATE_WINDOW_MINUTES,
        metavar="N", help=f"Rate window in minutes (default: {RATE_WINDOW_MINUTES})"
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    now = datetime.now(tz=timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    rate_start = now - timedelta(minutes=args.window)

    daily = collect_usage(since=today_start)
    rate = collect_usage(since=rate_start)

    if args.brief:
        _print_brief(daily, rate, args.window)
        return

    if RICH_AVAILABLE:
        console.print()
    _print_table("Today's usage", daily, "cyan")
    if RICH_AVAILABLE:
        console.print()
    _print_table(f"Last {args.window} minutes", rate, "yellow")

    if rate.messages >= 8:
        msg = f"⚠  {rate.messages} messages in the last {args.window} min — approaching rate limit."
        if RICH_AVAILABLE:
            console.print()
            console.print(Text(msg, style="bold red"))
        else:
            print(msg)

    if args.extra:
        local_hour = datetime.now().hour
        by_hour = collect_hourly(since=today_start)
        if RICH_AVAILABLE:
            console.print()
        _print_hourly(by_hour, local_hour)

    if RICH_AVAILABLE:
        console.print()


if __name__ == "__main__":
    main()
