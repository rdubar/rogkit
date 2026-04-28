#!/usr/bin/env python3
"""
Empty folder and sparse directory finder.

By default scans from the current working directory. Use --directory to override.
Outputs matching folders (one per line) for easy piping; use -v for summaries.
"""

import argparse
import fnmatch
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Tuple

try:  # Optional rich dependency for nicer verbose output
    from rich.console import Console
    from rich.table import Table

    console = Console()
    RICH_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover
    console = None
    RICH_AVAILABLE = False


def _is_ignored(path: Path, ignore_patterns: List[str]) -> bool:
    return any(path.match(pattern) or fnmatch.fnmatch(path.name, pattern) for pattern in ignore_patterns)


def _run_fd_for_empties(root: Path, ignore_patterns: List[str], file_limit: int, include_pyc_only: bool) -> List[Path] | None:
    """
    Use fd to list directories quickly, then post-filter for empties.
    Only used when file_limit == 0.
    """
    if shutil.which("fd") is None:
        return None

    # fd only finds truly empty dirs; emulate file_limit by filtering count==0
    if file_limit != 0:
        return None

    # Pattern "." matches anything; path is the root to search.
    # -H to include hidden, -I to ignore .gitignore
    cmd = ["fd", "-H", "-I", "--type", "d", "--absolute-path"]
    for pattern in ignore_patterns:
        cmd.extend(["--exclude", pattern])
    cmd.extend([".", str(root)])

    result = subprocess.run(
        cmd,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        sys.stderr.write(f"fd scan failed (exit {result.returncode}): {result.stderr.strip()}\n")
        return None
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    paths: List[Path] = []
    for line in lines:
        path = Path(line)
        if path == root:
            continue
        try:
            entries = list(path.iterdir())
        except OSError:
            continue

        # Match python logic: empty OR only .pyc files (opt-in), no subdirs
        if not entries:
            paths.append(path)
            continue

        files = [p for p in entries if p.is_file()]
        dirs = [p for p in entries if p.is_dir()]
        if include_pyc_only and not dirs and files and all(p.name.endswith(".pyc") for p in files):
            paths.append(path)
    return paths


def find_sparse_folders(
    directory: Path,
    file_limit: int,
    ignore_patterns: List[str],
    include_pyc_only: bool,
) -> Tuple[List[Path], int, int]:
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

        if include_pyc_only and files and not dirs and all(name.endswith(".pyc") for name in files):
            if current != directory:
                matches.append(current)

    return matches, directory_count, file_count


def print_summary(folders: List[Path], directory_count: int, file_count: int, file_limit: int, elapsed: float, engine: str) -> None:
    """Verbose summary with optional rich table."""
    if RICH_AVAILABLE:
        headline = (
            f"Found {len(folders)} matching folder(s) (entry limit <= {file_limit}) "
            f"from {file_count:,} files across {directory_count:,} directories "
            f"in {elapsed:.2f}s. [engine: {engine}]"
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
            f"in {elapsed:.2f} seconds. [engine: {engine}]"
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
        "--include-pyc",
        action="store_true",
        help="Also flag directories that contain only .pyc files (no subdirs).",
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
    parser.add_argument(
        "--engine",
        choices=["auto", "fd", "python"],
        default="auto",
        help="Engine to use: auto prefers fd when available (limit=0) else python.",
    )

    args = parser.parse_args()

    root = Path(args.directory).expanduser().resolve()
    if not root.exists():
        parser.error(f"Directory not found: {root}")
    if not root.is_dir():
        parser.error(f"Not a directory: {root}")

    start = time.time()
    ignores = [pattern.strip() for pattern in args.ignore if pattern and pattern.strip()]
    matches: List[Path] = []
    directory_count = 0
    file_count = 0
    engine_used = "python"

    use_fd = args.engine in {"auto", "fd"} and args.number == 0
    fd_results = _run_fd_for_empties(root, ignores, args.number, args.include_pyc) if use_fd else None

    if fd_results is not None:
        matches = fd_results
        engine_used = "fd"
    else:
        if use_fd:
            if shutil.which("fd") is None:
                print("fd not found; falling back to python engine.", file=sys.stderr)
            elif args.number != 0:
                print("fd engine only supports number=0; falling back to python.", file=sys.stderr)
            else:
                print("fd scan failed; falling back to python.", file=sys.stderr)
        matches, directory_count, file_count = find_sparse_folders(root, args.number, ignores, args.include_pyc)
    elapsed = time.time() - start

    if args.verbose:
        print(f"[empties] engine: {engine_used}")
        print_summary(matches, directory_count, file_count, args.number, elapsed, engine_used)

    for folder in matches:
        print(folder)


if __name__ == "__main__":
    main()
