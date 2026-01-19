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
import shutil
import sys
import time
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

from ..bin.fuzzy import MatchResult, find_candidates
from ..settings import get_invoking_cwd
from .tomlr import get_config_value

try:  # optional rich formatting
    from rich.console import Console
    from rich.table import Table
    from rich.text import Text

    console = Console()
    RICH_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover
    console = None
    RICH_AVAILABLE = False


def _print_message(message: str, *, style: str | None = None) -> None:
    if RICH_AVAILABLE:
        console.print(Text(message, style=style) if style else message)
    else:
        print(message)


def _render_paths(title: str, paths: Sequence[Path]) -> None:
    if not paths:
        return
    if RICH_AVAILABLE:
        table = Table(title=title, box=None, show_header=False, pad_edge=False)
        table.add_column("#", justify="right", style="dim")
        table.add_column("Path", style="white")
        for idx, path in enumerate(paths, start=1):
            table.add_row(str(idx), str(path))
        console.print(table)
    else:
        print(title)
        for path in paths:
            print(f"  - {path}")


def run_command(command: str, *, verbose: bool = False):
    """Execute a shell command and return its output and error."""
    if verbose:
        _print_message(f"Running command: {command}", style="dim")
    process = subprocess.run(command, capture_output=True, text=True, shell=True)
    return process.stdout, process.stderr

def find_files(directory: Path, patterns: Sequence[str]):
    """Get all files in a directory tree matching a set of patterns."""
    for root, _, files in os.walk(directory):
        root_path = Path(root)
        for pattern in patterns:
            for filename in fnmatch.filter(files, pattern):
                yield root_path / filename

def _deduplicate_paths(paths: Iterable[Path]) -> List[Path]:
    """Remove duplicate paths while preserving order."""
    seen: set[Path] = set()
    unique_paths: List[Path] = []
    for path in paths:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique_paths.append(path)
    return unique_paths

def clean_files(file_list: Iterable[Path], script_path: Path, *, verbose: bool = False):
    """Run the external cleaning script on each file in the list."""
    if not script_path.exists():
        _print_message(f"Script path {script_path} does not exist. Exiting.", style="bold red")
        return
    for path in file_list:
        _print_message(f'Cleaning {path}', style="cyan")
        command = f'{script_path} {path}'
        output, error = run_command(command, verbose=verbose)
        if error:
            _print_message(f"Error: {error}", style="bold red")
        elif output.strip():
            _print_message(output.strip(), style="dim")

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
        _print_message(f"After substring search filter '{needle}': {len(filtered)} files (from {before_filter})", style="bold yellow")
        _render_paths("Substring matches", filtered)
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

    _print_message(f"After fuzzy search filter '{needle}': {len(filtered_files)} files (from {before_filter})", style="bold green")
    _render_paths("Fuzzy matches", filtered_files)
    return filtered_files

def _fd_discover_files(root_directory: Path, patterns: Sequence[str], *, minutes: int, use_all: bool, verbose: bool) -> Optional[List[Path]]:
    """Use fd to discover files quickly. Returns None if fd unavailable or fails."""
    if shutil.which("fd") is None:
        return None

    # Run fd once per pattern; some fd versions treat multiple --glob flags as search paths.
    base_cmd = ["fd", "-t", "f", "-t", "l", "-a", "-H", "-I"]
    if not use_all:
        base_cmd.extend(["--changed-within", f"{minutes}m"])

    files: list[Path] = []
    for pattern in patterns:
        cmd = [*base_cmd, "-g", pattern, str(root_directory)]
        if verbose:
            _print_message(f"Using fd for discovery: {' '.join(cmd)}", style="dim")

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            _print_message("fd discovery failed; falling back to Python scan.", style="bold yellow")
            if verbose and (result.stderr or result.stdout):
                _print_message(result.stderr or result.stdout, style="dim")
            return None

        files.extend(Path(line.strip()) for line in result.stdout.splitlines() if line.strip())

    # Deduplicate because we run fd per-pattern.
    unique_files = _deduplicate_paths(files)
    if use_all:
        _print_message(f"fd found {len(unique_files)} matching files (all).", style="bold yellow")
    else:
        _print_message(f"fd found {len(unique_files)} files changed within last {minutes} minutes.", style="bold yellow")
    return unique_files

def _read_stdin_paths(root_directory: Path) -> List[Path]:
    """Read newline-delimited paths from stdin and normalize them."""
    if sys.stdin.isatty():
        return []

    stdin_paths: List[Path] = []
    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue
        path = Path(line).expanduser()
        stdin_paths.append(path if path.is_absolute() else root_directory / path)

    existing, missing = [], []
    for path in stdin_paths:
        if path.exists():
            existing.append(path)
        else:
            missing.append(path)

    if missing:
        _render_paths("Paths from stdin that were not found (skipped)", missing)

    return _deduplicate_paths(existing)

