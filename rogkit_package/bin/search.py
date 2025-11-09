#!/usr/bin/env python3
"""
File content search utility.

Recursively searches text/code files within the current working directory by
default. Use --path to override the root. Wrap queries in double-quotes to search
for an exact phrase. Results are case-insensitive, with common directories/files
ignored by default (e.g. .git, __pycache__, virtualenvs).
"""

import argparse
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Sequence

SEARCHABLE_EXTENSIONS = {
    ".py",
    ".xml",
    ".js",
    ".css",
    ".txt",
    ".md",
    ".log",
    ".po",
    ".pot",
}

EXCLUDE_PATTERNS = ["/.idea/", "__pycache__", ".git/", "venv/", "/eggs/"]


@dataclass
class SearchResults:
    """Encapsulates search results including matched files, skipped files, and errors."""

    matched_files: List[Path] = field(default_factory=list)
    skipped_files: List[Path] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    total_files: int = 0


def is_excluded(path: Path) -> bool:
    """Return True when the file path contains an excluded fragment."""
    path_str = str(path)
    return any(pattern in path_str for pattern in EXCLUDE_PATTERNS)


def is_valid_file(path: Path, skip_po: bool) -> bool:
    """Return True if the file extension is searchable (and not skipped)."""
    ext = path.suffix.lower()
    if skip_po and ext in {".po", ".pot"}:
        return False
    return ext in SEARCHABLE_EXTENSIONS


def file_contains(
    path: Path,
    tokens: Sequence[str],
    phrase: str,
    use_phrase: bool,
) -> bool:
    """Return True if the file's contents contain the requested tokens/phrase."""
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            content = handle.read().lower()
    except OSError as exc:
        raise IOError(f"Error reading file {path}: {exc}") from exc

    if use_phrase:
        return phrase in content
    return all(token in content for token in tokens)


def search_folder(
    root: Path,
    tokens: Sequence[str],
    phrase: str,
    use_phrase: bool,
    skip_po: bool,
) -> SearchResults:
    """Recursively search a folder for files containing the specified query."""
    results = SearchResults()

    for dirpath, dirnames, filenames in os.walk(root):
        current_dir = Path(dirpath)

        # Prune excluded directories in-place to avoid descending into them.
        dirnames[:] = [
            d for d in dirnames if not is_excluded(current_dir / d)
        ]

        for name in filenames:
            results.total_files += 1
            file_path = current_dir / name

            if is_excluded(file_path) or not is_valid_file(file_path, skip_po):
                results.skipped_files.append(file_path)
                continue

            try:
                if file_contains(file_path, tokens, phrase, use_phrase):
                    results.matched_files.append(file_path)
            except IOError as err:
                results.errors.append(str(err))

    return results


def parse_query(args: Sequence[str]) -> tuple[Sequence[str], str, bool, str]:
    """Normalise the CLI search query."""
    raw = " ".join(args)
    use_phrase = (
        len(args) == 1
        and args[0].startswith('"')
        and args[0].endswith('"')
    )

    if use_phrase:
        phrase = args[0].strip('"').lower()
        tokens: Sequence[str] = [phrase]
        display = phrase
    else:
        phrase = raw.lower()
        tokens = phrase.split()
        display = raw

    if not tokens or not phrase.strip():
        raise ValueError("Search text cannot be empty.")

    return tokens, phrase, use_phrase, display


def main() -> None:
    """CLI entry point for the file content search utility."""
    
    max_matches = 20 
    
    parser = argparse.ArgumentParser(
        description=(
            "Recursively search text/code files for the given terms. "
            "Wrap the query in double-quotes for an exact phrase."
        )
    )
    parser.add_argument(
        "text",
        nargs="+",
        help="Text to search for (wrap in quotes for a whole phrase).",
    )
    parser.add_argument(
        "--path",
        type=str,
        default=".",
        help="Root path to search (default: current working directory).",
    )
    parser.add_argument(
        "--show-matches",
        "-s",
        action="store_true",
        help=f"Always list matching files (otherwise limited to <{max_matches}).",
    )
    parser.add_argument(
        "--skip-po",
        action="store_true",
        help="Skip .po/.pot files.",
    )
    parser.add_argument(
        "--show-errors",
        action="store_true",
        help="Display files that could not be read.",
    )
    parser.add_argument(
        "--show-skipped",
        action="store_true",
        help="Display files that were skipped.",
    )

    args = parser.parse_args()

    try:
        tokens, phrase, use_phrase, display_query = parse_query(args.text)
    except ValueError as err:
        parser.error(str(err))
        return

    root = Path(args.path).expanduser().resolve()
    if not root.exists():
        parser.error(f"Path not found: {root}")
    if not root.is_dir():
        parser.error(f"Not a directory: {root}")

    print(f"Searching for: {display_query!r}")
    print(f"Root: {root}")
    if args.skip_po:
        print("Skipping .po/.pot files.")

    results = search_folder(root, tokens, phrase, use_phrase, args.skip_po)

    print(
        f"Found {len(results.matched_files):,} matches in {results.total_files:,} files "
        f"(Skipped {len(results.skipped_files):,}, Errors {len(results.errors):,})."
    )

    if results.matched_files and (args.show_matches or len(results.matched_files) < max_matches):
        print("Matches:")
        for match in results.matched_files:
            print(f"  {match}")

    if args.show_skipped and results.skipped_files:
        print("Skipped files:")
        for path in results.skipped_files:
            print(f"  {path}")

    if args.show_errors and results.errors:
        print("Errors:")
        for error in results.errors:
            print(f"  {error}")


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
