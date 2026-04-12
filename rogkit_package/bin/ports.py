#!/usr/bin/env python3
"""Show listening ports with their owning processes."""

from __future__ import annotations

import argparse
import re
import socket
import subprocess
import sys
from dataclasses import dataclass
from shutil import which

from ..settings import get_invoking_cwd

try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:  # pragma: no cover
    psutil = None  # type: ignore[assignment]
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


LISTEN_STATUS = "LISTEN"
LSOF_PATTERN = re.compile(
    r"^(?P<process>\S+)\s+"
    r"(?P<pid>\d+)\s+.*?\s"
    r"(?P<proto>TCP|UDP)\s+"
    r"(?P<address>\S+?):(?P<port>\d+)(?:\s+\((?P<status>[^)]+)\))?$"
)


@dataclass(frozen=True)
class PortInfo:
    """A listening TCP or UDP socket with process metadata."""

    port: int
    proto: str
    address: str
    pid: int | None
    process_name: str


def _print_message(message: str, *, style: str | None = None) -> None:
    """Print with optional Rich styling and a plain fallback."""
    if RICH_AVAILABLE:
        console.print(Text(message, style=style) if style else message)
    else:
        print(message)


def _socket_proto(sock_type: int) -> str | None:
    """Map socket type constants to printable protocol names."""
    if sock_type == socket.SOCK_STREAM:
        return "tcp"
    if sock_type == socket.SOCK_DGRAM:
        return "udp"
    return None


def _process_name(pid: int | None, cache: dict[int, str]) -> str:
    """Resolve a PID to a process name, caching lookups."""
    if pid is None:
        return "-"
    if pid in cache:
        return cache[pid]
    try:
        name = psutil.Process(pid).name()
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        name = "?"
    cache[pid] = name
    return name


def _port_matches(item: PortInfo, port: int | None, proc_filter: str | None) -> bool:
    """Return True when a PortInfo matches the active filters."""
    if port is not None and item.port != port:
        return False
    if proc_filter and proc_filter.lower() not in item.process_name.lower():
        return False
    return True


def _list_ports_psutil(port: int | None = None, proc_filter: str | None = None) -> list[PortInfo]:
    """Collect listening ports using psutil."""
    proc_text = proc_filter.lower() if proc_filter else None
    name_cache: dict[int, str] = {}
    results: list[PortInfo] = []

    for conn in psutil.net_connections(kind="inet"):
        proto = _socket_proto(conn.type)
        if proto is None or not conn.laddr:
            continue

        is_tcp_listener = proto == "tcp" and conn.status == LISTEN_STATUS
        is_udp_bound = proto == "udp"
        if not is_tcp_listener and not is_udp_bound:
            continue

        local_port = conn.laddr.port
        if port is not None and local_port != port:
            continue

        process_name = _process_name(conn.pid, name_cache)
        if proc_text and proc_text not in process_name.lower():
            continue

        results.append(
            PortInfo(
                port=local_port,
                proto=proto,
                address=getattr(conn.laddr, "ip", "") or "*",
                pid=conn.pid,
                process_name=process_name,
            )
        )

    return results


def _parse_lsof_output(output: str, port: int | None = None, proc_filter: str | None = None) -> list[PortInfo]:
    """Parse `lsof -nP -i` output into PortInfo rows."""
    results: list[PortInfo] = []
    for line in output.splitlines()[1:]:
        match = LSOF_PATTERN.match(line.strip())
        if not match:
            continue
        proto = match.group("proto").lower()
        status = match.group("status") or ""
        if proto == "tcp" and status != LISTEN_STATUS:
            continue
        item = PortInfo(
            port=int(match.group("port")),
            proto=proto,
            address=match.group("address"),
            pid=int(match.group("pid")),
            process_name=match.group("process").replace("\\x20", " "),
        )
        if _port_matches(item, port, proc_filter):
            results.append(item)
    return results


def _list_ports_lsof(port: int | None = None, proc_filter: str | None = None) -> list[PortInfo]:
    """Collect listening ports using lsof as a fallback when psutil is blocked."""
    if which("lsof") is None:
        return []
    result = subprocess.run(
        ["lsof", "-nP", "-iTCP", "-sTCP:LISTEN"],
        capture_output=True,
        text=True,
        check=False,
    )
    tcp_ports = _parse_lsof_output(result.stdout, port=port, proc_filter=proc_filter)

    result = subprocess.run(
        ["lsof", "-nP", "-iUDP"],
        capture_output=True,
        text=True,
        check=False,
    )
    udp_ports = _parse_lsof_output(result.stdout, port=port, proc_filter=proc_filter)
    return tcp_ports + udp_ports


def list_ports(port: int | None = None, proc_filter: str | None = None) -> list[PortInfo]:
    """Return listening/bound ports filtered by port number and process text."""
    results: list[PortInfo] = []
    if PSUTIL_AVAILABLE:
        try:
            results = _list_ports_psutil(port=port, proc_filter=proc_filter)
        except (psutil.AccessDenied, PermissionError, OSError):
            results = []
    if not results:
        results = _list_ports_lsof(port=port, proc_filter=proc_filter)
    results.sort(key=lambda item: (item.port, item.proto, item.process_name.lower(), item.pid or -1))
    return results


def render_ports(ports: list[PortInfo], *, plain: bool = False) -> None:
    """Render ports as a Rich table or aligned plain text."""
    if not ports:
        _print_message("No matching listening ports.", style="yellow")
        return

    if RICH_AVAILABLE and not plain:
        table = Table(header_style="bold cyan", show_lines=False)
        table.add_column("Port", justify="right", no_wrap=True)
        table.add_column("Proto", no_wrap=True)
        table.add_column("Address", overflow="fold")
        table.add_column("PID", justify="right", no_wrap=True)
        table.add_column("Process", overflow="fold")
        for item in ports:
            pid_text = "-" if item.pid is None else str(item.pid)
            table.add_row(str(item.port), item.proto, item.address, pid_text, item.process_name)
        console.print(table)
        return

    print(f"{'PORT':>6}  {'PROTO':<5}  {'ADDRESS':<15}  {'PID':>7}  PROCESS")
    print("-" * 60)
    for item in ports:
        pid_text = "-" if item.pid is None else str(item.pid)
        print(f"{item.port:>6}  {item.proto:<5}  {item.address:<15}  {pid_text:>7}  {item.process_name}")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Show listening TCP/UDP ports with their owning processes."
    )
    parser.add_argument("port", nargs="?", type=int, help="Filter to a specific port number")
    parser.add_argument("--proc", metavar="NAME", help="Filter by process name substring")
    parser.add_argument("--plain", action="store_true", help="Plain text output")
    return parser.parse_args()


def main() -> int:
    """CLI entry point."""
    _ = get_invoking_cwd()
    args = parse_args()
    ports = list_ports(port=args.port, proc_filter=args.proc)
    if not ports:
        _print_message(
            "No matching listening ports. If you expected results, try `ports --plain` or run the underlying module with sudo.",
            style="yellow",
        )
        return 0

    render_ports(ports, plain=args.plain)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
