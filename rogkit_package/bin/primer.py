#!/usr/bin/env python3
"""Cold-start briefing for agents (and humans) starting a session on this machine.

Every agent session begins by re-deriving context: what OS, what's running,
which repos are dirty, what changed recently. `primer` emits a compact,
deterministic briefing instead — hostname/OS, uptime, disk headroom,
dirty/ahead repos under ~/dev, listening ports, recent notes, and (when the
`drift` binary is available) what changed since the last snapshot.

Usage:
    primer            # plain-text briefing
    primer --json      # structured output for agents
"""

from __future__ import annotations

import argparse
import json
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Any

from ..settings import root_dir
from .note import _get_notes_file, _parse_entries
from .ports import list_ports
from .tomlr import load_rogkit_toml

try:
    from rich.console import Console
    from rich.text import Text

    console = Console()
    RICH_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover
    console = None
    RICH_AVAILABLE = False

DEFAULT_DEV_ROOT = Path.home() / "dev"
RECENT_NOTES = 5
DEFAULT_SERVICES = (
    "plexmediaserver",
    "smbd",
    "transmission-daemon",
    "wayvnc",
    "tailscaled",
)
DEFAULT_MEDIA_MOUNTS = ("/mnt/media1", "/mnt/media2", "/mnt/media3", "/mnt/media4")


def _print(message: str, *, style: str | None = None) -> None:
    if RICH_AVAILABLE:
        console.print(Text(message, style=style) if style else message)
    else:
        print(message)


def _sibling_binary(name: str) -> str | None:
    """Locate another rogkit Go tool: $PATH first, then go/bin under the
    rogkit repo root — mirrors drift's own sibling-lookup so `primer` still
    finds `sysreboot`/`drift` even outside an interactive shell where the
    `aliases` file's PATH export never ran."""
    found = shutil.which(name)
    if found:
        return found
    candidate = Path(root_dir) / "go" / "bin" / name
    return str(candidate) if candidate.exists() else None


def _run_json(binary: str, *args: str) -> dict[str, Any] | None:
    path = _sibling_binary(binary)
    if not path:
        return None
    try:
        result = subprocess.run(
            [path, *args], capture_output=True, text=True, timeout=10, check=False
        )
        return json.loads(result.stdout)
    except (subprocess.SubprocessError, json.JSONDecodeError, OSError):
        return None


def collect_uptime() -> dict[str, Any] | None:
    """Uptime/load/mem come from `sysreboot --json` rather than
    re-implementing the same platform-specific sysctl/proc reads."""
    return _run_json("sysreboot", "--json")


def collect_disk() -> dict[str, Any]:
    total, used, free = shutil.disk_usage("/")
    return {"total_bytes": total, "used_bytes": used, "free_bytes": free, "usage_pct": used / total * 100}


def collect_repos(root: Path = DEFAULT_DEV_ROOT, max_depth_dirs: int = 200) -> list[dict[str, Any]]:
    """Scan root's immediate children (and one level deeper) for dirty/ahead
    git repos — same depth-2 shape as drift's Go collector, reimplemented
    here since the two tools don't share a language."""
    if not root.is_dir():
        return []
    repos: list[dict[str, Any]] = []
    scanned = 0
    for child in sorted(root.iterdir()):
        if scanned >= max_depth_dirs or not child.is_dir():
            continue
        scanned += 1
        if (child / ".git").exists():
            info = _repo_status(child.name, child)
            if info:
                repos.append(info)
            continue
        for grandchild in sorted(child.iterdir()):
            if not grandchild.is_dir() or not (grandchild / ".git").exists():
                continue
            info = _repo_status(f"{child.name}/{grandchild.name}", grandchild)
            if info:
                repos.append(info)
    return [r for r in repos if r["dirty"] > 0 or r["ahead"] > 0]


def _repo_status(name: str, path: Path) -> dict[str, Any] | None:
    try:
        status = subprocess.run(
            ["git", "-C", str(path), "status", "--porcelain"],
            capture_output=True, text=True, timeout=5, check=False,
        )
    except (subprocess.SubprocessError, OSError):
        return None
    dirty = len([line for line in status.stdout.splitlines() if line.strip()])

    ahead = 0
    rev_list = subprocess.run(
        ["git", "-C", str(path), "rev-list", "--left-right", "--count", "HEAD...@{u}"],
        capture_output=True, text=True, timeout=5, check=False,
    )
    if rev_list.returncode == 0:
        fields = rev_list.stdout.split()
        if len(fields) == 2:
            ahead = int(fields[0])

    return {"name": name, "dirty": dirty, "ahead": ahead}


def collect_notes(count: int = RECENT_NOTES) -> list[dict[str, str]]:
    notes_file = _get_notes_file()
    if not notes_file.exists():
        return []
    entries = _parse_entries(notes_file.read_text(encoding="utf-8"))
    return [{"date": d, "entry": e} for d, e in entries[-count:]]


