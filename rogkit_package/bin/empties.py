#!/usr/bin/env python3
"""
Empty folder and sparse directory finder.

By default scans from the current working directory. Use --directory to override.
Outputs matching folders (one per line) for easy piping; use -v for summaries.
"""

import argparse
import fnmatch
import os
import time
from pathlib import Path
from typing import List, Tuple

try:  # Optional rich dependency for nicer verbose output
    from rich.console import Console
    from rich.table import Table
    from rich.text import Text

    console = Console()
    RICH_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover
    console = None
    RICH_AVAILABLE = False


def _is_ignored(path: Path, ignore_patterns: List[str]) -> bool:
    return any(path.match(pattern) or fnmatch.fnmatch(path.name, pattern) for pattern in ignore_patterns)


def find_sparse_folders(directory: Path, file_limit: int, ignore_patterns: List[str]) -> Tuple[List[Path], int, int]:
    """
    Recursively check directory for folders whose total entries (files + subdirs)
    are less than or equal to file_limit, or which contain only .pyc files.
    """
    matches: List[Path] = []
    directory_count = 0
    file_count = 0

    for root, dirs, files in os.walk(directory):
        directory_count += 1
        file_count += len(files)
        current = Path(root)

        # Skip ignored directories and prevent traversal into them
        dirs[:] = [d for d in dirs if not _is_ignored(Path(root) / d, ignore_patterns)]

        if _is_ignored(current, ignore_patterns):
            continue

        total_entries = len(files) + len(dirs)
        if total_entries <= file_limit:
            if current != directory:
                matches.append(current)
            continue

        if files and all(name.endswith(".pyc") for name in files):
            if current != directory:
                matches.append(current)

    return matches, directory_count, file_count


def print_summary(folders: List[Path], directory_count: int, file_count: int, file_limit: int, elapsed: float) -> None:
    """Verbose summary with optional rich table."""
    if RICH_AVAILABLE:
        headline = (
            f"Found {len(folders)} matching folder(s) (entry limit <= {file_limit}) "
            f"from {file_count:,} files across {directory_count:,} directories "
            f"in {elapsed:.2f}s."
        )
        table = Table(title=headline, box=None, pad_edge=False)
        table.add_column("#", justify="right", style="dim", no_wrap=True)
        table.add_column("Folder", style="white")
        for idx, folder in enumerate(folders, start=1):
            table.add_row(str(idx), str(folder))
        console.print(table)
    else:
        if folders:
            print(f"Found {len(folders)} matching folders (limit <= {file_limit}).")
            for folder in folders:
                print(f"  {folder}")
        else:
            print("No matching directories found.")

        print(
            f"Checked {file_count:,} files across {directory_count:,} directories "
            f"in {elapsed:.2f} seconds."
        )


def main() -> None:
    """CLI entry point for empty/sparse folder finder."""
    parser = argparse.ArgumentParser(
        description=(
            "Identify folders with few entries (default: empty) or only .pyc files. "
            "Outputs matching folders one per line for piping into other tools."
        )
    )
    parser.add_argument(
        "-d",
        "--directory",
        type=str,
        default=".",
        help="Directory to search (default: current working directory).",
    )
    parser.add_argument(
        "-n",
        "--number",
        type=int,
        default=0,
        help="Maximum number of entries allowed in a folder before it is flagged.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show summary and table (uses rich when installed).",
    )
    parser.add_argument(
        "--ignore",
        action="append",
        default=[],
        help="Glob pattern to ignore (can be repeated).",
    )

    args = parser.parse_args()

    root = Path(args.directory).expanduser().resolve()
    if not root.exists():
        parser.error(f"Directory not found: {root}")
    if not root.is_dir():
        parser.error(f"Not a directory: {root}")

    start = time.time()
    ignores = [pattern.strip() for pattern in args.ignore if pattern and pattern.strip()]
    matches, directory_count, file_count = find_sparse_folders(root, args.number, ignores)
    elapsed = time.time() - start

    if args.verbose:
        print_summary(matches, directory_count, file_count, args.number, elapsed)

    for folder in matches:
        print(folder)


if __name__ == "__main__":
    main()
