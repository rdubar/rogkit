#!/usr/bin/env python3
"""
Translation file cleaner utility.

Finds and cleans .po and .pot translation files using an external script.
Supports filtering by modification time and search terms. Configuration
via rogkit config.toml.

# Add to ~/.config/rogkit/config.toml: 
[clean]
script_path = '/home/rdubar/projects/pythonProject/openerp-addons/src/scripts/local/scripts/translation_clean.sh'
"""
import argparse
import fnmatch
import os
import subprocess
import time
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

from ..bin.fuzzy import MatchResult, find_candidates
from .tomlr import get_config_value


def run_command(command: str):
    """Execute a shell command and return its output and error."""
    process = subprocess.run(command, capture_output=True, text=True, shell=True)
    return process.stdout, process.stderr

def find_files(directory: Path, patterns: Sequence[str]):
    """Get all files in a directory tree matching a set of patterns."""
    for root, _, files in os.walk(directory):
        root_path = Path(root)
        for pattern in patterns:
            for filename in fnmatch.filter(files, pattern):
                yield root_path / filename

def clean_files(file_list: Iterable[Path], script_path: Path):
    """Run the external cleaning script on each file in the list."""
    if not script_path.exists():
        print(f"⚠️  Script path {script_path} does not exist. Exiting.")
        return
    for path in file_list:
        print(f'Running translation_clean.sh on {path}')
        command = f'{script_path} {path}'
        output, error = run_command(command)
        if error:
            print(f"Error: {error}")

def _filter_with_fuzzy(files: Sequence[Path], root_directory: Path, needle: str) -> List[Path]:
    """Filter files by matching fuzzy directories against the needle."""
    before_filter = len(files)
    search_roots = [root_directory]

    matches = find_candidates(search_roots, needle)
    candidate_dirs = [match.path if isinstance(match, MatchResult) else Path(match) for match in matches]

    if not candidate_dirs:
        # Fall back to simple substring matching if fuzzy search fails
        needle_lower = needle.lower()
        filtered = [file for file in files if needle_lower in str(file).lower()]
        print(f"After substring search filter '{needle}': {len(filtered)} files (from {before_filter})")
        for file in filtered:
            print(f"  {file}")
        return filtered

    filtered_files: List[Path] = []
    for file in files:
        file_path = file.resolve()
        for candidate in candidate_dirs:
            candidate_resolved = candidate.resolve()
            try:
                file_path.relative_to(candidate_resolved)
                filtered_files.append(file)
                break
            except ValueError:
                continue

    print(f"After fuzzy search filter '{needle}': {len(filtered_files)} files (from {before_filter})")
    for file in filtered_files:
        print(f"  {file}")
    return filtered_files

def main():
    """CLI entry point for translation file cleaner."""
    print("Translation Clean Script")
    
    script_path_value = get_config_value("clean", "script_path")
    script_path = Path(script_path_value).expanduser() if script_path_value else None
    if not script_path or not script_path.is_file():
        print(f"Script path not found at {script_path_value}. Exiting.")
        return

    default_minutes = 10
    root_directory_value = get_config_value("clean", "root_directory")
    root_directory = Path(root_directory_value).expanduser() if root_directory_value else None
    desired_filenames = ['*.po', '*.pot']

    parser = argparse.ArgumentParser(description="Clean .po and .pot files modified within a certain time frame.")
    parser.add_argument("--confirm", action="store_true", help="Confirm that files should be cleaned")
    parser.add_argument('-m', "--minutes", type=int, default=default_minutes, help="Minutes to look back for modified files")
    parser.add_argument('-a', "--all", action="store_true", help="Clean all matching files, ignoring modification time")
    parser.add_argument('search', nargs='?', default=None, help="Optional: only clean translation paths containing this string")
    args = parser.parse_args()

    if not root_directory or not root_directory.is_dir():
        print(f"Root directory {root_directory_value} does not exist or is not set. Exiting.")
        return
    
    matched_file: Optional[Path] = None
    if args.search:
        search_path = Path(args.search).expanduser()
        if search_path.is_file():
            matched_file = search_path
        else:
            test_path = (root_directory / args.search) if root_directory else None
            if test_path and test_path.is_file():
                matched_file = test_path
            
    if matched_file:
        print(f"Directly cleaning specified file: {matched_file}")
        clean_files([matched_file], script_path)
        return

    if not args.search:
        # just show help
        parser.print_help()
        return
        
    print(f"Searching for files named {', '.join(desired_filenames)} in {root_directory}")
    all_files = list(find_files(root_directory, desired_filenames))
    total_files = len(all_files)

    if args.all:
        files_to_clean = all_files
        print(f"Matching ALL {total_files:,} files.")
    else:
        time_limit = time.time() - (args.minutes * 60)
        files_to_clean = [file for file in all_files if file.stat().st_mtime > time_limit]
        print(f"Found {len(files_to_clean)} of {total_files:,} files modified within the last {args.minutes} minutes. (Use --all to match all files).")

    # New: warn if no files selected
    if not files_to_clean:
        print(f"⚠️  No files found to clean. Tip: use --all to clean/search across all files.")

    # New: Filter by search string if provided
    if args.search:
        files_to_clean = _filter_with_fuzzy(files_to_clean, root_directory, args.search)

    if not args.confirm:
        print("Test run only. No files were modified. Use --confirm to proceed.")
        return

    clean_files(files_to_clean, script_path)

if __name__ == "__main__":
    main()