#!/usr/bin/env python3
"""
A small cross-platform helper to start/stop/status an OpenVPN tunnel.

- Prefers an installed openvpn binary (brew on macOS, package on Linux).
- Uses a PID file for tracking, writes a log file, and avoids renaming binaries.
- Designed to work on macOS (M3) and Raspberry Pi OS (Pi 5).
"""

import argparse
import difflib
import os
import platform
import random
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Iterable, Optional, Sequence


DEFAULT_CONFIG_DIR = Path.home() / ".config" / "vpner"
DEFAULT_STATE_DIR = Path.home() / ".vpnctl"
DEFAULT_PID_FILE = DEFAULT_STATE_DIR / "openvpn.pid"
DEFAULT_LOG_FILE = DEFAULT_STATE_DIR / "openvpn.log"


KNOWN_OPENVPN_PATHS = [
    "/opt/homebrew/sbin/openvpn",  # Homebrew on Apple Silicon
    "/usr/local/opt/openvpn/sbin/openvpn",  # Homebrew on Intel
    "/usr/local/sbin/openvpn",
    "/usr/sbin/openvpn",
    "/usr/bin/openvpn",
]


def find_openvpn(user_hint: Optional[str]) -> Path:
    if user_hint:
        hint = Path(user_hint).expanduser()
        if hint.is_file() and os.access(hint, os.X_OK):
            return hint
        raise SystemExit(f"--openvpn-bin {hint} is not executable")

    from_shutil = shutil_which("openvpn")
    if from_shutil:
        return Path(from_shutil)

    for path in KNOWN_OPENVPN_PATHS:
        candidate = Path(path)
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate

    raise SystemExit(
        "openvpn not found. Install it (brew install openvpn on macOS; "
        "sudo apt install openvpn on Raspberry Pi OS) or pass --openvpn-bin."
    )


def shutil_which(binary: str) -> Optional[str]:
    # Local wrapper to avoid importing shutil at module import time.
    import shutil

    return shutil.which(binary)


def ensure_state_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def is_root() -> bool:
    if hasattr(os, "geteuid"):
        return os.geteuid() == 0
    return False


def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def read_pid(pid_file: Path) -> Optional[int]:
    try:
        value = pid_file.read_text().strip()
        return int(value) if value else None
    except FileNotFoundError:
        return None
    except ValueError:
        return None


def write_pidfile(pid_file: Path, pid: int) -> None:
    pid_file.write_text(str(pid))


def remove_pidfile(pid_file: Path) -> None:
    try:
        pid_file.unlink()
    except FileNotFoundError:
        pass


def resolve_config(args: argparse.Namespace) -> Path:
    # Priority: explicit --config, then fuzzy match of positional target, otherwise random from config dir.
    if args.config:
        cfg = Path(args.config).expanduser()
        if cfg.exists():
            return cfg
        raise SystemExit(f"Config not found: {cfg}")

    config_dir = Path(args.config_dir).expanduser()
    if not config_dir.exists():
        hint = (
            f"Config directory not found: {config_dir}\n"
            f"Create it and add .ovpn files, or pass --config-dir to override.\n"
            f"Example: mkdir -p {config_dir} && cp /path/to/profile.ovpn {config_dir}/"
        )
        raise SystemExit(hint)

    profiles = sorted(config_dir.glob("*.ovpn"))
    if not profiles:
        raise SystemExit(f"No .ovpn profiles found in {config_dir}")

    target = args.target
    if target:
        maybe_path = Path(target).expanduser()
        if maybe_path.exists():
            return maybe_path
        matched = match_config_name(target, profiles)
        if matched:
            print(f"Using config '{matched.name}' for search term '{target}'.")
            return matched
        names = ", ".join(p.name for p in profiles)
        raise SystemExit(f"No config matching '{target}' in {config_dir}. Available: {names}")

    chosen = random.choice(profiles)
    print(f"No target provided; selecting random profile: {chosen.name}")
    return chosen


