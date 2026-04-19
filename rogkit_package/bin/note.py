"""
Quick timestamped note-taking utility.

Appends notes to a Markdown file (default: ~/notes.md).
Each note is stored under a dated heading with a timestamp prefix.

Usage:
    note "remember this"          # append a note
    note -l                       # list recent notes
    note -l 20                    # list last 20 notes
    note -l query                 # filter notes by text
    note -f ~/work/notes.md "..."  # use a custom notes file

Configuration via ~/.config/rogkit/config.toml:

    [note]
    file = "~/notes.md"
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from .tomlr import get_config_value

try:
    from rich.console import Console
    from rich.rule import Rule
    from rich.text import Text

    console = Console()
    RICH_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover
    console = None  # type: ignore[assignment]
    RICH_AVAILABLE = False

DEFAULT_NOTES_FILE = Path.home() / "notes.md"
DEFAULT_LIST_COUNT = 10


def _get_notes_file(override: Optional[str] = None) -> Path:
    if override:
        return Path(override).expanduser()
    configured = get_config_value("note", "file")
    if configured:
        return Path(configured).expanduser()
    return DEFAULT_NOTES_FILE


def _print(message: str, style: Optional[str] = None) -> None:
    if RICH_AVAILABLE:
        console.print(Text(message, style=style) if style else message)
    else:
        print(message)


def append_note(text: str, notes_file: Path) -> None:
    """Append a timestamped note to the notes file."""
    now = datetime.now()
    date_heading = f"## {now.strftime('%Y-%m-%d')}"
    timestamp = now.strftime("%H:%M")
    entry = f"- **{timestamp}** {text}\n"

    notes_file.parent.mkdir(parents=True, exist_ok=True)

    existing = notes_file.read_text(encoding="utf-8") if notes_file.exists() else ""

    # If today's heading already exists, insert under it; otherwise append heading + entry.
    if date_heading in existing:
        heading_pos = existing.index(date_heading)
        rest = existing[heading_pos + len(date_heading):]
        next_section = re.search(r"\n## ", rest)
        if next_section:
            cut = heading_pos + len(date_heading) + next_section.start()
            updated = existing[:cut].rstrip("\n") + "\n" + entry + "\n" + existing[cut:].lstrip("\n")
        else:
            updated = existing.rstrip("\n") + "\n" + entry
    else:
        separator = "\n" if existing else ""
        updated = existing + f"{separator}{date_heading}\n\n" + entry

    notes_file.write_text(updated, encoding="utf-8")
    _print(f"[{timestamp}] {text}", style="green")


def _parse_entries(content: str) -> List[tuple[str, str]]:
    """Return list of (date_str, entry_line) pairs from notes file content."""
    entries: List[tuple[str, str]] = []
    current_date = ""
    for line in content.splitlines():
        if line.startswith("## "):
            current_date = line[3:].strip()
        elif line.startswith("- "):
            entries.append((current_date, line))
    return entries


def list_notes(
    notes_file: Path,
    count: int = DEFAULT_LIST_COUNT,
    query: Optional[str] = None,
) -> int:
    """Print recent notes, optionally filtered by query text."""
    if not notes_file.exists():
        _print(f"No notes file found at {notes_file}", style="bold yellow")
        return 1

    content = notes_file.read_text(encoding="utf-8")
    entries = _parse_entries(content)

    if query:
        q = query.lower()
        entries = [(d, e) for d, e in entries if q in d.lower() or q in e.lower()]

    entries = entries[-count:]

    if not entries:
        _print("No notes found.", style="bold yellow")
        return 0

    if RICH_AVAILABLE:
        console.print(Rule(f"[bold]Notes — {notes_file}", style="blue"))
    else:
        print(f"Notes — {notes_file}")
        print("-" * 40)

    current_date = ""
    for date_str, line in entries:
        if date_str != current_date:
            current_date = date_str
            if RICH_AVAILABLE:
                console.print(f"\n[bold cyan]{date_str}[/bold cyan]")
            else:
                print(f"\n{date_str}")
        # Render plain text by stripping markdown bold markers
        plain = re.sub(r"\*\*(.+?)\*\*", r"\1", line)
        if RICH_AVAILABLE:
            console.print(f"  {plain[2:]}")
        else:
            print(f"  {plain[2:]}")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Append or list timestamped notes in a Markdown file."
    )
    parser.add_argument("text", nargs="?", help="Note text to append")
    parser.add_argument(
        "-l", "--list",
        nargs="?",
        const=str(DEFAULT_LIST_COUNT),
        metavar="N_OR_QUERY",
        help=f"List recent notes; optionally pass a count (default {DEFAULT_LIST_COUNT}) or search query",
    )
    parser.add_argument("-f", "--file", metavar="PATH", help="Notes file path (overrides config)")
    args = parser.parse_args()

    notes_file = _get_notes_file(args.file)

    if args.list is not None:
        # -l may be a number (count) or a search string
        try:
            count = int(args.list)
            query = None
        except ValueError:
            count = DEFAULT_LIST_COUNT
            query = args.list
        return list_notes(notes_file, count=count, query=query)

    if args.text:
        append_note(args.text.strip(), notes_file)
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
