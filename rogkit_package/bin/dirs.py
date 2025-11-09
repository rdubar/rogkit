"""
Directory size calculator and analyzer.

Scans a directory tree (default: the current working directory) and reports
the largest subdirectories by total size. Supports substring filtering,
depth limits, and optional inclusion of hidden paths.
"""

import argparse
import os
import sys
from collections import defaultdict
from pathlib import Path
from time import perf_counter
from typing import DefaultDict, Optional

from .bytes import byte_size


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="List the largest directories under the given root."
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Root directory to analyze (default: current working directory).",
    )
    parser.add_argument(
        "-n",
        "--limit",
        type=int,
        default=10,
        help="Number of directories to display (default: 10).",
    )
    parser.add_argument(
        "-d",
        "--depth",
        type=int,
        default=1,
        help=(
            "Maximum depth (relative to the root) to include. "
            "Use 1 for direct children (default) and -1 for all levels."
        ),
    )
    parser.add_argument(
        "-s",
        "--search",
        help="Filter directories by case-insensitive substring match.",
    )
    parser.add_argument(
        "--include-hidden",
        action="store_true",
        help="Include hidden files and directories (names beginning with '.').",
    )
    args = parser.parse_args(argv)

    if args.limit <= 0:
        parser.error("--limit must be positive")
    if args.depth == 0 or args.depth < -1:
        parser.error("--depth must be -1 (all levels) or >= 1")

    return args


def collect_directory_sizes(root: Path, include_hidden: bool):
    root = root.resolve()
    dir_sizes: DefaultDict[Path, int] = defaultdict(int)
    total_files = 0
    errors = []

    for dirpath_str, dirnames, filenames in os.walk(root):
        dirpath = Path(dirpath_str)
        if not include_hidden:
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
            filenames = [name for name in filenames if not name.startswith(".")]

        for filename in filenames:
            total_files += 1
            file_path = dirpath / filename
            try:
                file_size = file_path.stat().st_size
            except OSError as exc:
                errors.append(f"{file_path}: {exc}")
                continue

            current = dirpath
            while True:
                dir_sizes[current] += file_size
                if current == root:
                    break
                current = current.parent

    dir_sizes.setdefault(root, 0)
    return dir_sizes, total_files, errors


def prepare_entries(dir_sizes, root: Path, depth: int, search: Optional[str]):
    search_term = search.lower() if search else None
    entries = []

    for path, size in dir_sizes.items():
        if path == root:
            continue

        try:
            relative = path.relative_to(root)
        except ValueError:
            # Should not happen, but skip gracefully if it does.
            continue

        relative_depth = len(relative.parts)
        if depth >= 0 and relative_depth > depth:
            continue

        display_path = str(relative) or "."
        if search_term and search_term not in display_path.lower():
            continue

        entries.append((path, display_path, size))

    entries.sort(key=lambda item: item[2], reverse=True)
    return entries


def main(argv=None):
    args = parse_args(argv)
    root = Path(args.path).expanduser()

    if not root.exists():
        print(f"Path not found: {root}", file=sys.stderr)
        return 1
    if not root.is_dir():
        print(f"Not a directory: {root}", file=sys.stderr)
        return 1

    root = root.resolve()
    print(f"Scanning {root}")
    start_time = perf_counter()
    dir_sizes, total_files, errors = collect_directory_sizes(root, args.include_hidden)
    elapsed = perf_counter() - start_time
    total_size = dir_sizes[root]

    entries = prepare_entries(dir_sizes, root, args.depth, args.search)
    filtered_total = sum(size for _, _, size in entries)
    limit = min(args.limit, len(entries))

    if limit:
        depth_label = "all levels" if args.depth == -1 else f"depth ≤ {args.depth}"
        print(f"\nTop {limit} directories ({depth_label}) under {root}:")
        print(f"{'Rank':>4} {'Size':>10} {'Share':>7} Path")
        for idx, (_, display_path, size) in enumerate(entries[:limit], start=1):
            share = (size / total_size * 100) if total_size else 0.0
            print(f"{idx:>4} {byte_size(size):>10} {share:>6.1f}% {display_path}")
    else:
        if args.search:
            print("No directories matched the provided search term.")
        else:
            print("No directories found under the specified root.")

    print(
        f"\nTotal size: {byte_size(total_size)} "
        f"across {len(dir_sizes):,} directories and {total_files:,} files "
        f"in {elapsed:.2f} seconds"
    )
    if args.search:
        print(f"Filtered total: {byte_size(filtered_total)} ({len(entries)} directories)")

    if errors:
        shown = min(5, len(errors))
        print(f"\nEncountered {len(errors)} errors while reading files (showing {shown}):")
        for error in errors[:shown]:
            print(f"  - {error}")
        if len(errors) > shown:
            print("  (showing first few only)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
