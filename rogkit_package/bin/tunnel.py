#!/usr/bin/env python3
"""Manage SSH DB tunnels and live-fetched credentials for ERP/Odoo13/P2P systems.

Single registry ([[tunnel.entry]] blocks in ~/.config/rogkit/config.toml) instead of
one-off shell aliases per system/tier. Passwords are fetched live via `rbw` (Vaultwarden
CLI) at connect time rather than copied into a local file, so a rotated credential can't
silently go stale.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess

from .tomlr import get_config_value

try:
    from rich.console import Console
    from rich.table import Table
    from rich.text import Text

    console = Console()
    RICH_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover
    console = None  # type: ignore[assignment]
    RICH_AVAILABLE = False


_TARGET_RE = re.compile(r"-L\s*127\.0\.0\.1:(\d+):([\w.\-]+):(\d+)")


def _print_message(message: str, *, style: str | None = None) -> None:
    """Print with optional Rich styling and a plain fallback."""
    if RICH_AVAILABLE:
        console.print(Text(message, style=style) if style else message)
    else:
        print(message)


def _entries() -> list[dict]:
    """Return all registered [[tunnel.entry]] blocks."""
    entries = get_config_value("tunnel", "entry")
    return entries if isinstance(entries, list) else []


def _find_entry(system: str, tier: str) -> dict | None:
    """Look up a single registered entry by system + tier."""
    for entry in _entries():
        if entry.get("system") == system and entry.get("tier") == tier:
            return entry
    return None


def _require_entry(args: argparse.Namespace) -> dict | None:
    """Look up the entry for args.system/args.tier, printing an error if missing."""
    entry = _find_entry(args.system, args.tier)
    if entry is None:
        _print_message(
            f"No registered entry for {args.system}/{args.tier}. "
            "Run 'tunnel list' to see what's configured.",
            style="red",
        )
    return entry


def _target_host(entry: dict, *, writer: bool) -> str | None:
    """Pick the read-only host unless --writer was given or none is configured."""
    if writer:
        return entry.get("host_rw")
    return entry.get("host_ro") or entry.get("host_rw")


def _listener_pids(port: int) -> list[int]:
    """Return PIDs of ssh processes forwarding 127.0.0.1:<port>."""
    try:
        result = subprocess.run(
            ["pgrep", "-f", rf"ssh.*-L[[:space:]]*127\.0\.0\.1:{port}:"],
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return []
    return [int(pid) for pid in result.stdout.split() if pid.strip().isdigit()]


def _tunnel_target(pid: int) -> str | None:
    """Best-effort: read the ssh command line for a pid to see its forward target."""
    try:
        result = subprocess.run(["ps", "-p", str(pid), "-wwo", "command="], capture_output=True, text=True)
    except FileNotFoundError:
        return None
    match = _TARGET_RE.search(result.stdout)
    return match.group(2) if match else None


def cmd_list(args: argparse.Namespace) -> int:
    """List every registered entry and whether its tunnel is currently open."""
    entries = _entries()
    if not entries:
        _print_message(
            "No tunnel entries registered. Add [[tunnel.entry]] blocks to "
            "~/.config/rogkit/config.toml.",
            style="yellow",
        )
        return 0

    rows = []
    for entry in entries:
        port = entry.get("local_port")
        pids = _listener_pids(port) if port else []
        status = "open" if pids else "closed"
        rows.append((entry.get("system", "?"), entry.get("tier", "?"), str(port or "-"), status))

    if RICH_AVAILABLE and not args.plain:
        table = Table(header_style="bold cyan")
        for col in ("System", "Tier", "Local port", "Status"):
            table.add_column(col)
        for row in rows:
            table.add_row(*row, style="green" if row[3] == "open" else None)
        console.print(table)
    else:
        for row in rows:
            print("  ".join(row))
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    """Show whether a specific tunnel is open, and verify its actual target."""
    entry = _require_entry(args)
    if entry is None:
        return 1

    port = entry.get("local_port")
    pids = _listener_pids(port) if port else []
    if not pids:
        _print_message(f"{args.system}/{args.tier}: closed (no listener on {port})", style="yellow")
        return 0

    target = _tunnel_target(pids[0])
    expected = _target_host(entry, writer=args.writer)
    _print_message(f"{args.system}/{args.tier}: open on port {port}, pid {pids[0]}", style="green")
    _print_message(f"  forwarding to: {target or 'unknown'}")
    if expected and target != expected:
        _print_message(
            f"  WARNING: expected {expected} -- verify before trusting results from this tunnel",
            style="red",
        )
    return 0


def cmd_open(args: argparse.Namespace) -> int:
    """Open a tunnel for the given system/tier, unless one is already open."""
    entry = _require_entry(args)
    if entry is None:
        return 1

    port = entry.get("local_port")
    host = _target_host(entry, writer=args.writer)
    if not port or not host:
        _print_message(
            f"Incomplete registry entry for {args.system}/{args.tier} "
            f"(local_port={port!r}, host={host!r}). Fill in ~/.config/rogkit/config.toml.",
            style="red",
        )
        return 1

    pids = _listener_pids(port)
    if pids:
        target = _tunnel_target(pids[0])
        if target == host:
            _print_message(f"{args.system}/{args.tier} already open on port {port} -> {host}", style="green")
            return 0
        _print_message(
            f"Port {port} already has a tunnel open to a different target ({target}). "
            f"Run 'tunnel close {args.system} {args.tier}' first.",
            style="red",
        )
        return 1

    bastion_user = entry.get("bastion_user", "tunnel")
    bastion_host = entry.get("bastion_host")
    remote_port = entry.get("remote_port", 5432)
    if not bastion_host:
        _print_message(f"No bastion_host configured for {args.system}/{args.tier}.", style="red")
        return 1

    cmd = [
        "ssh", "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null",
        "-f", "-N", "-T", "-M",
        "-L", f"127.0.0.1:{port}:{host}:{remote_port}",
        f"{bastion_user}@{bastion_host}",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        _print_message(f"Failed to open tunnel: {result.stderr.strip()}", style="red")
        return 1

    _print_message(
        f"Opened {args.system}/{args.tier}: 127.0.0.1:{port} -> {host}:{remote_port} via {bastion_host}",
        style="green",
    )
    return 0


def cmd_close(args: argparse.Namespace) -> int:
    """Close one tunnel, or every open tunnel with --all."""
    if args.all:
        targets = _entries()
    else:
        if not args.system or not args.tier:
            _print_message("Provide a system and tier, or use --all to close every open tunnel.", style="red")
            return 1
        entry = _require_entry(args)
        if entry is None:
            return 1
        targets = [entry]

    closed_any = False
    for entry in targets:
        port = entry.get("local_port")
        pids = _listener_pids(port) if port else []
        for pid in pids:
            os.kill(pid, 15)
            closed_any = True
            _print_message(f"Closed {entry.get('system')}/{entry.get('tier')} (port {port}, pid {pid})")

    if not closed_any:
        _print_message("No matching open tunnels.", style="yellow")
    return 0


def _rbw_password(item: str) -> str | None:
    """Fetch a password via rbw. Returns None (with a printed reason) on failure."""
    try:
        result = subprocess.run(["rbw", "get", item], capture_output=True, text=True)
    except FileNotFoundError:
        _print_message("rbw not found. Install with: brew install rbw", style="red")
        return None
    if result.returncode != 0:
        _print_message(
            f"rbw get '{item}' failed: {result.stderr.strip()}. Try 'rbw unlock' first.",
            style="red",
        )
        return None
    return result.stdout.strip()


def _entry_password(entry: dict) -> str | None:
    """Fetch an entry's password: prefer rbw (vaultwarden_item), fall back to env_var.

    The env_var fallback exists for systems not yet migrated to Vaultwarden (e.g. P2P,
    which as of 2026-09-10 has no Vaultwarden entry at all -- confirmed via `rbw list`).
    It carries the exact same staleness risk as the old .env_apv approach; prefer adding
    a Vaultwarden entry and switching to vaultwarden_item when one exists.
    """
    item = entry.get("vaultwarden_item", "")
    if item:
        return _rbw_password(item)

    env_var = entry.get("env_var", "")
    if env_var:
        value = os.environ.get(env_var)
        if not value:
            _print_message(f"${env_var} is not set in this shell's environment.", style="red")
            return None
        return value

    _print_message("No vaultwarden_item or env_var configured for this entry.", style="red")
    return None


def cmd_db(args: argparse.Namespace) -> int:
    """Ensure the tunnel is open, fetch the password, and exec psql."""
    entry = _require_entry(args)
    if entry is None:
        return 1

    if cmd_open(args) != 0:
        return 1

    password = _entry_password(entry)
    if password is None:
        return 1

    port = entry["local_port"]
    db_user = entry.get("db_user", "")
    db_name = entry.get("db_name", "")
    env = dict(os.environ, PGPASSWORD=password)
    conninfo = f"host=127.0.0.1 port={port} user={db_user} dbname={db_name} sslmode=prefer"
    try:
        os.execvpe("psql", ["psql", conninfo], env)
    except FileNotFoundError:
        _print_message("psql not found on PATH.", style="red")
        return 1


def cmd_pw(args: argparse.Namespace) -> int:
    """Fetch the password for an entry, printing or copying it to the clipboard."""
    entry = _require_entry(args)
    if entry is None:
        return 1

    item = entry.get("vaultwarden_item", "")
    if item:
        cmd = ["rbw", "get", item]
        if args.clipboard:
            cmd.append("--clipboard")
        result = subprocess.run(cmd)
        return result.returncode

    password = _entry_password(entry)
    if password is None:
        return 1
    if args.clipboard:
        subprocess.run(["pbcopy"], input=password.encode())
        _print_message("Copied to clipboard.", style="green")
    else:
        print(password)
    return 0


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Manage SSH DB tunnels and live-fetched credentials for ERP/Odoo13/P2P systems."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="List all registered entries and their status")
    p_list.add_argument("--plain", action="store_true", help="Plain text output")
    p_list.set_defaults(func=cmd_list)

    p_status = sub.add_parser("status", help="Show whether a tunnel is open and verify its target")
    p_status.add_argument("system")
    p_status.add_argument("tier")
    p_status.add_argument("--writer", action="store_true", help="Check against the writer endpoint")
    p_status.set_defaults(func=cmd_status)

    p_open = sub.add_parser("open", help="Open a tunnel")
    p_open.add_argument("system")
    p_open.add_argument("tier")
    p_open.add_argument("--writer", action="store_true", help="Use the writer endpoint instead of read-only")
    p_open.set_defaults(func=cmd_open)

    p_close = sub.add_parser("close", help="Close a tunnel")
    p_close.add_argument("system", nargs="?")
    p_close.add_argument("tier", nargs="?")
    p_close.add_argument("--all", action="store_true", help="Close every open tunnel")
    p_close.set_defaults(func=cmd_close)

    p_db = sub.add_parser("db", help="Open a tunnel (if needed) and launch psql with a live-fetched password")
    p_db.add_argument("system")
    p_db.add_argument("tier")
    p_db.add_argument("--writer", action="store_true", help="Use the writer endpoint instead of read-only")
    p_db.set_defaults(func=cmd_db)

    p_pw = sub.add_parser("pw", help="Fetch the password for an entry via rbw")
    p_pw.add_argument("system")
    p_pw.add_argument("tier")
    p_pw.add_argument("-c", "--clipboard", action="store_true", help="Copy to clipboard instead of printing")
    p_pw.set_defaults(func=cmd_pw)

    return parser.parse_args()


def main() -> int:
    """CLI entry point."""
    args = parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
