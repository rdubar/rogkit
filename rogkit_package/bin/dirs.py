"""
Directory size calculator and analyzer.

Scans a directory tree (default: the current working directory) and reports
the largest subdirectories by total size. Supports substring filtering,
depth limits, and optional inclusion of hidden paths.
"""

import argparse
import os
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from time import perf_counter
from typing import DefaultDict, Optional, List, NamedTuple

from .bytes import byte_size

try:  # Optional rich dependency for nicer formatting
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text

    console = Console()
    console_err = Console(stderr=True)
    RICH_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover - optional
    console = None
    console_err = None
    RICH_AVAILABLE = False


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
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show which engine was used and any fallback reasons.",
    )
    args = parser.parse_args(argv)

    if args.limit <= 0:
        parser.error("--limit must be positive")
    if args.depth == 0 or args.depth < -1:
        parser.error("--depth must be -1 (all levels) or >= 1")

    return args


class ScanResult(NamedTuple):
    dir_sizes: DefaultDict[Path, int]
    total_files: Optional[int]
    errors: list[str]
    engine: str
    details: List[str]


def _build_du_command(root: Path, depth: int, include_hidden: bool):
    du_path = shutil.which("du")
    if not du_path:
        return None, "du not available on PATH"
    if depth == -1:
        return None, "du fast path skipped: depth=-1 (full recursion) requested"

    cmd = [du_path, "-k"]
    if sys.platform == "darwin":
        cmd.extend(["-d", str(depth)])
        if not include_hidden:
            cmd.extend(["-I", ".*"])
    else:
        cmd.append(f"--max-depth={depth}")
        if not include_hidden:
            cmd.append("--exclude=.*")
    cmd.append(str(root))
    return cmd, None


