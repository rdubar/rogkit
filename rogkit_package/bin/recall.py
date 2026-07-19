#!/usr/bin/env python3
"""Unified recent-activity timeline: "what did I do on this machine
yesterday?" currently has no answer short of archaeology. `recall` merges
git reflogs across ~/dev, Claude Code session starts, and `note` entries
into one queryable timeline.

Shell history is deliberately NOT a source unless zsh's EXTENDED_HISTORY
option is on (`: <epoch>:<duration>;<command>` lines) — plain history has no
timestamps, and fabricating them from file mtime would be dishonest.

Usage:
    recall                    # last 20 entries, most recent first
    recall yesterday          # entries since yesterday
    recall --since 3d --grep rogkit
"""

from __future__ import annotations

import argparse
import glob
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from .note import _get_notes_file, _parse_entries

try:
    from rich.console import Console
    from rich.text import Text

    console = Console()
    RICH_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover
    console = None
    RICH_AVAILABLE = False

DEFAULT_DEV_ROOT = Path.home() / "dev"
CLAUDE_PROJECTS_DIR = Path.home() / ".claude" / "projects"
DEFAULT_LIMIT = 20
EXTENDED_HISTORY_RE = re.compile(r"^: (\d+):(\d+);(.*)$")


@dataclass(frozen=True)
class TimelineEntry:
    timestamp: datetime
    source: str
    text: str


def _print(message: str, *, style: Optional[str] = None) -> None:
    if RICH_AVAILABLE:
        console.print(Text(message, style=style) if style else message)
    else:
        print(message)


def collect_shell_history(histfile: Optional[Path] = None) -> list[TimelineEntry]:
    """Only zsh's EXTENDED_HISTORY format (`: <epoch>:<dur>;<cmd>`) carries a
    timestamp — plain history lines are skipped rather than guessed at."""
    path = histfile or Path.home() / ".zsh_history"
    if not path.exists():
        return []
    entries = []
    try:
        raw = path.read_bytes().decode("utf-8", errors="replace")
    except OSError:
        return []
    for line in raw.splitlines():
        m = EXTENDED_HISTORY_RE.match(line)
        if not m:
            continue
        ts = datetime.fromtimestamp(int(m.group(1)))
        entries.append(TimelineEntry(ts, "shell", m.group(3).strip()))
    return entries


def _find_repos(root: Path, max_dirs: int = 200) -> list[Path]:
    if not root.is_dir():
        return []
    repos = []
    scanned = 0
    for child in sorted(root.iterdir()):
        if scanned >= max_dirs or not child.is_dir():
            continue
        scanned += 1
        if (child / ".git").exists():
            repos.append(child)
            continue
        for grandchild in sorted(child.iterdir()):
            if grandchild.is_dir() and (grandchild / ".git").exists():
                repos.append(grandchild)
    return repos


def collect_git_reflog(root: Path = DEFAULT_DEV_ROOT) -> list[TimelineEntry]:
    import subprocess

    entries = []
    for repo in _find_repos(root):
        try:
            result = subprocess.run(
                ["git", "-C", str(repo), "reflog", "--date=iso-strict", "--format=%cd %gs"],
                capture_output=True, text=True, timeout=5, check=False,
            )
        except (subprocess.SubprocessError, OSError):
            continue
        if result.returncode != 0:
            continue
        for line in result.stdout.splitlines():
            parts = line.split(" ", 1)
            if len(parts) != 2:
                continue
            try:
                ts = datetime.fromisoformat(parts[0])
            except ValueError:
                continue
            entries.append(TimelineEntry(ts.replace(tzinfo=None), f"git:{repo.name}", parts[1]))
    return entries


