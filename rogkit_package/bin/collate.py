#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
File collation utility.

Recursively collates text and code files from a directory into a single file,
with support for filtering by content match, file exclusion patterns, and sorting.
"""
import argparse
import os
import sys
import fnmatch
from pathlib import Path
from typing import List, Optional

from ..bin.fuzzy import MatchResult, find_candidates
from ..settings import get_invoking_cwd

def clean_name(name):
    """Create a file-friendly name from a given string."""
    return name.replace(" ", "_").lower()

def collate_files(
    directory: Path,
    output_file: Optional[str] = None,
    match: Optional[str] = None,
    ignore_case: bool = False,
    report: bool = False,
    sort_files: bool = False,
    verbose: bool = False,
    exclude_patterns: Optional[List[str]] = None,
):
    """Recursively collates all text and code files from a given directory into one file."""
    matched = 0
    total = 0
    output = []

    if match is not None and ignore_case:
        match = match.lower()

    if not output_file:
        if match:
            output_file = f"collated_{clean_name(match)}.txt"
        elif directory:
            output_file = f"collated_{clean_name(os.path.basename(directory))}.txt"
        else:
            output_file = "collated_files.txt"

    exclude_dirs = {
        "__pycache__", "eggs", "v27", "venv", ".git", ".vscode", ".idea",
        ".ropeproject", ".mypy_cache", ".pytest_cache"
    }
    file_list = []

    for root, _, files in os.walk(directory):
        root_path = Path(root)
        if exclude_dirs.intersection(root_path.parts):
            continue
        for file in files:
            file_path = root_path / file

            # Skip excluded patterns
            if exclude_patterns and any(fnmatch.fnmatch(file, pattern) for pattern in exclude_patterns):
                if verbose:
                    print(f"[EXCLUDED] {file_path}")
                continue

            if file.endswith((
                ".txt", ".py", ".java", ".cpp", ".html", ".css", ".js",
                ".json", ".md", ".mako", ".csv", ".xml", ".yaml", ".yml"
            )):
                file_list.append(file_path)

    if sort_files:
        file_list.sort()

    for file_path in file_list:
        try:
            total += 1
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                if match is not None:
                    check_text = content.lower() if ignore_case else content
                    if match not in check_text:
                        continue
                output.append("\n--- {} ---\n".format(file_path))
                output.append(content + "\n")
                matched += 1
                if verbose:
                    print("[MATCH] {}: {}".format(file_path, match))
        except Exception as e:
            if report:
                print("[SKIP] {}: {}".format(file_path, e))

    if report:
        print("[SUMMARY] Matched {:,} out of {:,} files.".format(matched, total))

    if not matched:
        print("No files matched.")
        return

    try:
        with open(output_file, "w", encoding="utf-8") as out_file:
            out_file.write("".join(output))
        if report:
            print("[DONE] Collated files written to: {}".format(output_file))
    except Exception as e:
        print("[ERROR] Failed to write to {}: {}".format(output_file, e))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Collate text and code files from a directory into one file.")
    parser.add_argument("-a", "--all", action="store_true", help="Include all files regardless of match text.")
    parser.add_argument("-m", "--match", type=str, default=None, help="Text to match in file content.")
    parser.add_argument("-i", "--ignore", action="store_true", help="Ignore case in match text.")
    parser.add_argument("-p", "--path", type=str, default=os.getcwd(), help="Directory path to scan (default: current directory).")
    parser.add_argument("-o", "--output", type=str, default=None, help="Output file name.")
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress summary output.")
    parser.add_argument("-s", "--sort", action="store_true", help="Sort files alphabetically before collating.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output.")
    parser.add_argument(
        "-e", "--exclude", type=str, nargs="+",
        help="File patterns to exclude (e.g., *.txt *.log)"
    )
    parser.add_argument(
        "--fuzzy",
        action="store_true",
        help="Use fuzzy search if the provided path does not exist.",
    )
    parser.add_argument(
        "--fuzzy-root",
        type=str,
        nargs="+",
        help="Directories to search when using --fuzzy (default: current directory).",
    )
    parser.add_argument(
        "--fuzzy-strategy",
        choices=("substring", "fuzz"),
        default="substring",
        help="Match strategy for fuzzy search (default: substring).",
    )
    parser.add_argument(
        "--fuzzy-threshold",
        type=float,
        default=70.0,
        help="Minimum score when using --fuzzy-strategy fuzz (0-100).",
    )

    args = parser.parse_args()

    if not args.all and not args.match:
        print("You must specify either --all or --match.")
        sys.exit(1)

    target_path = Path(args.path).expanduser()
    if not target_path.exists():
        if args.fuzzy:
            search_roots = (
                [Path(p).expanduser() for p in args.fuzzy_root]
                if args.fuzzy_root
                else [get_invoking_cwd()]
            )
            matches = find_candidates(
                search_roots,
                args.path,
                strategy=args.fuzzy_strategy,
                threshold=args.fuzzy_threshold,
            )
            if len(matches) == 1:
                target_path = matches[0].path if isinstance(matches[0], MatchResult) else Path(matches[0])
                print(f"[FUZZY] Using matched path: {target_path}")
            elif matches:
                print("[ERROR] Multiple paths match '{}':".format(args.path))
                for match in matches:
                    path = match.path if isinstance(match, MatchResult) else match
                    print(f"  {path}")
                sys.exit(1)
            else:
                print("[ERROR] No paths matched '{}' using fuzzy search.".format(args.path))
                sys.exit(1)
        else:
            print("[ERROR] The path '{}' does not exist.".format(args.path))
            sys.exit(1)

    if args.all:
        args.match = None  # Include all files

    if not args.quiet:
        print("[START] Collating from: {}".format(target_path))
        if args.match is not None:
            print("[FILTER] Matching: '{}' (ignore case: {})".format(args.match, "Yes" if args.ignore else "No"))
        if args.sort:
            print("[INFO] Files will be sorted alphabetically.")
        if args.exclude:
            print(f"[EXCLUDE] Patterns: {', '.join(args.exclude)}")

    collate_files(
        target_path,
        output_file=args.output,
        match=args.match,
        ignore_case=args.ignore,
        report=not args.quiet,
        sort_files=args.sort,
        verbose=args.verbose,
        exclude_patterns=args.exclude
    )