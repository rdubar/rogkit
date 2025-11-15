#!/usr/bin/env python3
"""
Tkinter/CLI search UI for the Plex media cache.

The script now supports two modes:
* GUI (default) – launches a Tkinter interface for quick browsing.
* CLI (`--cli`) – prints results to stdout when Tk is unavailable or undesired.
It integrates with the modern media cache helpers (run_pretty_search, etc.).
"""

from __future__ import annotations

import argparse
import os
import sys
from argparse import Namespace
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from .helpers import detect_db_path
from .media_cache import ensure_cache_table
from .search import format_pretty_row, format_stats, run_pretty_search

DEFAULT_LIMIT = 250


def _search_terms(query: str) -> List[str]:
    """Split the search query into lowercase terms."""
    return [term.lower() for term in query.split() if term.strip()]


def initialise_database() -> Path:
    """Locate the Plex database and ensure the local cache table exists."""
    db_path = detect_db_path()
    if db_path is None:
        raise RuntimeError(
            "No Plex database found. Set PLEX_DB_PATH, configure [plex_remote], "
            "or run `python -m rogkit_package.media.media --list-paths` for help."
        )
    ensure_cache_table(db_path)
    return db_path


def run_search(
    db_path: Path,
    query: str,
    *,
    limit: int,
    display_args: Namespace,
    deep: bool,
) -> Tuple[List[object], List[str], str, int, int, bool]:
    """
    Execute a media search and return the raw rows, formatted lines, stats, and metadata.

    Returns:
        rows: raw rows returned from the cache (sqlite rows or dicts)
        formatted_lines: pretty-formatted strings for each row
        stats_text: summary string describing the result set
        visible_count: number of rows returned (<= limit)
        total_matches: total matches reported (may equal visible_count)
        deep_search: True if a deep search was required
    """
    limit_value = max(limit, 0)
    limit_arg: Optional[int] = limit_value or None

    terms = _search_terms(query)
    rows, total_matches = run_pretty_search(
        db_path,
        terms,
        limit=limit_arg,
        sort="title",
        reverse=False,
        deep=deep,
    )
    deep_search = deep

    if not rows and terms and not deep:
        rows, total_matches = run_pretty_search(
            db_path,
            terms,
            limit=limit_arg,
            sort="title",
            reverse=False,
            deep=True,
        )
        deep_search = True

    formatted_lines = [format_pretty_row(row, display_args) for row in rows]

    visible_count = len(rows)
    if total_matches is None:
        total_matches = visible_count

    stats_text = format_stats(rows) if rows else ""

    return rows, formatted_lines, stats_text, visible_count, total_matches, deep_search


def run_cli_mode(
    db_path: Path,
    query: str,
    *,
    limit: int,
    display_args: Namespace,
    deep: bool,
) -> int:
    """Execute a search and print results to stdout."""
    _, formatted_lines, stats_text, visible, total, deep_search = run_search(
        db_path,
        query,
        limit=limit,
        display_args=display_args,
        deep=deep,
    )

    if not formatted_lines:
        print("No matching media found.")
        return 0

    print("\n\n".join(formatted_lines))

    if stats_text:
        print()
        print(stats_text)

    if total > visible:
        remaining = total - visible
        print(f"...and {remaining} more result(s). Increase --limit or use --deep.")

    if deep_search and not deep:
        print("(Deep search performed automatically.)")

    return 0


def launch_gui(
    db_path: Path,
    query: str,
    *,
    limit: int,
) -> None:
    """Start the Tkinter interface."""
    try:
        import tkinter as tk  # type: ignore
        from tkinter import messagebox, scrolledtext  # type: ignore
    except ImportError as exc:  # pragma: no cover - environment specific
        raise RuntimeError(
            "Tkinter is not available in this Python installation."
        ) from exc

    configure_tk_environment()

    try:
        root = tk.Tk()
    except tk.TclError as exc:  # pragma: no cover - environment specific
        raise RuntimeError(
            "Tkinter failed to initialise. Ensure Tcl/Tk is installed "
            "and the TCL_LIBRARY/TK_LIBRARY environment variables point to the "
            "directory containing init.tcl (try `brew install python-tk@3.12`)."
        ) from exc

    display_args = Namespace(length=80, info=False, path=False)

    class SearchApp:
        """Tkinter application for searching the Plex media cache."""

        def __init__(self, master: tk.Tk):
            self.master = master
            self.master.title("Rog's Media Library")

            self.db_path = db_path
            self.limit = limit
            self.display_args = display_args

            self.search_frame = tk.Frame(self.master)
            self.search_frame.pack(padx=10, pady=10)

            self.search_var = tk.StringVar()
            self.search_entry = tk.Entry(
                self.search_frame, textvariable=self.search_var, width=50
            )
            self.search_entry.pack(side=tk.LEFT, padx=(0, 10))
            self.search_entry.bind("<Return>", self.perform_search)

            self.search_button = tk.Button(
                self.search_frame, text="Search", command=self.perform_search
            )
            self.search_button.pack(side=tk.LEFT)

            self.clear_button = tk.Button(
                self.search_frame, text="Clear", command=self.clear_search
            )
            self.clear_button.pack(side=tk.LEFT, padx=(10, 0))

            self.text_area = scrolledtext.ScrolledText(
                self.master,
                wrap=tk.WORD,
                width=80,
                height=20,
            )
            self.text_area.pack(padx=10, pady=(0, 10))
            self.text_area.config(state=tk.DISABLED)

            self.status_label = tk.Label(self.master, text="Ready.")
            self.status_label.pack(padx=10, pady=(0, 10))

            if query:
                self.search_var.set(query)
            self.perform_search()

        def perform_search(self, event: Optional[tk.Event] = None) -> None:  # type: ignore[override]
            query_text = self.search_var.get()
            try:
                _, formatted_lines, stats_text, visible, total, deep_search = run_search(
                    self.db_path,
                    query_text,
                    limit=self.limit,
                    display_args=self.display_args,
                    deep=False,
                )
            except Exception as exc:  # pragma: no cover - defensive
                messagebox.showerror("Search Error", str(exc))
                return

            if formatted_lines:
                text = "\n\n".join(formatted_lines)
            else:
                text = "No matching media found."

            self.text_area.config(state=tk.NORMAL)
            self.text_area.delete("1.0", tk.END)
            self.text_area.insert(tk.END, text)
            self.text_area.config(state=tk.DISABLED)

            if total == 0:
                status = "No matching media found."
            else:
                extra = " (deep search)" if deep_search else ""
                status = f"Showing {visible} of {total} match(es){extra}."
                if stats_text:
                    status += f" {stats_text}"
            self.status_label.config(text=status)

        def clear_search(self) -> None:
            self.search_var.set("")
            self.perform_search()

    SearchApp(root)
    root.mainloop()