def collect_claude_sessions() -> list[TimelineEntry]:
    """One entry per session file (its earliest timestamp), reusing clu.py's
    project-directory glob — not a per-message transcript."""
    entries = []
    pattern = str(CLAUDE_PROJECTS_DIR / "**" / "*.jsonl")
    for path_str in glob.glob(pattern, recursive=True):
        path = Path(path_str)
        try:
            with open(path) as fh:
                for line in fh:
                    try:
                        d = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    ts_str = d.get("timestamp", "")
                    try:
                        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00")).replace(tzinfo=None)
                    except (ValueError, AttributeError):
                        continue
                    entries.append(TimelineEntry(ts, "claude", f"session in {path.parent.name}"))
                    break  # only need the first timestamped line per file
        except OSError:
            continue
    return entries


def collect_notes() -> list[TimelineEntry]:
    notes_file = _get_notes_file()
    if not notes_file.exists():
        return []
    entries = []
    for date_str, line in _parse_entries(notes_file.read_text(encoding="utf-8")):
        m = re.match(r"- \*\*(\d{2}):(\d{2})\*\* (.*)$", line)
        if not m or not date_str:
            continue
        try:
            ts = datetime.strptime(f"{date_str} {m.group(1)}:{m.group(2)}", "%Y-%m-%d %H:%M")
        except ValueError:
            continue
        entries.append(TimelineEntry(ts, "note", m.group(3)))
    return entries


def collect_timeline(root: Path = DEFAULT_DEV_ROOT) -> list[TimelineEntry]:
    entries = []
    entries.extend(collect_shell_history())
    entries.extend(collect_git_reflog(root))
    entries.extend(collect_claude_sessions())
    entries.extend(collect_notes())
    entries.sort(key=lambda e: e.timestamp, reverse=True)
    return entries


def resolve_period(value: str) -> datetime:
    """Parse "today", "yesterday", a duration like "3d", or an ISO date."""
    now = datetime.now()
    lowered = value.lower()
    if lowered == "today":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    if lowered == "yesterday":
        return (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    if lowered.endswith("d") and lowered[:-1].isdigit():
        return now - timedelta(days=int(lowered[:-1]))
    return datetime.fromisoformat(value)


def filter_entries(
    entries: list[TimelineEntry], since: Optional[datetime] = None, grep: Optional[str] = None
) -> list[TimelineEntry]:
    out = entries
    if since is not None:
        out = [e for e in out if e.timestamp >= since]
    if grep:
        needle = grep.lower()
        out = [e for e in out if needle in e.text.lower() or needle in e.source.lower()]
    return out


def render_timeline(entries: list[TimelineEntry]) -> None:
    if not entries:
        _print("No matching activity.", style="yellow")
        return
    current_day = ""
    for e in entries:
        day = e.timestamp.strftime("%Y-%m-%d")
        if day != current_day:
            current_day = day
            _print(f"\n{day}", style="bold cyan")
        _print(f"  {e.timestamp.strftime('%H:%M')}  [{e.source}] {e.text}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Unified recent-activity timeline for this machine.")
    parser.add_argument("period", nargs="?", help='Shorthand for --since: "today", "yesterday", "3d", or a date')
    parser.add_argument("--since", help='Duration ("3d"), a date, "today", or "yesterday"')
    parser.add_argument("--grep", help="Filter by substring in the entry text or source")
    parser.add_argument("-n", "--limit", type=int, default=DEFAULT_LIMIT, help=f"Max entries when no --since is given (default {DEFAULT_LIMIT})")
    parser.add_argument("--json", action="store_true", help="Structured JSON output")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    since_value = args.since or args.period
    since = None
    if since_value:
        try:
            since = resolve_period(since_value)
        except ValueError:
            _print(f"Unrecognized period/date: {since_value!r}", style="bold red")
            return 1

    entries = collect_timeline()
    entries = filter_entries(entries, since=since, grep=args.grep)
    if since is None:
        entries = entries[: args.limit]

    if args.json:
        print(json.dumps(
            [{"timestamp": e.timestamp.isoformat(), "source": e.source, "text": e.text} for e in entries],
            indent=2,
        ))
    else:
        render_timeline(entries)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
