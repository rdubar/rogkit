#!/usr/bin/env python3
"""Convert timestamps between epoch seconds, local time, and UTC."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import UTC, datetime

from ..settings import get_invoking_cwd

try:
    from rich.console import Console
    from rich.table import Table
    from rich.text import Text

    console = Console()
    RICH_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover
    console = None  # type: ignore[assignment]
    RICH_AVAILABLE = False


@dataclass(frozen=True)
class TimestampInfo:
    """Normalized timestamp information."""

    epoch: int
    utc_iso: str
    local_iso: str


def _print_message(message: str, *, style: str | None = None) -> None:
    """Print with optional Rich styling and a plain fallback."""
    if RICH_AVAILABLE:
        console.print(Text(message, style=style) if style else message)
    else:
        print(message)


def _read_value(value: str | None) -> str:
    """Read a positional value or fall back to stdin."""
    if value is not None:
        return value
    try:
        if sys.stdin.isatty():
            raise ValueError("Provide a timestamp or pipe data on stdin.")
    except OSError:
        pass
    data = sys.stdin.read().strip()
    if not data:
        raise ValueError("No input provided.")
    return data


def _parse_input(value: str) -> datetime:
    """Parse epoch seconds or an ISO-like datetime string."""
    stripped = value.strip()
    try:
        epoch = float(stripped)
    except ValueError:
        epoch = None

    if epoch is not None:
        try:
            return datetime.fromtimestamp(epoch, UTC)
        except (OverflowError, OSError, ValueError) as exc:
            raise ValueError(f"Invalid epoch timestamp: {value}") from exc

    iso_value = stripped.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(iso_value)
    except ValueError as exc:
        raise ValueError(f"Invalid timestamp: {value}") from exc
    if dt.tzinfo is None:
        return dt.astimezone()
    return dt


def convert_timestamp(value: str) -> TimestampInfo:
    """Return UTC, local, and epoch representations of a timestamp."""
    dt = _parse_input(value)
    local_dt = dt.astimezone()
    utc_dt = dt.astimezone(UTC)
    return TimestampInfo(
        epoch=int(utc_dt.timestamp()),
        utc_iso=utc_dt.isoformat().replace("+00:00", "Z"),
        local_iso=local_dt.isoformat(),
    )


def render_timestamp(info: TimestampInfo, *, plain: bool = False) -> None:
    """Render timestamp conversions."""
    if RICH_AVAILABLE and not plain:
        table = Table(header_style="bold cyan", show_lines=False)
        table.add_column("Field", style="bold")
        table.add_column("Value", overflow="fold")
        table.add_row("epoch", str(info.epoch))
        table.add_row("utc", info.utc_iso)
        table.add_row("local", info.local_iso)
        console.print(table)
        return

    print(f"epoch: {info.epoch}")
    print(f"utc: {info.utc_iso}")
    print(f"local: {info.local_iso}")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Convert timestamps between epoch seconds, ISO8601, local time, and UTC."
    )
    parser.add_argument("value", nargs="?", help="Epoch seconds or ISO-like datetime (or pipe on stdin)")
    parser.add_argument("--plain", action="store_true", help="Plain text output")
    return parser.parse_args()


def main() -> int:
    """CLI entry point."""
    _ = get_invoking_cwd()
    args = parse_args()
    try:
        value = _read_value(args.value)
        info = convert_timestamp(value)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    render_timestamp(info, plain=args.plain)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
