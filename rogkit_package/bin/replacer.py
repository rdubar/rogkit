#!/usr/bin/env python3
"""
Text find and replace utility.

Recursively searches text files for specified text patterns and optionally
replaces them with new text, with confirmation option for each replacement.
"""
import dataclasses
import os
import argparse
from pathlib import Path
from typing import Iterable, Optional, Sequence
import time

from ..bin.fuzzy import MatchResult, find_candidates

SKIP_PARTS = (
    "node_modules",
    ".git",
    ".venv",
    ".tox",
    "__pycache__",
    "eggs",
    "parts",
    "env",
)


@dataclasses.dataclass
class SearchResults:
    """Encapsulates search results including matches, skipped files, and errors."""
    matches: list = dataclasses.field(default_factory=list)
    skipped: list = dataclasses.field(default_factory=list)
    errors: list = dataclasses.field(default_factory=list)
    total: int = 0

def skip_path(path: Path):
    """Check if path should be skipped based on common directories to exclude."""
    return any(part in SKIP_PARTS for part in path.parts)


def is_text_file(filename: Path):
    """Check if filename has a text file extension."""
    text_file_extensions = {'.py', '.txt', '.html', '.xml', '.js', '.css', '.csv', '.rst', '.po', '.pot', '.mako', '.md'}
    return filename.suffix.lower() in text_file_extensions

def find_text_files(path: Path, find_text: Optional[str], debug: bool = False):
    """Recursively search text files for specified text and return matching files."""
    results = SearchResults()
    if not find_text:
        return results
    for root, _, filenames in os.walk(path):
        for filename in filenames:
            results.total += 1
            file_path = Path(root) / filename
            if is_text_file(file_path):
                if skip_path(file_path):
                    results.skipped.append(file_path)
                    continue
                try:
                    with open(file_path, 'r', encoding='utf-8') as file:
                        if find_text in file.read():
                            results.matches.append(file_path)
                except Exception as e:
                    try:
                        error_message = f'Error reading {file_path}: {e}'
                        if debug:
                            print(error_message)
                        results.errors.append(error_message)
                    except Exception:
                        continue
    return results

def replace_text_in_file(file_path: Path, find_text: str, replace_text: str):
    """Replace text in a single file and return True if replacement was made."""
    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()
    if replace_text in content:
        return False
    content = content.replace(find_text, replace_text)
    with open(file_path, 'w', encoding='utf-8') as file:
        file.write(content)
    return True

def _resolve_search_path(args) -> Path:
    """Resolve the search path, optionally using fuzzy matching."""
    provided_path = Path(args.path or ".").expanduser()
    if provided_path.exists():
        return provided_path

    if not args.fuzzy:
        raise SystemExit(f"Path '{provided_path}' does not exist. Use --fuzzy to search for similar paths.")

    roots = (
        [Path(root).expanduser() for root in args.fuzzy_root]
        if args.fuzzy_root
        else [Path.cwd()]
    )
    matches = find_candidates(
        roots,
        args.path,
        strategy=args.fuzzy_strategy,
        threshold=args.fuzzy_threshold,
    )
    if len(matches) == 1:
        match = matches[0]
        resolved = match.path if isinstance(match, MatchResult) else Path(match)
        print(f"[FUZZY] Using matched path: {resolved}")
        return resolved

    if matches:
        print(f"Multiple paths match '{args.path}':")
        for match in matches:
            path = match.path if isinstance(match, MatchResult) else match
            print(f"  {path}")
        raise SystemExit(1)

    raise SystemExit(f"No paths matched '{args.path}' using fuzzy search.")

def get_args():
    """Parse command-line arguments for search and replace utility."""
    parser = argparse.ArgumentParser(description='Search and optionally replace text in files.')
    parser.add_argument("-p", '--path',  required=False, help='Path to search files in')
    parser.add_argument('-f', '--find_text', required=False, help='Text to find')
    parser.add_argument('--replace_text', help='Text to replace found text with')
    parser.add_argument('--confirm', action='store_true', help='Confirm before making each replacement')
    parser.add_argument('--debug', action='store_true', help='Run in debug mode')
    parser.add_argument(
        '--fuzzy',
        action='store_true',
        help='Resolve the path using fuzzy search if the provided path does not exist.',
    )
    parser.add_argument(
        '--fuzzy-root',
        type=str,
        nargs='+',
        help='Directories to search when using --fuzzy (default: current directory).',
    )
    parser.add_argument(
        '--fuzzy-strategy',
        choices=('substring', 'fuzz'),
        default='substring',
        help='Match strategy for fuzzy search (default: substring).',
    )
    parser.add_argument(
        '--fuzzy-threshold',
        type=float,
        default=70.0,
        help='Minimum score when using --fuzzy-strategy fuzz (0-100).',
    )
    args = parser.parse_args()
    return args

def do_search_and_replace(args):
    """Execute search and optional replace operation based on arguments."""
    clock = time.perf_counter()
    search_path = _resolve_search_path(args)

    if args.find_text:
        print(f"Searching for {args.find_text} in {search_path}")
    else:
        print(f"Searching for text in {search_path}")

    results = find_text_files(search_path, args.find_text, debug=args.debug)
    print(f"Found {len(results.matches):,} matching files in {results.total:,} files (skipped {len(results.skipped):,}, errors {len(results.errors):,}).")
    if args.confirm and args.replace_text:
        print(f"Replacing {args.find_text} with {args.replace_text} in {len(results.matches):,} files.")
        for file_path in results.matches:
            if replace_text_in_file(file_path, args.find_text, args.replace_text):
                print(f"Replaced text in {file_path}")
            else:
                print(f"Text already replaced in {file_path}")

    duration = time.perf_counter() - clock
    print(f"Total time: {duration:.2f} seconds.")

def main():
    """CLI entry point for text replacement utility."""
    args = get_args()

    over_ride = False

    print('Rogkit Replacer: Search and optionally replace text in files.')

    if over_ride: 
        # defaults for testing
        args.path = '/home/rdubar/projects/pythonProject/openerp-addons'
        
        # args.find_text = 'Die Lieferung ist inkl. <b>Liefertermin spätestens 48h</b>'
        # args.replace_text = 'Die Lieferung ist inkl. <b>Liefertermin und Preisen spätestens 48h</b>'

        # args.find_text = 'Delivery including the <b>delivery date</b>'
        # args.replace_text = 'Delivery including the <b>delivery date and prices</b>'
        args.confirm = False

    do_search_and_replace(args)

if __name__ == "__main__":
    main()