def collect_drift() -> dict[str, Any] | None:
    """Folds in `drift --json -q`'s summary when the binary is available —
    the most valuable part of a cold-start briefing is "what changed since
    last time", which is exactly what drift already computes."""
    return _run_json("drift", "--json", "-q")


def _configured_list(key: str, default: tuple[str, ...]) -> list[str]:
    """Return a configured primer list, preserving explicit empty lists."""
    try:
        config = load_rogkit_toml().get("primer", {})
    except (AttributeError, OSError, TypeError):
        return list(default)
    value = config.get(key)
    if value is None:
        return list(default)
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return value
    return list(default)


def collect_services() -> list[dict[str, str]]:
    """Report configured systemd services when systemd exists."""
    if platform.system() != "Linux" or shutil.which("systemctl") is None:
        return []
    services = []
    for name in _configured_list("services", DEFAULT_SERVICES):
        try:
            result = subprocess.run(
                ["systemctl", "is-active", name],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except (subprocess.SubprocessError, OSError):
            status = "unknown"
        else:
            status = result.stdout.strip() or "unknown"
        services.append({"name": name, "status": status})
    return services


def collect_media_mounts() -> list[dict[str, str | bool]]:
    """Report configured media mount points on Linux."""
    if platform.system() != "Linux" or shutil.which("findmnt") is None:
        return []
    configured_mounts = _configured_list("media_mounts", DEFAULT_MEDIA_MOUNTS)
    try:
        result = subprocess.run(
            ["findmnt", "-rn", "-o", "TARGET,SOURCE,FSTYPE,OPTIONS"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (subprocess.SubprocessError, OSError):
        return []
    mounted: dict[str, dict[str, str | bool]] = {}
    for line in result.stdout.splitlines():
        fields = line.split(None, 3)
        if len(fields) != 4 or fields[0] not in configured_mounts:
            continue
        mounted[fields[0]] = {
            "target": fields[0],
            "source": fields[1],
            "fstype": fields[2],
            "options": fields[3],
            "mounted": True,
        }
    return [mounted.get(target, {"target": target, "mounted": False}) for target in configured_mounts]


def collect_briefing() -> dict[str, Any]:
    ports = list_ports()
    return {
        "hostname": platform.node(),
        "os": f"{platform.system()} {platform.release()}",
        "sysreboot": collect_uptime(),
        "disk": collect_disk(),
        "repos": collect_repos(),
        "ports": [{"port": p.port, "proto": p.proto, "process": p.process_name} for p in ports],
        "services": collect_services(),
        "media_mounts": collect_media_mounts(),
        "notes": collect_notes(),
        "drift": collect_drift(),
    }


def render_briefing(b: dict[str, Any]) -> None:
    _print(f"{b['hostname']} · {b['os']}", style="bold cyan")

    sys = b["sysreboot"]
    if sys:
        _print(f"up {sys['uptime_seconds'] // 3600}h · load {sys['load1']:.2f} ({sys['cores']} cores) · {sys['verdict']}")

    disk = b["disk"]
    _print(f"disk: {disk['used_bytes'] / 1e9:.1f} GB used ({disk['usage_pct']:.0f}%)")

    if b["drift"]:
        d = b["drift"]
        if d.get("first_run"):
            _print("drift: no previous snapshot — this run is now the baseline")
        elif d.get("change_count"):
            _print(f"drift: {d['change_count']} change(s) since last snapshot ({d.get('notable_count', 0)} notable)", style="yellow" if d.get("notable_count") else None)
        else:
            _print("drift: no changes since last snapshot", style="green")

    repos = b["repos"]
    if repos:
        _print(f"\n{len(repos)} repo(s) need attention:", style="bold")
        for r in repos:
            bits = []
            if r["dirty"]:
                bits.append(f"{r['dirty']} dirty")
            if r["ahead"]:
                bits.append(f"{r['ahead']} ahead")
            _print(f"  {r['name']}: {', '.join(bits)}")
    else:
        _print("\nAll ~/dev repos clean.", style="green")

    ports = b["ports"]
    _print(f"\n{len(ports)} listening port(s)" + (f" — {', '.join(sorted({p['process'] for p in ports})[:6])}" if ports else ""))

    services = b["services"]
    if services:
        _print("\nMedia services:", style="bold")
        for service in services:
            style = "green" if service["status"] == "active" else "yellow"
            _print(f"  {service['name']}: {service['status']}", style=style)

    mounts = b["media_mounts"]
    if mounts:
        mounted = sum(1 for mount in mounts if mount["mounted"])
        _print(f"\nMedia mounts: {mounted}/{len(mounts)} mounted")

    notes = b["notes"]
    if notes:
        _print("\nRecent notes:", style="bold")
        for n in notes:
            _print(f"  {n['entry']}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Cold-start briefing for this machine.")
    parser.add_argument("--json", action="store_true", help="Structured JSON output")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    briefing = collect_briefing()
    if args.json:
        print(json.dumps(briefing, indent=2))
    else:
        render_briefing(briefing)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
