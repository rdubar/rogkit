#!/usr/bin/env python3
"""Hash files or stdin with common digest algorithms."""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

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


DEFAULT_ALGO = "sha256"
ALGORITHMS = ("md5", "sha1", "sha256", "sha512")
CHUNK_SIZE = 1024 * 1024


def _print_message(message: str, *, style: str | None = None) -> None:
    """Print with optional Rich styling and a plain fallback."""
    if RICH_AVAILABLE:
        console.print(Text(message, style=style) if style else message)
    else:
        print(message)


def _build_hasher(algorithm: str) -> hashlib._Hash:
    """Return a hashlib hasher for the selected algorithm."""
    if algorithm not in ALGORITHMS:
        raise ValueError(f"Unsupported algorithm: {algorithm}")
    return hashlib.new(algorithm)


def hash_bytes(data: bytes, algorithm: str = DEFAULT_ALGO) -> str:
    """Return the hex digest for raw bytes."""
    hasher = _build_hasher(algorithm)
    hasher.update(data)
    return hasher.hexdigest()


def hash_file(path: Path, algorithm: str = DEFAULT_ALGO) -> str:
    """Return the hex digest for a file."""
    hasher = _build_hasher(algorithm)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK_SIZE), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def hash_stdin(algorithm: str = DEFAULT_ALGO) -> str:
    """Return the hex digest for bytes read from stdin."""
    hasher = _build_hasher(algorithm)
    stream = sys.stdin.buffer
    for chunk in iter(lambda: stream.read(CHUNK_SIZE), b""):
        hasher.update(chunk)
    return hasher.hexdigest()


def render_results(results: list[tuple[str, str]], *, plain: bool = False) -> None:
    """Render digest results in a compact table or plain output."""
    if RICH_AVAILABLE and not plain and len(results) > 1:
        table = Table(header_style="bold cyan", show_lines=False)
        table.add_column("Digest", style="green")
        table.add_column("Source", overflow="fold")
        for digest, source in results:
            table.add_row(digest, source)
        console.print(table)
        return

    for digest, source in results:
        print(f"{digest}  {source}")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Hash files or stdin with md5, sha1, sha256, or sha512.")
    parser.add_argument("paths", nargs="*", help="Files to hash (omit to read from stdin)")
    parser.add_argument(
        "--algo",
        choices=ALGORITHMS,
        default=DEFAULT_ALGO,
        help=f"Hash algorithm to use (default: {DEFAULT_ALGO})",
    )
    parser.add_argument("--plain", action="store_true", help="Plain text output")
    return parser.parse_args()


def main() -> int:
    """CLI entry point."""
    cwd = get_invoking_cwd()
    args = parse_args()

    results: list[tuple[str, str]] = []

    if args.paths:
        for raw_path in args.paths:
            path = Path(raw_path).expanduser()
            if not path.is_absolute():
                path = cwd / path
            path = path.resolve()
            if not path.exists():
                print(f"error: file not found: {path}", file=sys.stderr)
                return 1
            if not path.is_file():
                print(f"error: not a file: {path}", file=sys.stderr)
                return 1
            results.append((hash_file(path, args.algo), str(path)))
    else:
        try:
            if sys.stdin.isatty():
                print("error: provide at least one file or pipe data on stdin", file=sys.stderr)
                return 1
        except OSError:
            pass
        results.append((hash_stdin(args.algo), "<stdin>"))

    render_results(results, plain=args.plain)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
