#!/usr/bin/env python3
"""
Tk-based front end for the modern `media` CLI.

* Default mode launches a Tk interface that shells out to the core media command.
* `--cli` falls back to a terminal wrapper while still delegating to the same CLI.
"""

from __future__ import annotations

import argparse
import io
import os
import shlex
import sys
import threading
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import List, Optional, Sequence

DEFAULT_NUMBER = 10
DEFAULT_LENGTH = 80


def execute_media_cli(args: Sequence[str]) -> tuple[int, str, str]:
    """Execute the media CLI with the provided argument list and capture output."""
    from rogkit_package.media.media import main as media_main

    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()
    try:
        with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
            exit_code = media_main(args)
    except SystemExit as exc:
        code = exc.code
        exit_code = int(code) if isinstance(code, int) else 0
    except Exception as exc:  # pragma: no cover - defensive
        stderr_buffer.write(f"media CLI execution failed: {exc}\n")
        exit_code = 1
    return exit_code, stdout_buffer.getvalue(), stderr_buffer.getvalue()


def build_media_cli_args(
    query_terms: Sequence[str],
    *,
    number: int,
    length: int,
    info: bool,
    path: bool,
    stats: bool,
    deep: bool,
    all_items: bool,
    people: bool,
    sort: str,
    reverse: bool,
    zed: bool,
    use_daemon: bool,
    update: bool,
    update_plex: bool,
    rsync: bool,
    list_paths: bool,
    show_path: bool,
) -> List[str]:
    """Compose an argument list for the core media CLI."""
    args: List[str] = []
    if not use_daemon:
        args.append("--no-daemon")
    if update:
        args.append("--update")
    if update_plex:
        args.append("--update-plex")
    if rsync:
        args.append("--rsync")
    if list_paths:
        args.append("--list-paths")
    if show_path:
        args.append("--show-path")

    number = max(0, number)
    length = max(10, length)
    args.extend(["--number", str(number)])
    args.extend(["--length", str(length)])

    if info:
        args.append("--info")
    if path:
        args.append("--path")
    if stats:
        args.append("--stats")
    if deep:
        args.append("--deep")
    if all_items and not zed:
        args.append("--all")
    if people:
        args.append("--people")
    if zed:
        args.append("--zed")
    if sort and sort != "added":
        args.extend(["--sort", sort])
    if reverse:
        args.append("--reverse")

    args.extend(query_terms)
    return args


def run_cli_mode(args: argparse.Namespace) -> int:
    """Invoke the media CLI based on command-line options and print results."""
    media_args = build_media_cli_args(
        query_terms=args.query,
        number=args.limit,
        length=args.length,
        info=args.info,
        path=args.path,
        stats=args.stats,
        deep=args.deep,
        all_items=args.all,
        people=args.people,
        sort=args.sort,
        reverse=args.reverse,
        zed=args.zed,
        use_daemon=args.use_daemon,
        update=args.update,
        update_plex=args.update_plex,
        rsync=args.rsync,
        list_paths=args.list_paths,
        show_path=args.show_path,
    )
    exit_code, stdout_text, stderr_text = execute_media_cli(media_args)
    if stdout_text:
        print(stdout_text, end="")
    if stderr_text:
        print(stderr_text, file=sys.stderr, end="")
    return exit_code


def configure_tk_environment() -> None:
    """
    Attempt to configure Tcl/Tk paths automatically for Homebrew and uv installs.

    This helps avoid the common "Can't find a usable init.tcl" error by locating the
    Tk data directories near the tkinter module or the current Python prefix.
    """
    if os.environ.get("TCL_LIBRARY") and os.environ.get("TK_LIBRARY"):
        return

    try:
        import tkinter  # type: ignore
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


