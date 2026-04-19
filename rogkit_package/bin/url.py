#!/usr/bin/env python3
"""Encode, decode, parse, and normalize URLs or query strings."""

from __future__ import annotations

import argparse
import sys
from urllib.parse import parse_qsl, quote, unquote, urlencode, urlparse, urlunparse

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
            raise ValueError("Provide a value or pipe data on stdin.")
    except OSError:
        pass
    data = sys.stdin.read().strip()
    if not data:
        raise ValueError("No input provided.")
    return data


def encode_value(value: str, *, plus: bool = False) -> str:
    """Percent-encode a string."""
    safe = "" if plus else "/"
    encoded = quote(value, safe=safe)
    return encoded.replace("%20", "+") if plus else encoded


def decode_value(value: str, *, plus: bool = False) -> str:
    """Percent-decode a string."""
    return unquote(value.replace("+", "%20")) if plus else unquote(value)


def parse_url(value: str) -> dict[str, object]:
    """Return parsed URL components and query items."""
    parsed = urlparse(value)
    query_items = parse_qsl(parsed.query, keep_blank_values=True)
    return {
        "scheme": parsed.scheme,
        "netloc": parsed.netloc,
        "path": parsed.path,
        "params": parsed.params,
        "query": parsed.query,
        "fragment": parsed.fragment,
        "query_items": query_items,
    }


def normalize_url(value: str, *, sort_query: bool = True) -> str:
    """Normalize a URL by lowercasing scheme/host and optionally sorting query params."""
    parsed = urlparse(value)
    query = parsed.query
    if sort_query:
        query = urlencode(sorted(parse_qsl(parsed.query, keep_blank_values=True)))
    # Rebuild netloc: lowercase only hostname, preserve credentials and port casing.
    host = (parsed.hostname or "").lower()
    netloc = f"{host}:{parsed.port}" if parsed.port else host
    if parsed.username is not None:
        userinfo = parsed.username
        if parsed.password is not None:
            userinfo = f"{userinfo}:{parsed.password}"
        netloc = f"{userinfo}@{netloc}"
    return urlunparse(
        (
            parsed.scheme.lower(),
            netloc,
            parsed.path or "/",
            parsed.params,
            query,
            parsed.fragment,
        )
    )


def render_parsed(parsed: dict[str, object], *, plain: bool = False) -> None:
    """Render parsed URL components."""
    query_items = parsed["query_items"]
    if RICH_AVAILABLE and not plain:
        table = Table(header_style="bold cyan", show_lines=False)
        table.add_column("Field", style="bold")
        table.add_column("Value", overflow="fold")
        for key in ("scheme", "netloc", "path", "params", "query", "fragment"):
            table.add_row(key, str(parsed[key]))
        if query_items:
            for key, value in query_items:  # type: ignore[misc]
                table.add_row("query_item", f"{key}={value}")
        console.print(table)
        return

    for key in ("scheme", "netloc", "path", "params", "query", "fragment"):
        print(f"{key}: {parsed[key]}")
    for key, value in query_items:  # type: ignore[misc]
        print(f"query_item: {key}={value}")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Encode, decode, parse, and normalize URLs or query strings.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    encode_parser = subparsers.add_parser("encode", help="Percent-encode text")
    encode_parser.add_argument("value", nargs="?", help="Value to encode (or pipe on stdin)")
    encode_parser.add_argument("--plus", action="store_true", help="Encode spaces as +")

    decode_parser = subparsers.add_parser("decode", help="Percent-decode text")
    decode_parser.add_argument("value", nargs="?", help="Value to decode (or pipe on stdin)")
    decode_parser.add_argument("--plus", action="store_true", help="Treat + as space")

    parse_parser = subparsers.add_parser("parse", help="Parse a URL into components")
    parse_parser.add_argument("value", nargs="?", help="URL to parse (or pipe on stdin)")
    parse_parser.add_argument("--plain", action="store_true", help="Plain text output")

    normalize_parser = subparsers.add_parser("normalize", help="Normalize a URL")
    normalize_parser.add_argument("value", nargs="?", help="URL to normalize (or pipe on stdin)")
    normalize_parser.add_argument("--keep-query-order", action="store_true", help="Preserve original query order")

    return parser.parse_args()


def main() -> int:
    """CLI entry point."""
    _ = get_invoking_cwd()
    args = parse_args()

    try:
        value = _read_value(getattr(args, "value", None))
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.command == "encode":
        print(encode_value(value, plus=args.plus))
        return 0
    if args.command == "decode":
        print(decode_value(value, plus=args.plus))
        return 0
    if args.command == "parse":
        render_parsed(parse_url(value), plain=args.plain)
        return 0
    if args.command == "normalize":
        print(normalize_url(value, sort_query=not args.keep_query_order))
        return 0

    print(f"error: unknown command: {args.command}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