def detect_auth_file(config: Path) -> Optional[Path]:
    try:
        content = config.read_text().splitlines()
    except OSError:
        return None

    for line in content:
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", ";")):
            continue
        parts = stripped.split()
        if parts and parts[0].lower() == "auth-user-pass":
            if len(parts) >= 2:
                return Path(parts[1]).expanduser()
            return None
    return None


def match_config_name(target: str, profiles: Sequence[Path]) -> Optional[Path]:
    wanted = target.lower()

    exact = [p for p in profiles if p.stem.lower() == wanted]
    if exact:
        return exact[0]

    contains = [p for p in profiles if wanted in p.stem.lower()]
    if len(contains) == 1:
        return contains[0]
    if len(contains) > 1:
        best_partial = difflib.get_close_matches(wanted, [p.stem.lower() for p in contains], n=1, cutoff=0.0)
        if best_partial:
            return next(p for p in contains if p.stem.lower() == best_partial[0])

    stems = [p.stem.lower() for p in profiles]
    closest = difflib.get_close_matches(wanted, stems, n=1, cutoff=0.0)
    if closest:
        return next(p for p in profiles if p.stem.lower() == closest[0])

    return None


def start_vpn(args: argparse.Namespace) -> None:
    if not is_root():
        raise SystemExit("Start requires root privileges to create VPN interfaces. Re-run with sudo.")

    openvpn_bin = find_openvpn(args.openvpn_bin)
    config = resolve_config(args)

    auth_file = detect_auth_file(config)
    if auth_file and not auth_file.exists():
        hint = (
            f"Credentials file not found: {auth_file}\n"
            f"Create it with two lines (username then password) and lock it down:\n"
            f"  mkdir -p {auth_file.parent}\n"
            f"  printf 'USERNAME\\nPASSWORD\\n' > {auth_file}\n"
            f"  chmod 600 {auth_file}"
        )
        raise SystemExit(hint)

    ensure_state_dir(DEFAULT_STATE_DIR)
    pid_file = Path(args.pid_file).expanduser()
    log_file = Path(args.log_file).expanduser()

    existing_pid = read_pid(pid_file)
    if existing_pid and pid_alive(existing_pid):
        raise SystemExit(f"OpenVPN already running (pid {existing_pid}). Use stop first.")

    cmd = [
        str(openvpn_bin),
        "--config",
        str(config),
        "--daemon",
        "--writepid",
        str(pid_file),
        "--log",
        str(log_file),
    ]
    if args.extra:
        cmd.extend(args.extra)

    print(f"Starting OpenVPN using {config} ...")
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"Failed to start OpenVPN (exit {exc.returncode}). See {log_file}.") from exc

    # Allow OpenVPN to write the PID file before we proceed.
    time.sleep(1)
    pid = read_pid(pid_file)
    if not pid or not pid_alive(pid):
        raise SystemExit(f"OpenVPN did not start or no pid recorded in {pid_file}. See {log_file}.")

    print(f"OpenVPN started with pid {pid}. Log: {log_file}")


def stop_vpn(args: argparse.Namespace) -> None:
    if not is_root():
        raise SystemExit("Stop requires root privileges to signal OpenVPN. Re-run with sudo.")

    pid_file = Path(args.pid_file).expanduser()
    pid = read_pid(pid_file)
    if not pid:
        raise SystemExit(f"No pid file at {pid_file}; is OpenVPN running?")

    if not pid_alive(pid):
        print(f"Process {pid} not running. Cleaning up pid file.")
        remove_pidfile(pid_file)
        return

    print(f"Stopping OpenVPN pid {pid} ...")
    os.kill(pid, signal.SIGTERM)

    wait_seconds = args.timeout
    for _ in range(wait_seconds * 10):
        if not pid_alive(pid):
            break
        time.sleep(0.1)

    if pid_alive(pid):
        print(f"OpenVPN did not exit after {wait_seconds}s, sending SIGKILL.")
        os.kill(pid, signal.SIGKILL)
        time.sleep(0.5)

    if pid_alive(pid):
        raise SystemExit("Unable to stop OpenVPN (process still alive).")

    remove_pidfile(pid_file)
    print("OpenVPN stopped.")


