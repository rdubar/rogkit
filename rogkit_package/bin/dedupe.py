#!/usr/bin/env python3
"""Find duplicate files by size and hash under a directory tree."""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from ..settings import get_invoking_cwd
from .bytes import byte_size
from .hash import hash_file

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


@dataclass(frozen=True)
class DuplicateGroup:
    """A set of duplicate files sharing size and content hash."""

    digest: str
    size: int
    paths: tuple[Path, ...]


def _print_message(message: str, *, style: str | None = None) -> None:
    """Print with optional Rich styling and a plain fallback."""
    if RICH_AVAILABLE:
        console.print(Text(message, style=style) if style else message)
    else:
        print(message)


def iter_files(root: Path) -> list[Path]:
    """Return all regular files under *root* in deterministic order."""
    return sorted((path for path in root.rglob("*") if path.is_file()), key=lambda path: str(path).lower())


def find_duplicate_groups(root: Path, algorithm: str = DEFAULT_ALGO) -> list[DuplicateGroup]:
    """Group duplicate files by size first, then by content hash."""
    by_size: dict[int, list[Path]] = defaultdict(list)
    for path in iter_files(root):
        try:
            size = path.stat().st_size
        except OSError:
            continue
        by_size[size].append(path)

    groups: list[DuplicateGroup] = []
    for size, paths in by_size.items():
        if len(paths) < 2:
            continue
        by_hash: dict[str, list[Path]] = defaultdict(list)
        for path in paths:
            try:
                digest = hash_file(path, algorithm)
            except OSError:
                continue
            by_hash[digest].append(path)
        for digest, dup_paths in by_hash.items():
            if len(dup_paths) > 1:
                groups.append(
                    DuplicateGroup(
                        digest=digest,
                        size=size,
                        paths=tuple(sorted(dup_paths, key=lambda path: str(path).lower())),
                    )
                )

    groups.sort(key=lambda group: (-group.size, str(group.paths[0]).lower()))
    return groups


def find_empty_files(root: Path) -> list[Path]:
    """Return zero-byte files under *root*."""
    empty_files: list[Path] = []
    for path in iter_files(root):
        try:
            if path.stat().st_size == 0:
                empty_files.append(path)
        except OSError:
            continue
    return empty_files


def delete_empty_files(paths: list[Path], *, force: bool = False) -> int:
    """Delete zero-byte files, prompting unless force=True."""
    if not paths:
        _print_message("No empty files found.", style="yellow")
        return 0

    if not force:
        try:
            answer = input(f"Delete {len(paths)} empty file(s)? [y/N] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if answer != "y":
            _print_message("Skipped deleting empty files.", style="yellow")
            return 0

    deleted = 0
    for path in paths:
        try:
            path.unlink()
            deleted += 1
        except OSError:
            continue
    return deleted


def render_groups(groups: list[DuplicateGroup], *, plain: bool = False) -> None:
    """Render duplicate groups."""
    if not groups:
        _print_message("No duplicate files found.", style="yellow")
        return

    if RICH_AVAILABLE and not plain:
        table = Table(header_style="bold cyan", show_lines=False)
        table.add_column("Size", justify="right", no_wrap=True)
        table.add_column("Count", justify="right", no_wrap=True)
        table.add_column("Hash", no_wrap=True)
        table.add_column("Files", overflow="fold")
        for group in groups:
            table.add_row(
                byte_size(group.size),
                str(len(group.paths)),
                group.digest[:16],
                "\n".join(str(path) for path in group.paths),
            )
        console.print(table)
        return

    for index, group in enumerate(groups, start=1):
        print(f"Group {index}: {byte_size(group.size)} x {len(group.paths)} [{group.digest[:16]}]")
        for path in group.paths:
            print(f"  {path}")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Find duplicate files by size and hash under a directory tree.")
    parser.add_argument("path", nargs="?", default=".", help="Directory to scan (default: current directory)")
    parser.add_argument("--algo", choices=("md5", "sha1", "sha256", "sha512"), default=DEFAULT_ALGO, help=f"Hash algorithm (default: {DEFAULT_ALGO})")
    parser.add_argument("--delete-empty", action="store_true", help="Delete zero-byte files after confirmation")
    parser.add_argument("--force", action="store_true", help="Skip confirmation for --delete-empty")
    parser.add_argument("--plain", action="store_true", help="Plain text output")
    return parser.parse_args()


def main() -> int:
    """CLI entry point."""
    cwd = get_invoking_cwd()
    args = parse_args()

    root = Path(args.path).expanduser()
    if not root.is_absolute():
        root = cwd / root
    root = root.resolve()

    if not root.exists():
        print(f"error: path not found: {root}", file=sys.stderr)
        return 1
    if not root.is_dir():
        print(f"error: not a directory: {root}", file=sys.stderr)
        return 1

    if args.delete_empty:
        empty_files = find_empty_files(root)
        deleted = delete_empty_files(empty_files, force=args.force)
        _print_message(f"Deleted {deleted} empty file(s).", style="green" if deleted else "yellow")
        return 0

    groups = find_duplicate_groups(root, algorithm=args.algo)
    render_groups(groups, plain=args.plain)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