def _collect_directory_sizes_du(root: Path, depth: int, include_hidden: bool) -> tuple[Optional[ScanResult], Optional[str]]:
    cmd, skip_reason = _build_du_command(root, depth, include_hidden)
    if not cmd:
        return None, skip_reason

    details: List[str] = [f"du command: {' '.join(cmd)}", "file count: n/a (du mode)"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        reason = f"du failed with exit {result.returncode}: {result.stderr.strip() or 'no stderr'}"
        return None, reason

    dir_sizes: DefaultDict[Path, int] = defaultdict(int)
    for line in result.stdout.splitlines():
        parts = line.split(None, 1)
        if len(parts) != 2:
            continue
        try:
            size_kib = int(parts[0])
        except ValueError:
            continue
        dir_sizes[Path(parts[1])] = size_kib * 1024

    dir_sizes.setdefault(root, 0)
    errors = []
    stderr = result.stderr.strip()
    if stderr:
        errors.append(stderr)
        details.append(f"du stderr: {stderr}")

    return ScanResult(dir_sizes, None, errors, "du", details), None


def _collect_directory_sizes_python(root: Path, include_hidden: bool, _depth: int, prior: Optional[str]) -> ScanResult:
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
    details: List[str] = ["engine: python os.walk accumulator"]
    if prior:
        details.append(f"fallback reason: {prior}")
    return ScanResult(dir_sizes, total_files, errors, "python", details)


def collect_directory_sizes(root: Path, include_hidden: bool, depth: int) -> ScanResult:
    root = root.resolve()
    du_result, du_skip_reason = _collect_directory_sizes_du(root, depth, include_hidden)
    if du_result:
        return du_result
    return _collect_directory_sizes_python(root, include_hidden, depth, du_skip_reason)


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


def _print_message(message: str, *, style: str | None = None, stderr: bool = False) -> None:
    if RICH_AVAILABLE:
        text = Text(message, style=style) if style else message
        (console_err if stderr else console).print(text)
    else:
        target = sys.stderr if stderr else sys.stdout
        print(message, file=target)


def _render_intro(root: Path, include_hidden: bool) -> None:
    hidden_note = "including hidden folders" if include_hidden else "excluding hidden folders"
    message = f"Scanning {root} ({hidden_note})"
    _print_message(message, style="bold blue")


def _render_results_table(root: Path, entries, total_size: int, limit: int, depth: int) -> None:
    if not limit:
        return

    depth_label = "all levels" if depth == -1 else f"depth ≤ {depth}"
    title = f"Top {limit} directories ({depth_label}) under {root}"

    if RICH_AVAILABLE:
        table = Table(title=title, box=None, padding=(0, 1))
        table.add_column("Rank", justify="right", style="bold cyan")
        table.add_column("Size", justify="right", style="magenta")
        table.add_column("Share", justify="right", style="green")
        table.add_column("Path", style="white")
        for idx, (_, display_path, size) in enumerate(entries[:limit], start=1):
            share = (size / total_size * 100) if total_size else 0.0
            table.add_row(str(idx), byte_size(size), f"{share:0.1f}%", display_path)
        console.print(table)
    else:
        print(f"\n{title}:")
        print(f"{'Rank':>4} {'Size':>10} {'Share':>7} Path")
        for idx, (_, display_path, size) in enumerate(entries[:limit], start=1):
            share = (size / total_size * 100) if total_size else 0.0
            print(f"{idx:>4} {byte_size(size):>10} {share:>6.1f}% {display_path}")


def _render_summary(dir_sizes_count: int, total_files: Optional[int], total_size: int, elapsed: float,
                    filtered_total: int, filtered_count: int, search_term: Optional[str]) -> None:
    summary_lines = [
        ("Total size", byte_size(total_size)),
        ("Directories", f"{dir_sizes_count:,}"),
        ("Files", f"{total_files:,}" if total_files is not None else "n/a"),
        ("Elapsed", f"{elapsed:.2f}s"),
    ]
    if search_term:
        summary_lines.append(("Filtered total", f"{byte_size(filtered_total)} ({filtered_count} dirs)"))

    if RICH_AVAILABLE:
        table = Table(show_header=False, box=None, pad_edge=False)
        table.add_column(justify="right", style="bold green")
        table.add_column(style="white")
        for label, value in summary_lines:
            table.add_row(f"{label}:", value)
        console.print(Panel(table, title="Scan Summary", border_style="green", padding=(0, 1)))
    else:
        files_label = f"{total_files:,}" if total_files is not None else "n/a"
        print(
            f"\nTotal size: {byte_size(total_size)} "
            f"across {dir_sizes_count:,} directories and {files_label} files "
            f"in {elapsed:.2f} seconds"
        )
        if search_term:
            print(f"Filtered total: {byte_size(filtered_total)} ({filtered_count} directories)")


def _render_errors(errors: list[str]) -> None:
    if not errors:
        return

    shown = min(5, len(errors))
    header = f"Encountered {len(errors)} errors while reading files (showing {shown}):"

    if RICH_AVAILABLE:
        console.print(Panel(header, border_style="red", style="red"))
        for error in errors[:shown]:
            console.print(f"[red]- {error}[/red]")
        if len(errors) > shown:
            console.print("[red](showing first few only)[/red]")
    else:
        print(f"\n{header}")
        for error in errors[:shown]:
            print(f"  - {error}")
        if len(errors) > shown:
            print("  (showing first few only)")


def _render_engine_details(engine: str, details: List[str]) -> None:
    header = f"Engine: {engine}"
    body = "\n".join(details) if details else ""
    if RICH_AVAILABLE:
        console.print(Panel(body or "no details", title=header, border_style="cyan"))
    else:
        print(f"\n{header}")
        if body:
            for line in details:
                print(f"- {line}")
        else:
            print("- no details")


def main(argv=None):
    args = parse_args(argv)
    root = Path(args.path).expanduser()

    if not root.exists():
        _print_message(f"Path not found: {root}", style="bold red", stderr=True)
        return 1
    if not root.is_dir():
        _print_message(f"Not a directory: {root}", style="bold red", stderr=True)
        return 1

    root = root.resolve()
    _render_intro(root, args.include_hidden)
    start_time = perf_counter()
    result = collect_directory_sizes(root, args.include_hidden, args.depth)
    elapsed = perf_counter() - start_time
    dir_sizes = result.dir_sizes
    total_files = result.total_files
    errors = result.errors
    total_size = dir_sizes[root]

    entries = prepare_entries(dir_sizes, root, args.depth, args.search)
    filtered_total = sum(size for _, _, size in entries)
    limit = min(args.limit, len(entries))

    if limit:
        _render_results_table(root, entries, total_size, limit, args.depth)
    else:
        if args.search:
            _print_message("No directories matched the provided search term.", style="yellow")
        else:
            _print_message("No directories found under the specified root.", style="yellow")

    if args.verbose:
        _render_engine_details(result.engine, result.details)

    _render_summary(len(dir_sizes), total_files, total_size, elapsed, filtered_total, len(entries), args.search)
    _render_errors(errors)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
