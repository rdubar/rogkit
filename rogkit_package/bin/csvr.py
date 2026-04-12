"""
CSV viewer — renders a CSV file as a Rich table in the terminal.

Reads from a file or stdin. Auto-detects delimiter (comma, tab, semicolon, pipe).

Usage:
    csv file.csv                    # full table (up to default row limit)
    csv file.csv -n 50              # first 50 data rows
    csv file.csv -c name,email      # select columns by header name
    csv file.csv -s age             # sort by column
    csv file.csv -s age --desc      # sort descending
    cat file.csv | csv              # from stdin
    csv file.csv --no-header        # treat first row as data, not header
    csv file.csv -d '\\t'           # explicit delimiter
    csv file.csv --plain            # plain text, no Rich formatting
    csv file.csv --count            # show row count only
"""

from __future__ import annotations

import argparse
import csv
import sys
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

DEFAULT_ROW_LIMIT = 100
MAX_CELL_WIDTH = 60


def _truncate(value: str, max_len: int = MAX_CELL_WIDTH) -> str:
    return value if len(value) <= max_len else value[: max_len - 1] + "…"


def _detect_delimiter(sample: str) -> str:
    """Sniff the delimiter from a sample of CSV text."""
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t;|")
        return dialect.delimiter
    except csv.Error:
        return ","


def read_csv(
    source: Optional[str],
    *,
    delimiter: Optional[str] = None,
    has_header: bool = True,
) -> tuple[list[str], list[list[str]]]:
    """
    Read CSV from file or stdin.

    Returns (headers, rows) where headers is a list of column names
    and rows is a list of string lists.  If has_header is False,
    headers are generated as Col1, Col2, …
    """
    if source:
        with open(source, encoding="utf-8", newline="") as fh:
            raw = fh.read()
    else:
        raw = sys.stdin.read()

    if not raw.strip():
        return [], []

    sep = delimiter or _detect_delimiter(raw[:4096])
    reader = csv.reader(raw.splitlines(), delimiter=sep)
    all_rows = list(reader)

    if not all_rows:
        return [], []

    if has_header:
        headers = all_rows[0]
        data_rows = all_rows[1:]
    else:
        width = max(len(r) for r in all_rows)
        headers = [f"Col{i + 1}" for i in range(width)]
        data_rows = all_rows

    return headers, data_rows


def filter_columns(
    headers: list[str],
    rows: list[list[str]],
    columns: list[str],
) -> tuple[list[str], list[list[str]]]:
    """Keep only the named columns (case-insensitive)."""
    lower_cols = [c.lower() for c in columns]
    indices = [
        i for i, h in enumerate(headers) if h.lower() in lower_cols
    ]
    if not indices:
        raise ValueError(f"None of the requested columns found: {columns}")
    new_headers = [headers[i] for i in indices]
    new_rows = [[row[i] if i < len(row) else "" for i in indices] for row in rows]
    return new_headers, new_rows


def sort_rows(
    headers: list[str],
    rows: list[list[str]],
    sort_col: str,
    *,
    descending: bool = False,
) -> list[list[str]]:
    """Sort rows by a named column, attempting numeric sort where possible."""
    lower = sort_col.lower()
    indices = [i for i, h in enumerate(headers) if h.lower() == lower]
    if not indices:
        raise ValueError(f"Sort column not found: {sort_col!r}")
    idx = indices[0]

    def key(row: list[str]) -> tuple:
        val = row[idx] if idx < len(row) else ""
        try:
            return (0, float(val))
        except ValueError:
            return (1, val.lower())

    return sorted(rows, key=key, reverse=descending)


