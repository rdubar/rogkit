#!/usr/bin/env python3
"""Environment and configuration diagnostics for rogkit."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

from ..settings import root_dir
from .tomlr import get_rogkit_secrets_path, get_rogkit_toml_path, load_rogkit_toml

try:  # optional rich formatting
    from rich.console import Console
    from rich.table import Table
    from rich.text import Text

    console = Console()
    RICH_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover
    console = None
    RICH_AVAILABLE = False


ALIASES_PATH = Path(root_dir) / "aliases"


@dataclass
class CheckResult:
    """Structured result for a single doctor check."""

    name: str
    status: str
    summary: str
    details: list[str] = field(default_factory=list)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Run rogkit environment, config, and media diagnostics."
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit check results as JSON instead of formatted text.",
    )
    return parser.parse_args()


def _with_hints(details: list[str], *hints: str) -> list[str]:
    for hint in hints:
        details.append(f"hint: {hint}")
    return details


def _shell_startup_candidates(shell: str | None) -> list[Path]:
    shell_name = Path(shell or os.environ.get("SHELL", "")).name.lower()
    home = Path.home()
    if shell_name == "zsh":
        return [home / ".zshrc", home / ".zprofile"]
    if shell_name == "bash":
        return [home / ".bashrc", home / ".bash_profile", home / ".profile"]
    if shell_name == "fish":
        return [home / ".config" / "fish" / "config.fish"]
    return [home / ".profile"]


def _profile_sources_aliases(profile_path: Path, aliases_path: Path = ALIASES_PATH) -> bool:
    if not profile_path.exists():
        return False
    try:
        content = profile_path.read_text(encoding="utf-8")
    except OSError:
        return False

    aliases_str = str(aliases_path)
    patterns = (
        aliases_str,
        "~/dev/rogkit/aliases",
        "$ROGKIT/aliases",
        "source aliases",
        ". aliases",
    )
    return any(pattern in content for pattern in patterns)


def _mask_value(value: Any) -> str:
    if value in (None, "", [], {}):
        return "<empty>"
    return "<set>"


def _check_config() -> CheckResult:
    config_path = get_rogkit_toml_path()
    secrets_path = get_rogkit_secrets_path()
    details = [
        f"config: {config_path}",
        f"secrets: {secrets_path}",
    ]
    if not config_path.exists():
        return CheckResult(
            name="config",
            status="fail",
            summary="config.toml is missing.",
            details=_with_hints(
                details,
                "Run `setup --apply` to create the default rogkit config.",
                "Use `tomlr -d` to inspect the default config template.",
            ),
        )

    try:
        config = load_rogkit_toml()
    except SystemExit:
        return CheckResult(
            name="config",
            status="fail",
            summary="config.toml or secrets.toml could not be parsed.",
            details=_with_hints(
                details,
                "Run `tomlr --validate` to pinpoint the TOML parse issue.",
            ),
        )

    section_names = sorted(config.keys())
    details.append(f"sections: {', '.join(section_names)}")
    if secrets_path.exists():
        details.append("secrets.toml present and merged at load time.")
        return CheckResult(
            name="config",
            status="ok",
            summary="Config and secrets files are available.",
            details=details,
        )
    return CheckResult(
        name="config",
        status="warn",
        summary="Config loaded, but secrets.toml is missing.",
        details=_with_hints(
            details,
            "Create `secrets.toml` only if you need to store credentials separately from config.toml.",
        ),
    )


def _check_shell_setup() -> CheckResult:
    shell = os.environ.get("SHELL", "")
    candidates = _shell_startup_candidates(shell)
    details = [f"shell: {shell or '<unknown>'}"]
    existing_profiles = [path for path in candidates if path.exists()]
    details.extend(f"profile: {path}" for path in candidates)

    sourced_from = next(
        (path for path in existing_profiles if _profile_sources_aliases(path)),
        None,
    )
    if sourced_from is not None:
        details.append(f"aliases sourced from: {sourced_from}")
        return CheckResult(
            name="shell",
            status="ok",
            summary="A shell startup file appears to source rogkit aliases.",
            details=details,
        )

    if existing_profiles:
        details.append(f"expected aliases path: {ALIASES_PATH}")
        return CheckResult(
            name="shell",
            status="warn",
            summary="No shell startup file appears to source rogkit aliases.",
            details=_with_hints(
                details,
                "Run `setup --apply` to add the rogkit aliases source line automatically.",
                f'Or source them manually with: source "{ALIASES_PATH}"',
            ),
        )

    return CheckResult(
        name="shell",
        status="warn",
        summary="No known shell startup file was found to source rogkit aliases.",
        details=_with_hints(
            details,
            "Run `setup --shell-profile ~/.zshrc --apply` or pass the profile you want to update.",
        ),
    )


def _check_binaries() -> CheckResult:
    required = ("uv", "git")
    optional = ("fd", "ffmpeg", "rsync", "ollama", "ssh")
    missing_required = [name for name in required if shutil.which(name) is None]
    details = [
        *(f"{name}: {shutil.which(name) or 'missing'}" for name in required + optional),
    ]
    if missing_required:
        return CheckResult(
            name="binaries",
            status="fail",
            summary=f"Missing required binaries: {', '.join(missing_required)}.",
            details=_with_hints(
                details,
                f"Install required tools first: {', '.join(missing_required)}.",
            ),
        )

    missing_optional = [name for name in optional if shutil.which(name) is None]
    if missing_optional:
        return CheckResult(
            name="binaries",
            status="warn",
            summary=f"Required binaries are present; optional binaries missing: {', '.join(missing_optional)}.",
            details=_with_hints(
                details,
                "Missing optional tools only affect the rogkit commands that rely on them.",
            ),
        )

    return CheckResult(
        name="binaries",
        status="ok",
        summary="Required and common optional binaries are available.",
        details=details,
    )


def _check_media() -> CheckResult:
    try:
        from ..media.daemon import ping_daemon
        from ..media.helpers import detect_db_path, load_remote_config
        from ..media.media import _daemon_socket_path
    except Exception as exc:  # pragma: no cover - defensive import failure
        return CheckResult(
            name="media",
            status="fail",
            summary=f"Media diagnostics could not be loaded: {exc}",
        )

    remote = load_remote_config()
    socket_path = _daemon_socket_path()
    details: list[str] = [f"daemon socket: {socket_path}"]
    daemon_running = ping_daemon(socket_path, timeout=0.5)
    details.append(f"daemon: {'running' if daemon_running else 'not running'}")
    db_path = detect_db_path()
    details.append(f"detected db path: {db_path or '<not found>'}")

    if not remote:
        return CheckResult(
            name="media",
            status="warn",
            summary="No remote Plex/media configuration found.",
            details=_with_hints(
                details,
                "Add `media_files.server` / `media_files.user` or a `[plex_remote]` section if you use remote Plex sync.",
            ),
        )

    details.extend(
        [
            f"remote host: {remote.host}",
            f"remote user: {remote.username}",
            f"remote port: {remote.port}",
            f"remote password: {_mask_value(remote.password)}",
            f"remote db path: {remote.db_path}",
        ]
    )

    try:
        with socket.create_connection((remote.host, remote.port), timeout=2.0):
            reachable = True
    except OSError as exc:
        details.append(f"ssh reachability error: {exc}")
        reachable = False

    if not reachable:
        return CheckResult(
            name="media",
            status="fail",
            summary=f"SSH to {remote.host}:{remote.port} is not reachable.",
            details=_with_hints(
                details,
                f"Test SSH directly with: ssh {remote.username}@{remote.host}",
                "If the host is offline, bring it back first; otherwise re-check rogkit remote host settings.",
            ),
        )

    if daemon_running:
        return CheckResult(
            name="media",
            status="ok",
            summary="Media remote host is reachable and the media daemon is running.",
            details=details,
        )

    return CheckResult(
        name="media",
        status="warn",
        summary="Media remote host is reachable, but the media daemon is not running.",
        details=_with_hints(
            details,
            "Run `p` or `p --update-plex` to start the media daemon on demand.",
            "If the daemon seems stuck, try `p -S` and then run `p` again.",
        ),
    )


def run_checks() -> list[CheckResult]:
    """Run the default doctor check suite."""
    return [
        _check_config(),
        _check_shell_setup(),
        _check_binaries(),
        _check_media(),
    ]


def _render_plain(results: Iterable[CheckResult]) -> None:
    for result in results:
        print(f"[{result.status.upper()}] {result.name}: {result.summary}")
        for detail in result.details:
            print(f"  - {detail}")


def _render_rich(results: Iterable[CheckResult]) -> None:
    table = Table(title="rogkit doctor", show_lines=False)
    table.add_column("Status", style="bold")
    table.add_column("Check", style="cyan")
    table.add_column("Summary", style="white")
    table.add_column("Details", style="dim")

    status_styles = {
        "ok": "green",
        "warn": "yellow",
        "fail": "red",
    }
    for result in results:
        style = status_styles.get(result.status, "white")
        details = "\n".join(result.details)
        table.add_row(
            Text(result.status.upper(), style=style),
            result.name,
            result.summary,
            details,
        )
    console.print(table)


def main() -> int:
    """CLI entry point."""
    args = parse_args()
    results = run_checks()

    if args.json:
        print(json.dumps([asdict(result) for result in results], indent=2))
    elif RICH_AVAILABLE:
        _render_rich(results)
    else:
        _render_plain(results)

    return 1 if any(result.status == "fail" for result in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