def launch_gui(args: argparse.Namespace) -> None:
    """Start the Tkinter interface and forward actions to the media CLI."""
    try:
        import tkinter as tk  # type: ignore
        from tkinter import messagebox, scrolledtext  # type: ignore
    except ImportError as exc:  # pragma: no cover - environment specific
        raise RuntimeError("Tkinter is not available in this Python installation.") from exc

    configure_tk_environment()

    try:
        root = tk.Tk()
    except tk.TclError as exc:  # pragma: no cover - environment specific
        raise RuntimeError(
            "Tkinter failed to initialise. Ensure Tcl/Tk is installed "
            "and the TCL_LIBRARY/TK_LIBRARY environment variables point to the "
            "directory containing init.tcl (try `brew install python-tk@3.12`)."
        ) from exc

    class SearchApp:
        """Tkinter application that shells out to the media CLI."""

        def __init__(self, master: tk.Tk, cli_defaults: argparse.Namespace):
            self.master = master
            self.worker: Optional[threading.Thread] = None
            self.last_args: List[str] = []
            self.master.title("Rog's Media Library")
            self.master.minsize(760, 520)

            initial_query = " ".join(cli_defaults.query)

            self.query_var = tk.StringVar(value=initial_query)
            self.limit_var = tk.IntVar(value=max(1, cli_defaults.limit))
            self.length_var = tk.IntVar(value=max(10, cli_defaults.length))
            self.sort_var = tk.StringVar(value=cli_defaults.sort)
            self.info_var = tk.BooleanVar(value=cli_defaults.info)
            self.path_var = tk.BooleanVar(value=cli_defaults.path)
            self.stats_var = tk.BooleanVar(value=cli_defaults.stats)
            self.deep_var = tk.BooleanVar(value=cli_defaults.deep)
            self.all_var = tk.BooleanVar(value=cli_defaults.all)
            self.people_var = tk.BooleanVar(value=cli_defaults.people)
            self.reverse_var = tk.BooleanVar(value=cli_defaults.reverse)
            self.zed_var = tk.BooleanVar(value=cli_defaults.zed)
            self.daemon_var = tk.BooleanVar(value=cli_defaults.use_daemon)

            # Search controls
            search_frame = tk.Frame(master)
            search_frame.pack(fill=tk.X, padx=10, pady=10)

            tk.Label(search_frame, text="Search").pack(side=tk.LEFT)
            self.search_entry = tk.Entry(search_frame, textvariable=self.query_var, width=50)
            self.search_entry.pack(side=tk.LEFT, padx=(6, 10), expand=True, fill=tk.X)
            self.search_entry.bind("<Return>", self.perform_search)
            tk.Button(search_frame, text="Search", command=self.perform_search).pack(side=tk.LEFT)
            tk.Button(search_frame, text="Clear", command=self.clear_search).pack(side=tk.LEFT, padx=(6, 0))

            # Option toggles
            options_frame = tk.LabelFrame(master, text="Options")
            options_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

            tk.Label(options_frame, text="Results").grid(row=0, column=0, sticky="w")
            tk.Spinbox(
                options_frame, from_=1, to=500, textvariable=self.limit_var, width=5
            ).grid(row=0, column=1, sticky="w")

            tk.Label(options_frame, text="Length").grid(row=0, column=2, sticky="w", padx=(10, 0))
            tk.Spinbox(
                options_frame, from_=20, to=160, textvariable=self.length_var, width=5
            ).grid(row=0, column=3, sticky="w")

            tk.Label(options_frame, text="Sort").grid(row=0, column=4, sticky="w", padx=(10, 0))
            tk.OptionMenu(options_frame, self.sort_var, "added", "title", "year").grid(
                row=0, column=5, sticky="w"
            )
            tk.Checkbutton(
                options_frame, text="Reverse", variable=self.reverse_var
            ).grid(row=0, column=6, sticky="w", padx=(10, 0))
            tk.Checkbutton(
                options_frame, text="Year mode (-z)", variable=self.zed_var
            ).grid(row=0, column=7, sticky="w", padx=(10, 0))

            tk.Checkbutton(options_frame, text="Info", variable=self.info_var).grid(
                row=1, column=0, sticky="w", pady=(4, 0)
            )
            tk.Checkbutton(options_frame, text="Path", variable=self.path_var).grid(
                row=1, column=1, sticky="w", pady=(4, 0)
            )
            tk.Checkbutton(options_frame, text="Stats", variable=self.stats_var).grid(
                row=1, column=2, sticky="w", pady=(4, 0)
            )
            tk.Checkbutton(options_frame, text="Deep search", variable=self.deep_var).grid(
                row=1, column=3, sticky="w", pady=(4, 0)
            )
            tk.Checkbutton(options_frame, text="All results", variable=self.all_var).grid(
                row=1, column=4, sticky="w", pady=(4, 0)
            )
            tk.Checkbutton(options_frame, text="People search", variable=self.people_var).grid(
                row=1, column=5, sticky="w", pady=(4, 0)
            )
            tk.Checkbutton(options_frame, text="Use daemon", variable=self.daemon_var).grid(
                row=1, column=6, sticky="w", pady=(4, 0)
            )

            # Operational buttons
            button_frame = tk.Frame(master)
            button_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
            tk.Button(button_frame, text="Update", command=self.run_update).pack(side=tk.LEFT)
            tk.Button(button_frame, text="Update (no extras)", command=self.run_update_plex).pack(
                side=tk.LEFT, padx=(6, 0)
            )
            tk.Button(button_frame, text="List Paths", command=self.run_list_paths).pack(
                side=tk.LEFT, padx=(6, 0)
            )
            tk.Button(button_frame, text="Show Path", command=self.run_show_path).pack(
                side=tk.LEFT, padx=(6, 0)
            )
            tk.Button(button_frame, text="Repeat Last", command=self.repeat_last).pack(
                side=tk.LEFT, padx=(6, 0)
            )

            # Output area
            self.text_area = scrolledtext.ScrolledText(master, wrap=tk.WORD, width=90, height=24)
            self.text_area.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
            self.text_area.config(state=tk.DISABLED)

            self.status_label = tk.Label(master, text="Ready.")
            self.status_label.pack(fill=tk.X, padx=10, pady=(0, 10))

            # Kick off an initial search once the UI settles.
            self.master.after(150, self.perform_search)

        def _build_search_args(
            self,
            *,
            query_terms: Optional[List[str]] = None,
            update: bool = False,
            update_plex: bool = False,
            list_paths: bool = False,
            show_path: bool = False,
        ) -> List[str]:
            if query_terms is None:
                query_text = self.query_var.get().strip()
                query_terms = shlex.split(query_text) if query_text else []
            return build_media_cli_args(
                query_terms=query_terms,
                number=self.limit_var.get(),
                length=self.length_var.get(),
                info=self.info_var.get(),
                path=self.path_var.get(),
                stats=self.stats_var.get(),
                deep=self.deep_var.get(),
                all_items=self.all_var.get(),
                people=self.people_var.get(),
                sort=self.sort_var.get(),
                reverse=self.reverse_var.get(),
                zed=self.zed_var.get(),
                use_daemon=self.daemon_var.get(),
                update=update,
                update_plex=update_plex,
                list_paths=list_paths,
                show_path=show_path,
            )

        def _run_media_command(self, media_args: List[str], description: str, *, remember: bool = True) -> None:
            if self.worker and self.worker.is_alive():
                messagebox.showinfo("media UI", "Another command is still running. Please wait.")
                return

            if remember:
                self.last_args = list(media_args)

            self.status_label.config(text=f"{description}…")
            self.text_area.config(state=tk.NORMAL)
            self.text_area.delete("1.0", tk.END)
            self.text_area.insert(tk.END, f"$ media {' '.join(media_args)}\n\nRunning…")
            self.text_area.config(state=tk.DISABLED)

            def task() -> None:
                exit_code, stdout_text, stderr_text = execute_media_cli(media_args)
                self.master.after(
                    0,
                    lambda: self._handle_result(
                        description,
                        exit_code,
                        stdout_text,
                        stderr_text,
                    ),
                )

            self.worker = threading.Thread(target=task, daemon=True)
            self.worker.start()

        def _handle_result(
            self,
            description: str,
            exit_code: int,
            stdout_text: str,
            stderr_text: str,
        ) -> None:
            self.worker = None
            combined = stdout_text.strip()
            stderr_stripped = stderr_text.strip()
            if stderr_stripped:
                if combined:
                    combined += "\n\n"
                combined += "[stderr]\n" + stderr_stripped
            if not combined:
                combined = "Command completed with no output."

            self.text_area.config(state=tk.NORMAL)
            self.text_area.delete("1.0", tk.END)
            self.text_area.insert(tk.END, combined)
            self.text_area.config(state=tk.DISABLED)

            status = f"{description} finished with exit code {exit_code}."
            if stderr_stripped:
                status += " See output above for details."
            self.status_label.config(text=status)

        def perform_search(self, event: Optional["tk.Event"] = None) -> None:  # type: ignore[name-defined]
            self._run_media_command(self._build_search_args(), "Search")

        def clear_search(self) -> None:
            self.query_var.set("")
            self._run_media_command(self._build_search_args(), "Search")

        def run_update(self) -> None:
            self._run_media_command(self._build_search_args(update=True), "Update")

        def run_update_plex(self) -> None:
            self._run_media_command(self._build_search_args(update_plex=True), "Update (no extras)")

        def run_list_paths(self) -> None:
            self._run_media_command(
                self._build_search_args(query_terms=[], list_paths=True), "List paths"
            )

        def run_show_path(self) -> None:
            self._run_media_command(
                self._build_search_args(query_terms=[], show_path=True), "Show path"
            )

        def repeat_last(self) -> None:
            if not self.last_args:
                messagebox.showinfo("media UI", "No command has been run yet.")
                return
            self._run_media_command(list(self.last_args), "Repeat command", remember=False)

    SearchApp(root, args)
    root.mainloop()


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    """Parse command-line options for the Tk/CLI wrapper."""
    parser = argparse.ArgumentParser(
        description="Tkinter or CLI wrapper around the rogkit media tool."
    )
    parser.add_argument(
        "query",
        nargs="*",
        help="Search terms forwarded to the media CLI.",
    )
    parser.add_argument(
        "--cli",
        action="store_true",
        help="Run in CLI mode (no Tk).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_NUMBER,
        help="Pass through to media --number (default: %(default)s).",
    )
    parser.add_argument(
        "--length",
        type=int,
        default=DEFAULT_LENGTH,
        help="Pass through to media --length (default: %(default)s).",
    )
    parser.add_argument("--info", action="store_true", help="Enable media --info output.")
    parser.add_argument("--path", action="store_true", help="Enable media --path output.")
    parser.add_argument("--stats", action="store_true", help="Enable media --stats output.")
    parser.add_argument("--deep", action="store_true", help="Enable media --deep searches.")
    parser.add_argument("--all", action="store_true", help="Include media --all flag.")
    parser.add_argument("--people", action="store_true", help="Include media --people flag.")
    parser.add_argument(
        "--sort",
        choices=("added", "title", "year"),
        default="added",
        help="Sort order forwarded to media (default: %(default)s).",
    )
    parser.add_argument("--reverse", action="store_true", help="Reverse sort order.")
    parser.add_argument("--zed", action="store_true", help="Enable media --zed year view.")
    parser.add_argument(
        "--use-daemon",
        action="store_true",
        help="Allow using the media daemon instead of forcing --no-daemon.",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="Run media --update before displaying results.",
    )
    parser.add_argument(
        "--update-plex",
        action="store_true",
        help="Run media --update-plex before displaying results.",
    )
    parser.add_argument(
        "--rsync",
        action="store_true",
        help="Prefer rsync for remote Plex database transfers.",
    )
    parser.add_argument(
        "--list-paths",
        action="store_true",
        help="Pass media --list-paths.",
    )
    parser.add_argument(
        "--show-path",
        action="store_true",
        help="Pass media --show-path.",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Entry point for both CLI and GUI usage."""
    args = parse_args(argv)
    if args.cli:
        return run_cli_mode(args)
    try:
        launch_gui(args)
    except RuntimeError as exc:
        print(f"media_tk: {exc}", file=sys.stderr)
        print("Falling back to CLI mode...", file=sys.stderr)
        return run_cli_mode(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
