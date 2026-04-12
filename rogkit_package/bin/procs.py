"""
Process finder and manager.

Searches running processes by name or command substring and optionally
terminates them. Uses psutil for cross-platform compatibility (Mac + Linux).

Usage:
    procs                  # top 20 processes by CPU usage
    procs foo              # processes matching "foo" in name or command
    procs foo --kill       # SIGTERM each match after confirmation
    procs foo --force      # SIGKILL each match, no confirmation
    procs --sort mem       # sort by memory instead of CPU
    procs --all            # show all processes (no limit)
"""

from __future__ import annotations

import argparse
import os
import signal
import sys
from dataclasses import dataclass
from typing import List, Optional

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:  # pragma: no cover
    PSUTIL_AVAILABLE = False

try:
    from rich.console import Console
    from rich.table import Table
    from rich.text import Text

    console = Console()
    RICH_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover
    console = None  # type: ignore[assignment]
    RICH_AVAILABLE = False

DEFAULT_LIMIT = 20


@dataclass
class ProcInfo:
    pid: int
    name: str
    status: str
    cpu_percent: float
    mem_percent: float
    cmdline: str


def _print(message: str, style: Optional[str] = None) -> None:
    if RICH_AVAILABLE:
        console.print(Text(message, style=style) if style else message)
    else:
        print(message)


def find_procs(pattern: Optional[str] = None) -> List[ProcInfo]:
    """Return matching ProcInfo entries, sorted by CPU descending."""
    results: List[ProcInfo] = []
    attrs = ["pid", "name", "status", "cpu_percent", "memory_percent", "cmdline"]
    for proc in psutil.process_iter(attrs):
        try:
            info = proc.info
            name = info.get("name") or ""
            cmd_parts = info.get("cmdline") or []
            cmd = " ".join(cmd_parts)
            if pattern:
                needle = pattern.lower()
                if needle not in name.lower() and needle not in cmd.lower():
                    continue
            results.append(ProcInfo(
                pid=info["pid"],
                name=name,
                status=info.get("status") or "",
                cpu_percent=info.get("cpu_percent") or 0.0,
                mem_percent=info.get("memory_percent") or 0.0,
                cmdline=cmd[:120] or name,
            ))
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    results.sort(key=lambda p: p.cpu_percent, reverse=True)
    return results


def render_procs(procs: List[ProcInfo], *, plain: bool = False) -> None:
    if not procs:
        _print("No matching processes.", style="yellow")
        return

    if RICH_AVAILABLE and not plain:
        table = Table(header_style="bold cyan", show_lines=False)
        table.add_column("PID", justify="right", style="dim", no_wrap=True)
        table.add_column("Name", style="bold")
        table.add_column("Status", no_wrap=True)
        table.add_column("CPU%", justify="right")
        table.add_column("MEM%", justify="right")
        table.add_column("Command", overflow="fold")
        for p in procs:
            cpu_style = "red" if p.cpu_percent > 50 else ("yellow" if p.cpu_percent > 10 else "")
            table.add_row(
                str(p.pid),
                p.name,
                p.status,
                Text(f"{p.cpu_percent:.1f}", style=cpu_style),
                f"{p.mem_percent:.1f}",
                p.cmdline,
            )
        console.print(table)
    else:
        print(f"{'PID':>7}  {'NAME':<20}  {'STATUS':<10}  {'CPU%':>5}  {'MEM%':>5}  COMMAND")
        print("-" * 80)
        for p in procs:
            print(f"{p.pid:>7}  {p.name:<20}  {p.status:<10}  {p.cpu_percent:>5.1f}  {p.mem_percent:>5.1f}  {p.cmdline[:60]}")


def kill_procs(procs: List[ProcInfo], *, force: bool = False) -> int:
    """Kill processes, prompting for confirmation unless force=True."""
    sig = signal.SIGKILL if force else signal.SIGTERM
    sig_name = "SIGKILL" if force else "SIGTERM"
    killed = 0
    for p in procs:
        if not force:
            try:
                answer = input(f"Kill PID {p.pid} ({p.name})? [y/N] ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if answer != "y":
                continue
        try:
            os.kill(p.pid, sig)
            _print(f"Sent {sig_name} to PID {p.pid} ({p.name})", style="green")
            killed += 1
        except ProcessLookupError:
            _print(f"PID {p.pid} already gone", style="dim")
        except PermissionError:
            _print(f"Permission denied: PID {p.pid} ({p.name})", style="bold red")
    return killed


def main() -> int:
    if not PSUTIL_AVAILABLE:
        print("error: psutil is required — run: uv add psutil", file=sys.stderr)
        return 1

    parser = argparse.ArgumentParser(
        description="Find and optionally kill processes by name or command."
    )
    parser.add_argument("pattern", nargs="?", help="Name/command substring to match")
    parser.add_argument("--kill", action="store_true", help="Terminate matches (SIGTERM, with confirmation)")
    parser.add_argument("--force", action="store_true", help="Kill matches immediately (SIGKILL, no confirmation)")
    parser.add_argument("--sort", choices=["cpu", "mem"], default="cpu", help="Sort field (default: cpu)")
    parser.add_argument("-n", "--limit", type=int, default=DEFAULT_LIMIT,
                        metavar="N", help=f"Max processes to show (default {DEFAULT_LIMIT})")
    parser.add_argument("--all", action="store_true", help="Show all matches without limit")
    parser.add_argument("--plain", action="store_true", help="Plain text output")
    args = parser.parse_args()

    procs = find_procs(pattern=args.pattern)

    if args.sort == "mem":
        procs.sort(key=lambda p: p.mem_percent, reverse=True)

    if not args.all:
        procs = procs[: args.limit]

    if args.kill or args.force:
        if not procs:
            _print("No matching processes to kill.", style="yellow")
            return 0
        render_procs(procs, plain=args.plain)
        kill_procs(procs, force=args.force)
        return 0

    render_procs(procs, plain=args.plain)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
