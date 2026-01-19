#!/usr/bin/env python3
"""
Full-path search utility with optional media metadata display.

Searches the configured media/library folders (from rogkit config `[media].paths`)
or directories supplied via `--path`. Every supplied text token must appear
somewhere in the full path (folders + filename). Use `--media` to display video
resolution + codec via ffmpeg.
"""

import argparse
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

import ffmpeg  # type: ignore

from ..settings import get_invoking_cwd
from .bytes import byte_size
from .tomlr import get_config_value

try:  # Rich is optional; fall back to plain text when missing
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text

    console = Console()
    console_err = Console(stderr=True)
    RICH_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover
    console = None
    console_err = None
    RICH_AVAILABLE = False


def media_info(filepath: Path, verbose: bool = False) -> str:
    """Return resolution/codec metadata for a video file."""
    try:
        probe = ffmpeg.probe(str(filepath))
        stream = next(
            (s for s in probe.get("streams", []) if s.get("codec_type") == "video"),
            None,
        )
        if stream:
            width = stream.get("width")
            height = stream.get("height")
            codec = stream.get("codec_name")
            if width and height and codec:
                return f"{width}x{height} {codec}"
    except ffmpeg.Error as err:
        error = f"ffmpeg error: {err.stderr.decode(errors='ignore')}"
    except (OSError, ValueError, KeyError) as exc:  # pragma: no cover - ffmpeg edge cases
        error = f"Error: {exc}"
    else:
        error = "No video stream"

    return error if verbose else ""


def _print_message(message: str, *, style: str | None = None, stderr: bool = False) -> None:
    if RICH_AVAILABLE:
        text = Text(message, style=style) if style else message
        (console_err if stderr else console).print(text)
    else:
        target = sys.stderr if stderr else sys.stdout
        print(message, file=target)


def _render_paths_table(rows: List[tuple[str, str, str]], show_media: bool, to_show: int) -> None:
    if RICH_AVAILABLE:
        table = Table(box=None, pad_edge=False)
        table.add_column("Size", justify="right", style="cyan")
        table.add_column("Path", style="white")
        if show_media:
            table.add_column("Media", style="magenta")
        for size, path, media in rows[:to_show]:
            columns = [size, path]
            if show_media:
                columns.append(media)
            table.add_row(*columns)
        console.print(table)
    else:
        for size, path, media in rows[:to_show]:
            print(f"{size:>10}  {path}")
            if show_media and media:
                print(f"{'':>12}{media}")


