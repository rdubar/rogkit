#!/usr/bin/env python3
"""Show local network interfaces and the current external IP."""

from __future__ import annotations

import argparse
import socket
import sys
from dataclasses import dataclass
from urllib.error import URLError
from urllib.request import urlopen

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


EXTERNAL_IP_SERVICES = (
    "https://api.ipify.org",
    "https://ifconfig.me/ip",
)


@dataclass(frozen=True)
class InterfaceInfo:
    """Summary of a network interface."""

    name: str
    ipv4: str
    netmask: str
    mac: str
    is_default: bool


def _print_message(message: str, *, style: str | None = None) -> None:
    """Print with optional Rich styling and a plain fallback."""
    if RICH_AVAILABLE:
        console.print(Text(message, style=style) if style else message)
    else:
        print(message)


def _is_loopback(name: str, ipv4: str) -> bool:
    """Return True when the interface looks like loopback."""
    return name.startswith("lo") or ipv4.startswith("127.")


def _link_families() -> set[int]:
    """Return the socket families used for MAC addresses on this platform."""
    families: set[int] = set()
    if hasattr(socket, "AF_LINK"):
        families.add(socket.AF_LINK)
    if hasattr(socket, "AF_PACKET"):
        families.add(socket.AF_PACKET)
    return families


def _default_interface() -> str | None:
    """Best-effort detection of the interface used for the default route."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            local_ip = sock.getsockname()[0]
    except OSError:
        return None

    for name, addrs in psutil.net_if_addrs().items():
        for addr in addrs:
            if addr.family == socket.AF_INET and addr.address == local_ip:
                return name
    return None


def list_interfaces(include_loopback: bool = False) -> list[InterfaceInfo]:
    """Return IPv4 network interfaces with netmask and MAC address."""
    default_name = _default_interface()
    link_families = _link_families()
    interfaces: list[InterfaceInfo] = []

    for name, addrs in psutil.net_if_addrs().items():
        ipv4 = ""
        netmask = ""
        mac = ""
        for addr in addrs:
            if addr.family == socket.AF_INET:
                ipv4 = addr.address or ""
                netmask = addr.netmask or ""
            elif addr.family in link_families:
                mac = addr.address or ""

        if not ipv4:
            continue
        if not include_loopback and _is_loopback(name, ipv4):
            continue

        interfaces.append(
            InterfaceInfo(
                name=name,
                ipv4=ipv4,
                netmask=netmask or "-",
                mac=mac or "-",
                is_default=name == default_name,
            )
        )

    interfaces.sort(key=lambda item: (not item.is_default, item.name.lower()))
    return interfaces


def fetch_external_ip(timeout: float = 2.0) -> str | None:
    """Return the current public IP address using a small set of HTTP endpoints."""
    for url in EXTERNAL_IP_SERVICES:
        try:
            with urlopen(url, timeout=timeout) as response:
                value = response.read().decode("utf-8").strip()
        except (URLError, TimeoutError, OSError):
            continue
        if value:
            return value
    return None


def render_interfaces(interfaces: list[InterfaceInfo], *, plain: bool = False) -> None:
    """Render interfaces as a Rich table or plain text."""
    if not interfaces:
        _print_message("No matching network interfaces.", style="yellow")
        return

    if RICH_AVAILABLE and not plain:
        table = Table(header_style="bold cyan", show_lines=False)
        table.add_column("Interface", style="bold")
        table.add_column("IPv4")
        table.add_column("Netmask")
        table.add_column("MAC")
        table.add_column("Default", justify="center")
        for item in interfaces:
            table.add_row(
                item.name,
                item.ipv4,
                item.netmask,
                item.mac,
                "yes" if item.is_default else "",
            )
        console.print(table)
        return

    print(f"{'INTERFACE':<12}  {'IPV4':<15}  {'NETMASK':<15}  {'MAC':<18}  DEFAULT")
    print("-" * 74)
    for item in interfaces:
        print(
            f"{item.name:<12}  {item.ipv4:<15}  {item.netmask:<15}  {item.mac:<18}  "
            f"{'yes' if item.is_default else ''}"
        )


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Show local network interfaces and the current external IP."
    )
    parser.add_argument("--all", action="store_true", help="Include loopback interfaces")
    parser.add_argument("--plain", action="store_true", help="Plain text output")
    parser.add_argument(
        "--no-external",
        action="store_true",
        help="Skip the external IP lookup",
    )
    return parser.parse_args()


def main() -> int:
    """CLI entry point."""
    _ = get_invoking_cwd()
    if not PSUTIL_AVAILABLE:
        print("error: psutil is required to inspect network interfaces", file=sys.stderr)
        return 1

    args = parse_args()
    interfaces = list_interfaces(include_loopback=args.all)
    render_interfaces(interfaces, plain=args.plain)

    if not args.no_external:
        external_ip = fetch_external_ip()
        message = f"External IP: {external_ip}" if external_ip else "External IP: unavailable"
        _print_message(message, style="green" if external_ip else "yellow")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
