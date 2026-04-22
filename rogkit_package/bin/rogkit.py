#!/usr/bin/env python3
"""Top-level rogkit command."""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

from .. import __author__, __license__, __title__, __url__, __version__
from . import doctor as doctor_cmd
from . import setup as setup_cmd

COMMAND_GROUPS: dict[str, tuple[str, ...]] = {
    "Top-level": ("doctor", "setup", "update", "--version", "--credits", "--help"),
    "AI & LLM": ("aish", "chat", "clu", "lm"),
    "Files": ("archive", "backup", "dedupe", "delete", "json", "purge", "serve"),
    "System": ("doctor", "httpcheck", "myip", "ports", "procs", "syscheck"),
    "Media": ("p", "media_files", "media_scan", "shrink", "spot", "vido"),
    "Data & text": ("bytes", "csv", "env", "hash", "note", "ts", "url"),
}


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level rogkit parser."""
    parser = argparse.ArgumentParser(
        prog=__title__,
        description="Rog's personal utility toolkit.",
        epilog=(
            "Examples: `rogkit doctor`, `rogkit setup --apply`, "
            "`rogkit --credits`, `rogkit update --full`"
        ),
    )
    parser.add_argument(
        "command",
        nargs="?",
        choices=("doctor", "setup", "update", "credits", "help"),
        help="Top-level rogkit command to run.",
    )
    parser.add_argument(
        "command_args",
        nargs=argparse.REMAINDER,
        help="Arguments passed through to the selected subcommand.",
    )
    parser.add_argument(
        "-V",
        "--version",
        action="store_true",
        help="Show the rogkit version and exit.",
    )
    parser.add_argument(
        "--credits",
        action="store_true",
        help="Show credits and project metadata.",
    )
    parser.add_argument(
        "-u",
        "--update",
        action="store_true",
        help="Run the rogkit updater and exit.",
    )
    return parser


def _print_credits() -> None:
    print(f"{__title__} v{__version__}")
    print(f"Author: {__author__}")
    print(f"License: {__license__}")
    print(f"Repo: {__url__}")


def _print_command_overview() -> None:
    """Print a friendly overview of commonly available rogkit commands."""
    print(f"{__title__} v{__version__}")
    print("Personal utility toolkit with 85+ commands.")
    print()
    print("Common commands:")
    for heading, commands in COMMAND_GROUPS.items():
        print(f"  {heading:<12} {'  '.join(commands)}")
    print()
    print("Use `rogkit --help` for CLI help, `rogkit --credits` for project info,")
    print("or source the repo `aliases` file for the short command names.")


def _run_update(argv: list[str] | None = None) -> int:
    """Run the rogkit update helper script."""
    script_path = Path(__file__).with_name("update")
    bash_path = shutil.which("bash")
    if bash_path is None:
        print("Error: `bash` is required to run the rogkit updater.")
        return 1
    result = subprocess.run(
        [bash_path, str(script_path), *(argv or [])],
        check=False,
    )
    return result.returncode


def _show_command_help(topic: str | None) -> int:
    """Render help for the top-level command or a specific subcommand."""
    if topic == "doctor":
        try:
            doctor_cmd.parse_args(["--help"])
        except SystemExit as exc:
            return int(exc.code or 0)
        return 0
    if topic == "setup":
        try:
            setup_cmd.parse_args(["--help"])
        except SystemExit as exc:
            return int(exc.code or 0)
        return 0
    if topic == "update":
        return _run_update(["--help"])
    build_parser().print_help()
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = build_parser()
    args, extras = parser.parse_known_args(argv)
    forwarded_args = [*args.command_args, *extras]

    if args.version:
        print(f"{__title__} {__version__}")
        return 0

    if args.credits or args.command == "credits":
        _print_credits()
        return 0

    if args.update or args.command == "update":
        return _run_update(forwarded_args)

    if args.command == "doctor":
        return doctor_cmd.main(forwarded_args)

    if args.command == "setup":
        return setup_cmd.main(forwarded_args)

    if args.command == "help":
        topic = forwarded_args[0] if forwarded_args else None
        return _show_command_help(topic)

    if forwarded_args:
        parser.error(f"unrecognized arguments: {' '.join(forwarded_args)}")

    _print_command_overview()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