def render_table(
    headers: list[str],
    rows: list[list[str]],
    *,
    title: Optional[str] = None,
    plain: bool = False,
    truncate: bool = True,
) -> None:
    """Print the data as a Rich table or plain-text fallback."""
    if not headers and not rows:
        _print("(empty)", style="yellow")
        return

    max_len = MAX_CELL_WIDTH if truncate else None

    if RICH_AVAILABLE and not plain:
        table = Table(title=title, show_lines=False, header_style="bold cyan")
        for header in headers:
            table.add_column(header, overflow="fold")
        for row in rows:
            cells = [_truncate(row[i] if i < len(row) else "", max_len or 9999) for i in range(len(headers))]
            table.add_row(*cells)
        console.print(table)
    else:
        if title:
            print(title)
            print("-" * len(title))
        sep = "  "
        widths = [len(h) for h in headers]
        for row in rows:
            for i, h in enumerate(headers):
                cell = row[i] if i < len(row) else ""
                if max_len:
                    cell = _truncate(cell, max_len)
                widths[i] = max(widths[i], len(cell))
        header_line = sep.join(h.ljust(widths[i]) for i, h in enumerate(headers))
        print(header_line)
        print("-" * len(header_line))
        for row in rows:
            cells = [(row[i] if i < len(row) else "") for i in range(len(headers))]
            if max_len:
                cells = [_truncate(c, max_len) for c in cells]
            print(sep.join(c.ljust(widths[i]) for i, c in enumerate(cells)))


def _print(message: str, style: Optional[str] = None) -> None:
    if RICH_AVAILABLE:
        console.print(Text(message, style=style) if style else message)
    else:
        print(message)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Render a CSV file as a table in the terminal."
    )
    parser.add_argument("file", nargs="?", help="CSV file (omit to read from stdin)")
    parser.add_argument("-n", "--rows", type=int, default=DEFAULT_ROW_LIMIT,
                        metavar="N", help=f"Maximum rows to display (default {DEFAULT_ROW_LIMIT})")
    parser.add_argument("-c", "--columns", metavar="COL,...",
                        help="Comma-separated list of columns to show")
    parser.add_argument("-s", "--sort", metavar="COL",
                        help="Sort by this column")
    parser.add_argument("--desc", action="store_true",
                        help="Sort descending (use with -s)")
    parser.add_argument("-d", "--delimiter", metavar="CHAR",
                        help="Field delimiter (auto-detected by default)")
    parser.add_argument("--no-header", action="store_true",
                        help="Treat first row as data, not a header")
    parser.add_argument("--plain", action="store_true",
                        help="Plain text output, no Rich formatting")
    parser.add_argument("--count", action="store_true",
                        help="Print row count and exit")
    args = parser.parse_args()

    if not args.file and sys.stdin.isatty():
        parser.print_help()
        return 0

    delimiter = args.delimiter.replace("\\t", "\t") if args.delimiter else None

    try:
        headers, rows = read_csv(args.file, delimiter=delimiter, has_header=not args.no_header)
    except FileNotFoundError:
        _print(f"error: file not found: {args.file}", style="bold red")
        return 1
    except Exception as exc:
        _print(f"error: {exc}", style="bold red")
        return 1

    if not headers and not rows:
        _print("(empty file)", style="yellow")
        return 0

    if args.count:
        print(f"{len(rows)} rows, {len(headers)} columns")
        return 0

    if args.columns:
        requested = [c.strip() for c in args.columns.split(",")]
        try:
            headers, rows = filter_columns(headers, rows, requested)
        except ValueError as exc:
            _print(f"error: {exc}", style="bold red")
            return 1

    if args.sort:
        try:
            rows = sort_rows(headers, rows, args.sort, descending=args.desc)
        except ValueError as exc:
            _print(f"error: {exc}", style="bold red")
            return 1

    total = len(rows)
    rows = rows[: args.rows]
    title = args.file or "<stdin>"
    if total > args.rows:
        title += f" (showing {args.rows} of {total} rows)"

    render_table(headers, rows, title=title, plain=args.plain)

    if total > args.rows:
        _print(f"  {total - args.rows} more rows hidden — use -n to show more", style="dim")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
