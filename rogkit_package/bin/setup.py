#!/usr/bin/env python3
"""Bootstrap rogkit config and shell integration."""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from ..settings import root_dir
from .tomlr import get_rogkit_secrets_path, get_rogkit_toml_path, setup_rogkit_toml

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
class SetupResult:
    """Structured result for a single setup action."""

    name: str
    status: str
    summary: str
    details: list[str] = field(default_factory=list)


def _print_message(message: str, *, style: str | None = None) -> None:
    if RICH_AVAILABLE:
        console.print(Text(message, style=style) if style else message)
    else:
        print(message)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Set up rogkit config files and shell aliases.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write changes instead of only previewing them.",
    )
    parser.add_argument(
        "-y",
        "--yes",
        dest="apply",
        action="store_true",
        help="Alias for --apply.",
    )
    parser.add_argument(
        "--shell-profile",
        type=Path,
        help="Explicit shell profile to update (for example ~/.zshrc).",
    )
    parser.add_argument(
        "--skip-shell",
        action="store_true",
        help="Skip shell profile checks and updates.",
    )
    parser.add_argument(
        "--skip-config",
        action="store_true",
        help="Skip rogkit config checks and creation.",
    )
    return parser.parse_args(argv)


def _detect_shell_name(shell: str | None = None) -> str:
    return Path(shell or os.environ.get("SHELL", "")).name.lower()


def _default_profile_for_shell(shell_name: str) -> Path | None:
    home = Path.home()
    if shell_name == "zsh":
        return home / ".zshrc"
    if shell_name == "bash":
        return home / ".bashrc"
    return None


def _profile_sources_aliases(profile_path: Path, aliases_path: Path | None = None) -> bool:
    aliases_path = aliases_path or ALIASES_PATH
    if not profile_path.exists():
        return False
    try:
        content = profile_path.read_text(encoding="utf-8")
    except OSError:
        return False

    patterns = (
        str(aliases_path),
        "~/dev/rogkit/aliases",
        "$ROGKIT/aliases",
        'source "aliases"',
        "source aliases",
        ". aliases",
    )
    return any(pattern in content for pattern in patterns)


def _source_line(aliases_path: Path | None = None) -> str:
    aliases_path = aliases_path or ALIASES_PATH
    return f'source "{aliases_path}"'


def _ensure_config(*, apply: bool) -> SetupResult:
    config_path = get_rogkit_toml_path()
    secrets_path = get_rogkit_secrets_path()
    details = [
        f"config: {config_path}",
        f"secrets: {secrets_path}",
    ]

    if config_path.exists():
        details.append("config.toml already exists.")
        if secrets_path.exists():
            details.append("secrets.toml already exists.")
        else:
            details.append("secrets.toml does not exist yet; create it only when needed.")
        return SetupResult(
            name="config",
            status="ok",
            summary="Rogkit config is already present.",
            details=details,
        )

    if not apply:
        details.append("Run with --apply to create the default config.toml.")
        return SetupResult(
            name="config",
            status="warn",
            summary="Rogkit config.toml would be created.",
            details=details,
        )

    setup_rogkit_toml()
    details.append("Created default config.toml.")
    details.append("secrets.toml remains optional and can be created later.")
    return SetupResult(
        name="config",
        status="changed",
        summary="Created rogkit config.toml.",
        details=details,
    )


def _ensure_shell_profile(
    *,
    apply: bool,
    explicit_profile: Path | None,
    shell_name: str,
) -> SetupResult:
    if explicit_profile is not None:
        profile_path = explicit_profile.expanduser()
    else:
        profile_path = _default_profile_for_shell(shell_name)

    details = [
        f"shell: {shell_name or '<unknown>'}",
        f"aliases: {ALIASES_PATH}",
    ]

    if explicit_profile is None and shell_name == "fish":
        details.append("rogkit aliases use bash/zsh syntax and are not safe to source from fish config.")
        return SetupResult(
            name="shell",
            status="warn",
            summary="Shell auto-setup is not supported for fish.",
            details=details,
        )

    if profile_path is None:
        details.append("Pass --shell-profile to choose a profile manually.")
        return SetupResult(
            name="shell",
            status="warn",
            summary="Could not determine which shell profile to update.",
            details=details,
        )

    details.append(f"profile: {profile_path}")

    if _profile_sources_aliases(profile_path):
        details.append("Profile already sources rogkit aliases.")
        return SetupResult(
            name="shell",
            status="ok",
            summary="Shell profile is already configured for rogkit.",
            details=details,
        )

    line = _source_line()
    details.append(f"line: {line}")
    if not apply:
        details.append("Run with --apply to add this line to the profile.")
        return SetupResult(
            name="shell",
            status="warn",
            summary="Shell profile would be updated to source rogkit aliases.",
            details=details,
        )

    profile_path.parent.mkdir(parents=True, exist_ok=True)
    existing = ""
    if profile_path.exists():
        existing = profile_path.read_text(encoding="utf-8")
    with profile_path.open("a", encoding="utf-8") as handle:
        if existing and not existing.endswith("\n"):
            handle.write("\n")
        handle.write("\n# rogkit\n")
        handle.write(f"{line}\n")

    details.append("Added source line to shell profile.")
    return SetupResult(
        name="shell",
        status="changed",
        summary="Updated shell profile to load rogkit aliases.",
        details=details,
    )


def run_setup(args: argparse.Namespace) -> list[SetupResult]:
    """Run the setup workflow and return structured results."""
    results: list[SetupResult] = []
    shell_name = _detect_shell_name()

    if not args.skip_config:
        results.append(_ensure_config(apply=args.apply))
    if not args.skip_shell:
        results.append(
            _ensure_shell_profile(
                apply=args.apply,
                explicit_profile=args.shell_profile,
                shell_name=shell_name,
            )
        )
    return results


def _render_plain(results: Iterable[SetupResult]) -> None:
    for result in results:
        print(f"[{result.status.upper()}] {result.name}: {result.summary}")
        for detail in result.details:
            print(f"  - {detail}")


def _render_rich(results: Iterable[SetupResult]) -> None:
    table = Table(title="rogkit setup", show_lines=False)
    table.add_column("Status", style="bold")
    table.add_column("Step", style="cyan")
    table.add_column("Summary", style="white")
    table.add_column("Details", style="dim")

    status_styles = {
        "ok": "green",
        "warn": "yellow",
        "changed": "cyan",
        "fail": "red",
    }
    for result in results:
        style = status_styles.get(result.status, "white")
        table.add_row(
            Text(result.status.upper(), style=style),
            result.name,
            result.summary,
            "\n".join(result.details),
        )
    console.print(table)


def _print_next_steps(args: argparse.Namespace, results: list[SetupResult]) -> None:
    if not results:
        return

    changed = any(result.status == "changed" for result in results)
    shell_changed = any(result.name == "shell" and result.status == "changed" for result in results)
    config_changed = any(result.name == "config" and result.status == "changed" for result in results)

    if not args.apply:
        _print_message("Preview only. Re-run with --apply or -y to make these changes.", style="yellow")
        return

    if shell_changed:
        _print_message(f'Load aliases now with: source "{ALIASES_PATH}"', style="green")
    if config_changed:
        _print_message(f"Review your config at: {get_rogkit_toml_path()}", style="green")
    if not changed:
        _print_message("Nothing needed changing; rogkit setup already looks good.", style="green")


def main() -> int:
    """CLI entry point."""
    args = parse_args()
    results = run_setup(args)

    if RICH_AVAILABLE:
        _render_rich(results)
    else:
        _render_plain(results)

    _print_next_steps(args, results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
