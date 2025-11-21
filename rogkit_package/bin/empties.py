#!/usr/bin/env python3
"""
Empty folder and sparse directory finder.

By default scans from the current working directory. Use --directory to override.
Matched folders are deleted only when --confirm is supplied (otherwise a dry run).
"""

import argparse
import os
import time
from pathlib import Path
from typing import List, Tuple

from .delete import safe_delete


def find_sparse_folders(directory: Path, file_limit: int) -> Tuple[List[Path], int, int]:
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
    """Print summary of matching folders and scan statistics."""
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


def delete_matches(folders: List[Path], force: bool) -> None:
    """Delete the supplied folders using safe_delete."""
    for folder in folders:
        safe_delete(str(folder), force=force)


def main() -> None:
    """CLI entry point for empty/sparse folder finder."""
    parser = argparse.ArgumentParser(
        description=(
            "Identify folders with few entries (default: empty) or only .pyc files. "
            "By default performs a dry run from the current working directory."
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
        "--confirm",
        action="store_true",
        help="Delete matching folders. Without this flag the command is read-only.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Permanently delete matching folders (requires --confirm).",
    )
    parser.add_argument(
        "-r",
        "--raw",
        action="store_true",
        help="Print matching folders only (one per line) for easy piping; suppresses summaries.",
    )

    args = parser.parse_args()

    if args.force and not args.confirm:
        parser.error("--force requires --confirm")

    root = Path(args.directory).expanduser().resolve()
    if not root.exists():
        parser.error(f"Directory not found: {root}")
    if not root.is_dir():
        parser.error(f"Not a directory: {root}")

    start = time.time()
    matches, directory_count, file_count = find_sparse_folders(root, args.number)
    elapsed = time.time() - start

    if not args.raw:
        print(f"Scanning {root}")
        print_summary(matches, directory_count, file_count, args.number, elapsed)

    if not matches:
        return

    if args.raw:
        for folder in matches:
            print(folder)
        if not args.confirm:
            return

    if args.confirm:
        delete_matches(matches, force=args.force)
    else:
        print("Dry run complete. Re-run with --confirm to delete matching folders.")


if __name__ == "__main__":
    main()