def configure_tk_environment() -> None:
    """
    Attempt to configure Tcl/Tk paths automatically for Homebrew and uv installs.

    This helps avoid the common "Can't find a usable init.tcl" error by locating the
    Tk data directories near the tkinter module or the current Python prefix.
    """
    if os.environ.get("TCL_LIBRARY") and os.environ.get("TK_LIBRARY"):
        return

    try:
        import tkinter
    except ImportError:
        return

    tk_path = Path(tkinter.__file__).resolve().parent
    candidates: List[Path] = []
    for parent in [tk_path, tk_path.parent, tk_path.parent.parent]:
        candidates.extend(
            [
                parent / "tcl8.6",
                parent / "tcl8.7",
                parent / "lib/tcl8.6",
                parent / "lib/tcl8.7",
                parent / "tk8.6",
                parent / "tk8.7",
                parent / "lib/tk8.6",
                parent / "lib/tk8.7",
            ]
        )

    for prefix in {sys.prefix, sys.exec_prefix, sys.base_prefix, sys.base_exec_prefix}:
        prefix_path = Path(prefix)
        candidates.extend(
            [
                prefix_path / "lib/tcl8.6",
                prefix_path / "lib/tk8.6",
                prefix_path / "lib/tcl8.7",
                prefix_path / "lib/tk8.7",
                prefix_path / "share/tcl8.6",
                prefix_path / "share/tk8.6",
                prefix_path / "share/tcl8.7",
                prefix_path / "share/tk8.7",
            ]
        )

    tcl_candidate = None
    tk_candidate = None

    for candidate in candidates:
        init_file = candidate / "init.tcl"
        if init_file.exists():
            if "tcl" in candidate.name and not tcl_candidate:
                tcl_candidate = candidate
            elif "tk" in candidate.name and not tk_candidate:
                tk_candidate = candidate
        if tcl_candidate and tk_candidate:
            break

    if tcl_candidate and "TCL_LIBRARY" not in os.environ:
        os.environ["TCL_LIBRARY"] = str(tcl_candidate)
    if tk_candidate and "TK_LIBRARY" not in os.environ:
        os.environ["TK_LIBRARY"] = str(tk_candidate)


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    """Parse command-line options."""
    parser = argparse.ArgumentParser(description="Browse the Plex media cache (Tk or CLI).")
    parser.add_argument("query", nargs="*", help="Search terms (default: show latest additions).")
    parser.add_argument(
        "--cli",
        action="store_true",
        help="Run in CLI mode (useful when Tk is unavailable).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help="Maximum number of results to show (default: %(default)s).",
    )
    parser.add_argument(
        "--deep",
        action="store_true",
        help="Force deep search (full-text across cached metadata).",
    )
    parser.add_argument(
        "--length",
        type=int,
        default=80,
        help="Maximum title width when printing CLI output.",
    )
    parser.add_argument(
        "--info",
        action="store_true",
        help="Include summaries beneath each CLI result.",
    )
    parser.add_argument(
        "--path",
        action="store_true",
        help="Include the file path beneath each CLI result.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Entry point for both CLI and GUI usage."""
    args = parse_args(argv)
    query = " ".join(args.query).strip()

    try:
        db_path = initialise_database()
    except RuntimeError as exc:
        print(f"media_tk: {exc}", file=sys.stderr)
        return 2

    display_args = Namespace(length=args.length, info=args.info, path=args.path)

    if args.cli:
        return run_cli_mode(
            db_path,
            query,
            limit=args.limit,
            display_args=display_args,
            deep=args.deep,
        )

    try:
        launch_gui(
            db_path,
            query,
            limit=args.limit,
        )
        return 0
    except RuntimeError as exc:
        print(f"media_tk: {exc}", file=sys.stderr)
        print("Falling back to CLI mode...", file=sys.stderr)
        return run_cli_mode(
            db_path,
            query,
            limit=args.limit,
            display_args=display_args,
            deep=args.deep,
        )


if __name__ == "__main__":
    raise SystemExit(main())


if __name__ == "__main__":
    main()