@dataclass
class SearchReport:
    """Encapsulates file search results and metadata."""

    search_terms: List[str]
    folders: List[Path] = field(default_factory=list)
    results: List[Path] = field(default_factory=list)
    total_files_searched: int = 0
    search_time: float = 0.0

    def display_files(self, number: int = 10, show_all: bool = False, show_media: bool = False) -> None:
        """Display search results with file size and optional media info."""
        to_show = len(self.results) if show_all else min(number, len(self.results))
        matches = "match" if len(self.results) == 1 else "matches"
        summary = (
            f"Found {len(self.results):,} {matches} in "
            f"{self.total_files_searched:,} files across {len(self.folders)} root(s) "
            f"in {self.search_time:.2f} seconds."
        )
        if RICH_AVAILABLE:
            console.print(Panel(summary, border_style="cyan"))
        else:
            print(summary)

        rows: List[tuple[str, str, str]] = []
        for result in self.results:
            try:
                size = byte_size(result.stat().st_size)
            except OSError:
                size = "N/A"
            media_details = ""
            if show_media:
                info = media_info(result)
                if info:
                    media_details = info
            rows.append((size, str(result), media_details))

        _render_paths_table(rows, show_media, to_show)

        if len(self.results) > to_show:
            _print_message("...and more", style="dim")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for file search."""
    parser = argparse.ArgumentParser(
        description=(
            "Search configured media/library folders for full paths containing all "
            "supplied text tokens. Paths default to the rogkit config `[media].paths` "
            "list and can be overridden with `--path` (repeatable)."
        ),
        epilog=(
            "Configuration example:\n"
            "  [media]\n"
            "  paths = [\"~/Media\", \"/mnt/storage/TV\"]\n"
            "Override at runtime:\n"
            "  paths thriller --path /srv/library --path ~/Downloads"
        ),
    )
    parser.add_argument(
        "-a",
        "--all",
        action="store_true",
        help="Show all matching results (default shows up to --number).",
    )
    parser.add_argument(
        "-p",
        "--path",
        action="append",
        dest="paths",
        help="Override media paths (repeatable). Defaults to [media].paths in rogkit config.",
    )
    parser.add_argument(
        "-m",
        "--media",
        action="store_true",
        help="Show media info (resolution/codec) for matching video files.",
    )
    parser.add_argument(
        "-n",
        "--number",
        type=int,
        default=10,
        help="Number of results to display (default: 10).",
    )
    parser.add_argument(
        "-u",
        "--user",
        action="store_true",
        help="Include the user's home directory as an additional search root.",
    )
    parser.add_argument(
        "texts",
        nargs="+",
        help="Text tokens to match (all must appear in the file path).",
    )

    args = parser.parse_args()
    if not args.texts:
        parser.print_help(sys.stderr)
        parser.exit(1)
    return args


def normalise_search_terms(raw_terms: Sequence[str]) -> List[str]:
    return [term.lower() for term in raw_terms]


def resolve_media_paths(cli_paths: Iterable[str] | None) -> Tuple[List[Path], str]:
    """Return search roots and a label describing their source."""
    if cli_paths:
        return _expand_paths(cli_paths), "command line override"

    config_value = get_config_value("media", "paths")
    if isinstance(config_value, str):
        paths = _expand_paths([config_value])
    elif isinstance(config_value, (list, tuple, set)):
        paths = _expand_paths(config_value)
    else:
        paths = []

    if paths:
        return paths, "rogkit config [media].paths"

    fallback = [get_invoking_cwd()]
    return fallback, "current working directory"


def _expand_paths(paths: Iterable[str]) -> List[Path]:
    expanded: List[Path] = []
    for entry in paths:
        entry = str(entry).strip()
        if not entry:
            continue
        expanded.append(Path(entry).expanduser().resolve())
    return expanded


def find_files(roots: Sequence[Path], tokens: Sequence[str]) -> SearchReport:
    """Recursively search for files whose path contains all tokens."""
    start_time = time.perf_counter()
    report = SearchReport(search_terms=list(tokens))
    lower_tokens = [token.lower() for token in tokens]

    for root in roots:
        if not root.exists():
            continue
        report.folders.append(root)
        for dirpath, _dirnames, filenames in os.walk(root):
            for filename in filenames:
                report.total_files_searched += 1
                filepath = Path(dirpath) / filename
                path_str = str(filepath).lower()
                if all(token in path_str for token in lower_tokens):
                    report.results.append(filepath)

    report.search_time = time.perf_counter() - start_time
    return report


def ensure_valid_roots(roots: List[Path], include_home: bool) -> List[Path]:
    valid = [path for path in roots if path.exists()]
    missing = sorted(set(roots) - set(valid))
    if missing:
        _print_message("Skipping missing paths:", style="yellow")
        for path in missing:
            _print_message(f"  - {path}", style="yellow")

    if include_home:
        home = Path.home()
        if home not in valid:
            valid.append(home)

    if not valid:
        raise RuntimeError(
            "No valid media paths found. Provide --path PATH or configure [media].paths."
        )

    return valid


def main() -> None:
    """CLI entry point for file search utility."""
    args = parse_args()
    tokens = normalise_search_terms(args.texts)

    roots, source_label = resolve_media_paths(args.paths)
    try:
        roots = ensure_valid_roots(roots, include_home=args.user)
    except RuntimeError as err:
        _print_message(str(err), style="bold red", stderr=True)
        return

    _print_message(f"Searching roots ({source_label}):", style="bold blue")
    for root in roots:
        _print_message(f"  - {root}")

    _print_message(f"Looking for full paths containing all of: {', '.join(tokens)}")
    if args.media:
        _print_message("Media metadata (resolution/codec) will be displayed for video files.", style="magenta")

    report = find_files(roots, tokens)
    report.display_files(number=args.number, show_all=args.all, show_media=args.media)


if __name__ == "__main__":
    main()
