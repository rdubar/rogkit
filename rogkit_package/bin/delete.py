#!/usr/bin/env python3
"""Delete or trash files/folders; supports piped input with confirmation."""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path
from typing import Iterable, List

from send2trash import send2trash

from .bytes import byte_size

try:  # Rich is optional; fall back to plain text when missing
    from rich.console import Console
    from rich.table import Table

    console = Console()
    console_err = Console(stderr=True)
    RICH_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover
    console = None
    console_err = None
    RICH_AVAILABLE = False


def _print(message: str, *, style: str | None = None, stderr: bool = False) -> None:
    if RICH_AVAILABLE:
        (console_err if stderr else console).print(message, style=style)
    else:
        target = sys.stderr if stderr else sys.stdout
        print(message, file=target)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Move files/folders to trash by default; use -f to delete permanently. Accepts args or piped paths."
    )
    parser.add_argument("paths", nargs="*", help="File(s)/folder(s) to process")
    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Permanently delete instead of moving to trash",
    )
    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Skip confirmation (useful for scripted runs)",
    )
    return parser


def _stdin_paths() -> List[str]:
    if sys.stdin.closed or sys.stdin.isatty():
        return []
    return [line.strip() for line in sys.stdin.read().splitlines() if line.strip()]


def _normalize_paths(raw_paths: Iterable[str]) -> List[Path]:
    seen = set()
    normalized: List[Path] = []
    for raw_path in raw_paths:
        path = Path(raw_path).expanduser().resolve(strict=False)
        key = path.as_posix()
        if key and key not in seen:
            seen.add(key)
            normalized.append(path)
    return normalized


def _path_size_display(path: Path) -> str:
    try:
        if path.is_file():
            return byte_size(path.stat().st_size)
        if path.is_dir():
            return "<dir>"
    except OSError:
        return "unreadable"
    return "missing"


def _render_paths_table(paths: List[Path]) -> None:
    if RICH_AVAILABLE:
        table = Table(box=None, pad_edge=False)
        table.add_column("Size", justify="right", style="cyan")
        table.add_column("Path", style="white")
        for path in paths:
            size = _path_size_display(path)
            style = "red" if not path.exists() else None
            table.add_row(size, str(path), style=style)
        console.print(table)
    else:
        for path in paths:
            size = _path_size_display(path)
            marker = " (missing)" if not path.exists() else ""
            print(f"{size:>10}  {path}{marker}")


def _prompt_deletion_choices(paths: List[Path], auto_yes: bool, piped_input: bool) -> List[Path] | None:
    """
    Return the subset of paths approved for deletion.
    - When not piped or auto_yes is True, all paths are approved.
    - When piped, prompt per item with y/yes/no/all. If "all" is chosen, require a follow-up "confirm".
    """
    if not piped_input or auto_yes:
        return paths

    approved: List[Path] = []
    delete_all = False

    for path in paths:
        if delete_all:
            approved.append(path)
            continue

        while True:
            response = _read_from_tty(f"Delete {path}? [y/n/all]: ")
            if response is None:
                return None
            answer = response.strip().lower()
            if answer in {"y", "yes"}:
                approved.append(path)
                break
            if answer in {"n", "no", ""}:
                break
            if answer == "all":
                confirm = _read_from_tty("Type 'confirm' to delete all listed items: ")
                if confirm is None:
                    return None
                if confirm.strip().lower() == "confirm":
                    delete_all = True
                    approved.append(path)
                    break
                _print("All-request canceled. Continuing prompts.", style="yellow")
                continue
            _print("Please respond with y, n, or all.", style="yellow")

    if not approved:
        _print("Aborted; nothing changed.", style="yellow")
        return None

    return approved


def _read_from_tty(prompt: str) -> str | None:
    """Read a line even when stdin was piped; fall back to -y advice."""
    if sys.stdin.isatty():
        return console.input(prompt) if RICH_AVAILABLE else input(prompt)

    try:
        with open("/dev/tty", "r", encoding="utf-8", errors="ignore") as tty:
            if RICH_AVAILABLE:
                console.print(prompt, end="")
            else:
                print(prompt, end="", flush=True)
            return tty.readline()
    except OSError:
        _print(
            "No TTY available for confirmation. Re-run with -y to auto-confirm in pipelines.",
            style="red",
            stderr=True,
        )
        return None


def _delete_path(path: Path, force: bool) -> bool:
    if not path.exists():
        _print(f"Skipping missing path: {path}", style="yellow")
        return True

    try:
        if force:
            if path.is_file() or path.is_symlink():
                path.unlink()
            else:
                shutil.rmtree(path)
            _print(f"Permanently deleted: {path}", style="magenta")
        else:
            send2trash(str(path))
            _print(f"Trashed: {path}", style="green")
        return True
    except Exception as exc:  # pragma: no cover - system dependent
        _print(f"Failed to process {path}: {exc}", style="red", stderr=True)
        return False


def safe_delete(path: str | Path, force: bool = False) -> bool:
    """Backward-compatible helper for other modules (e.g., empties)."""
    return _delete_path(Path(path), force)


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    piped_paths = _stdin_paths()
    paths = _normalize_paths([*args.paths, *piped_paths])

    if not paths:
        parser.print_usage()
        _print(
            "No files provided. Pass paths as arguments or pipe newline-separated paths.",
            stderr=True,
        )
        return 1

    _render_paths_table(paths)

    approved_paths = _prompt_deletion_choices(paths, args.yes, bool(piped_paths))
    if approved_paths is None:
        return 1

    results = [_delete_path(path, args.force) for path in approved_paths]
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