def main():
    """CLI entry point for translation file cleaner."""
    _print_message("Translation Clean Script", style="bold blue")
    
    script_path_value = get_config_value("clean", "script_path")
    script_path = Path(script_path_value).expanduser() if script_path_value else None
    if not script_path or not script_path.is_file():
        _print_message(f"Script path not found at {script_path_value}. Exiting.", style="bold red")
        return

    default_minutes = 10
    root_directory = get_invoking_cwd()
    desired_filenames = ['*.po', '*.pot']

    parser = argparse.ArgumentParser(description="Clean .po and .pot files modified within a certain time frame.")
    parser.add_argument("--confirm", action="store_true", help="Confirm that files should be cleaned")
    parser.add_argument('-m', "--minutes", type=int, default=default_minutes, help="Minutes to look back for modified files")
    parser.add_argument('-a', "--all", action="store_true", help="Clean all matching files, ignoring modification time")
    parser.add_argument('-v', '--verbose', action='store_true', help="Enable verbose output")
    parser.add_argument('search', nargs='?', default=None, help="Optional: only clean translation paths containing this string")
    args = parser.parse_args()

    if not root_directory.is_dir():
        _print_message(f"Root directory {root_directory} does not exist. Exiting.", style="bold red")
        return

    files_from_stdin = _read_stdin_paths(root_directory)
    if files_from_stdin:
        _print_message(f"Received {len(files_from_stdin)} path(s) from stdin.", style="bold green")
        if args.verbose:
            _render_paths("Paths provided via stdin", files_from_stdin)

    matched_file: Optional[Path] = None
    if args.search:
        search_path = Path(args.search).expanduser()
        if search_path.is_file():
            matched_file = search_path
        else:
            test_path = root_directory / args.search
            if test_path.is_file():
                matched_file = test_path

    selected_files: List[Path] = []
    if files_from_stdin:
        selected_files.extend(files_from_stdin)
    if matched_file:
        selected_files.append(matched_file)

    if not selected_files:
        if not args.search:
            # just show help
            parser.print_help()
            _print_message("Provide a search term (or file path) to select translations to clean.", style="yellow")
            _print_message("You can also pipe file paths in: `find . -name \"*.po\" | clean.py --confirm`.", style="yellow")
            return
            
        _print_message(f"Searching for files named {', '.join(desired_filenames)} in {root_directory}")
        files_to_clean = _fd_discover_files(
            root_directory,
            desired_filenames,
            minutes=args.minutes,
            use_all=bool(args.all),
            verbose=args.verbose,
        )
        if files_to_clean is None:
            all_files = list(find_files(root_directory, desired_filenames))
            total_files = len(all_files)

            if args.all:
                files_to_clean = all_files
                _print_message(f"Searching ALL {total_files:,} files.", style="bold yellow")
            else:
                time_limit = time.time() - (args.minutes * 60)
                files_to_clean = [file for file in all_files if file.stat().st_mtime > time_limit]
                _print_message(
                    f"Found {len(files_to_clean)} of {total_files:,} files modified within the last {args.minutes} minutes. "
                    "(Use --all to match all files)."
                )

        # Warn if no files selected
        if not files_to_clean:
            _print_message("No files found to clean. Tip: use --all to clean/search across all files.", style="bold yellow")

        # Filter by search string if provided
        if args.search:
            files_to_clean = _filter_with_fuzzy(files_to_clean, root_directory, args.search)
    else:
        files_to_clean = selected_files
        if args.search and not matched_file:
            files_to_clean = _filter_with_fuzzy(files_to_clean, root_directory, args.search)

    files_to_clean = _deduplicate_paths(files_to_clean)

    if files_to_clean:
        preview_limit = 20
        preview = files_to_clean if len(files_to_clean) <= preview_limit else files_to_clean[:preview_limit]
        _render_paths("Files selected for cleaning", preview)
        if len(files_to_clean) > preview_limit:
            _print_message(f"...and {len(files_to_clean) - preview_limit} more files.", style="dim")
    else:
        _print_message("No files selected for cleaning.", style="bold yellow")

    if not args.confirm:
        _print_message("Test run only. No files were modified. Use --confirm to proceed.", style="bold yellow")
        return

    clean_files(files_to_clean, script_path, verbose=args.verbose)

if __name__ == "__main__":
    main()
