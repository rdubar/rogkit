#!/usr/bin/env python3
"""Find duplicate files by size and hash under a directory tree."""

from __future__ import annotations

import argparse
import fnmatch
import shutil
import subprocess
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
DEFAULT_EXCLUDE_PATTERNS = ("__init__.py",)


@dataclass(frozen=True)
class DuplicateGroup:
    """A set of duplicate files sharing size and content hash."""

    digest: str
    size: int
    paths: tuple[Path, ...]


@dataclass(frozen=True)
class ScanConfig:
    """File discovery configuration for dedupe scans."""

    ignore_patterns: tuple[str, ...]
    engine: str = "auto"
    use_gitignore: bool = False


def _print_message(message: str, *, style: str | None = None) -> None:
    """Print with optional Rich styling and a plain fallback."""
    if RICH_AVAILABLE:
        console.print(Text(message, style=style) if style else message)
    else:
        print(message)


def _normalize_ignore_patterns(
    patterns: list[str] | None = None,
    *,
    include_defaults: bool = True,
) -> tuple[str, ...]:
    """Return normalized ignore globs."""
    merged: list[str] = list(DEFAULT_EXCLUDE_PATTERNS if include_defaults else ())
    if patterns:
        merged.extend(pattern.strip() for pattern in patterns if pattern and pattern.strip())
    deduped: list[str] = []
    seen: set[str] = set()
    for pattern in merged:
        if pattern not in seen:
            seen.add(pattern)
            deduped.append(pattern)
    return tuple(deduped)


def _is_ignored(path: Path, root: Path, patterns: tuple[str, ...]) -> bool:
    """Return True when a path matches one of the ignore patterns."""
    if not patterns:
        return False
    rel = str(path.relative_to(root))
    return any(
        fnmatch.fnmatch(path.name, pattern)
        or fnmatch.fnmatch(rel, pattern)
        or fnmatch.fnmatch(str(path), pattern)
        for pattern in patterns
    )


def _iter_files_python(root: Path, ignore_patterns: tuple[str, ...]) -> list[Path]:
    """Discover files with pathlib recursion."""
    return sorted(
        (
            path
            for path in root.rglob("*")
            if path.is_file() and not _is_ignored(path, root, ignore_patterns)
        ),
        key=lambda path: str(path).lower(),
    )


def _iter_files_fd(root: Path, ignore_patterns: tuple[str, ...], *, use_gitignore: bool) -> list[Path] | None:
    """Discover files with fd, optionally respecting .gitignore."""
    if shutil.which("fd") is None:
        return None
    cmd = ["fd", "-t", "f", "-a", "-H"]
    if not use_gitignore:
        cmd.append("-I")
    for pattern in ignore_patterns:
        cmd.extend(["--exclude", pattern])
    cmd.extend([".", str(root)])
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return None
    return sorted((Path(line.strip()) for line in result.stdout.splitlines() if line.strip()), key=lambda path: str(path).lower())


def iter_files(root: Path, config: ScanConfig) -> tuple[list[Path], str]:
    """Return regular files under *root* and the engine used."""
    if config.engine in {"auto", "fd"}:
        fd_results = _iter_files_fd(root, config.ignore_patterns, use_gitignore=config.use_gitignore)
        if fd_results is not None:
            return fd_results, "fd (preferred by auto)"
        if config.engine == "fd":
            return [], "fd"
    return _iter_files_python(root, config.ignore_patterns), "python"


def find_duplicate_groups(
    root: Path,
    algorithm: str = DEFAULT_ALGO,
    *,
    config: ScanConfig | None = None,
) -> tuple[list[DuplicateGroup], str, int]:
    """Group duplicate files by size first, then by content hash."""
    config = config or ScanConfig(ignore_patterns=_normalize_ignore_patterns())
    files, engine_used = iter_files(root, config)
    by_size: dict[int, list[Path]] = defaultdict(list)
    for path in files:
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
    return groups, engine_used, len(files)


def find_empty_files(root: Path, *, config: ScanConfig | None = None) -> tuple[list[Path], str, int]:
    """Return zero-byte files under *root*."""
    config = config or ScanConfig(ignore_patterns=_normalize_ignore_patterns())
    files, engine_used = iter_files(root, config)
    empty_files: list[Path] = []
    for path in files:
        try:
            if path.stat().st_size == 0:
                empty_files.append(path)
        except OSError:
            continue
    return empty_files, engine_used, len(files)


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


def render_summary(
    *,
    root: Path,
    engine_used: str,
    scanned_files: int,
    groups: list[DuplicateGroup] | None = None,
    empty_files: list[Path] | None = None,
    ignore_patterns: tuple[str, ...] = (),
) -> None:
    """Render a concise verbose summary."""
    duplicate_groups = groups or []
    duplicate_files = sum(len(group.paths) for group in duplicate_groups)
    wasted_bytes = sum(group.size * (len(group.paths) - 1) for group in duplicate_groups)
    empty_count = len(empty_files or [])
    _print_message(
        f"[dedupe] root={root} engine={engine_used} scanned={scanned_files:,} "
        f"groups={len(duplicate_groups):,} dup_files={duplicate_files:,} "
        f"wasted={byte_size(wasted_bytes)} empty={empty_count:,}",
        style="dim",
    )
    if ignore_patterns:
        _print_message(
            f"[dedupe] ignore={', '.join(ignore_patterns)}",
            style="dim",
        )


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Find duplicate files by size and hash under a directory tree.")
    parser.add_argument("path", nargs="?", default=".", help="Directory to scan (default: current directory)")
    parser.add_argument("--algo", choices=("md5", "sha1", "sha256", "sha512"), default=DEFAULT_ALGO, help=f"Hash algorithm (default: {DEFAULT_ALGO})")
    parser.add_argument("--delete-empty", action="store_true", help="Delete zero-byte files after confirmation")
    parser.add_argument("--force", action="store_true", help="Skip confirmation for --delete-empty")
    parser.add_argument("--exclude", action="append", default=[], help="Glob pattern to ignore (can be repeated)")
    parser.add_argument("--no-default-excludes", action="store_true", help="Do not exclude default boilerplate files like __init__.py")
    parser.add_argument("--gitignore", action="store_true", help="Respect .gitignore when using fd discovery")
    parser.add_argument(
        "--engine",
        choices=("auto", "fd", "python"),
        default="auto",
        help="Discovery engine (default: auto, which prefers fd and falls back to python)",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Show scan summary and active ignore patterns")
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

    config = ScanConfig(
        ignore_patterns=_normalize_ignore_patterns(
            args.exclude,
            include_defaults=not args.no_default_excludes,
        ),
        engine=args.engine,
        use_gitignore=args.gitignore,
    )

    if args.delete_empty:
        empty_files, engine_used, scanned_files = find_empty_files(root, config=config)
        if args.verbose:
            render_summary(
                root=root,
                engine_used=engine_used,
                scanned_files=scanned_files,
                empty_files=empty_files,
                ignore_patterns=config.ignore_patterns,
            )
        deleted = delete_empty_files(empty_files, force=args.force)
        _print_message(f"Deleted {deleted} empty file(s).", style="green" if deleted else "yellow")
        return 0

    groups, engine_used, scanned_files = find_duplicate_groups(root, algorithm=args.algo, config=config)
    if args.verbose:
        render_summary(
            root=root,
            engine_used=engine_used,
            scanned_files=scanned_files,
            groups=groups,
            ignore_patterns=config.ignore_patterns,
        )
    render_groups(groups, plain=args.plain)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