def status_vpn(args: argparse.Namespace) -> None:
    pid_file = Path(args.pid_file).expanduser()
    pid = read_pid(pid_file)
    alive = pid_alive(pid) if pid else False
    if pid and alive:
        print(f"OpenVPN running (pid {pid}).")
    elif pid and not alive:
        print(f"OpenVPN pid file exists but process {pid} is not running.")
    else:
        print("OpenVPN not running (no pid file).")

    iface_state = detect_tunnel_interface()
    if iface_state:
        print(f"Tunnel interface detected: {iface_state}")
    else:
        print("No tunnel interface detected.")

    if args.check_ip:
        ip = fetch_public_ip()
        print(f"Public IP: {ip}")


def detect_tunnel_interface() -> Optional[str]:
    system = platform.system().lower()
    candidates: Iterable[str]
    if system == "darwin":
        candidates = ("utun0", "utun1", "utun2")
    else:
        candidates = ("tun0", "tun1", "tap0", "tap1")

    if shutil_which("ip"):
        output = run_and_get_stdout(["ip", "addr", "show"])
    else:
        output = run_and_get_stdout(["ifconfig"])

    if not output:
        return None

    for name in candidates:
        if name in output:
            return name
    return None


def run_and_get_stdout(cmd: list[str]) -> str:
    try:
        res = subprocess.run(cmd, check=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        return res.stdout or ""
    except FileNotFoundError:
        return ""


def fetch_public_ip() -> str:
    import urllib.error
    import urllib.request

    url = "https://api.ipify.org"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            return resp.read().decode("utf-8").strip()
    except (urllib.error.URLError, TimeoutError):
        return "unavailable"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Cross-platform OpenVPN helper.")

    sub = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--pid-file",
        default=str(DEFAULT_PID_FILE),
        help=f"PID file path (default: {DEFAULT_PID_FILE})",
    )
    common.add_argument(
        "--log-file",
        default=str(DEFAULT_LOG_FILE),
        help=f"Log file path (default: {DEFAULT_LOG_FILE})",
    )
    common.add_argument(
        "--openvpn-bin",
        default=None,
        help="Path to openvpn binary (optional; auto-detected otherwise).",
    )

    start = sub.add_parser("start", parents=[common], help="Start OpenVPN.")
    start.add_argument(
        "target",
        nargs="?",
        help="Config name (from --config-dir) or explicit path to .ovpn.",
    )
    start.add_argument(
        "--config-dir",
        default=str(DEFAULT_CONFIG_DIR),
        help=f"Directory containing .ovpn files for name-based selection (default: {DEFAULT_CONFIG_DIR}).",
    )
    start.add_argument(
        "--config",
        default=None,
        help="Explicit path to .ovpn (overrides target/config-dir).",
    )
    start.add_argument(
        "--extra",
        nargs=argparse.ZERO_OR_MORE,
        help="Additional args passed to openvpn verbatim.",
    )

    stop = sub.add_parser("stop", parents=[common], help="Stop OpenVPN.")
    stop.add_argument(
        "--timeout",
        type=int,
        default=5,
        help="Seconds to wait for graceful shutdown before SIGKILL (default: 5).",
    )

    status = sub.add_parser("status", parents=[common], help="Show VPN status.")
    status.add_argument(
        "--check-ip",
        action="store_true",
        help="Fetch and display public IP address.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    command = args.command

    if command == "start":
        start_vpn(args)
    elif command == "stop":
        stop_vpn(args)
    elif command == "status":
        status_vpn(args)
    else:
        raise SystemExit(f"Unknown command {command}")


if __name__ == "__main__":
    main()
