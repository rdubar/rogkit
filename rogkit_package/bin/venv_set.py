#!/usr/bin/env python3
"""
Virtual environment locator and activation helper.

- Scans the current directory for virtualenvs (prefers .venv, venv, env).
- Prints the activation command for your shell and copies it to the clipboard.
  (Clipboard copy is best-effort; disabled when pyclip is missing.)
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

from .clipboard import copy_to_clipboard

PREFERRED_NAMES = [".venv", "venv", "env"]
ACTIVATE_FILES = [
    ("bash", "bin/activate"),
    ("zsh", "bin/activate"),
    ("fish", "bin/activate.fish"),
    ("tcsh", "bin/activate.csh"),
    ("csh", "bin/activate.csh"),
    ("default", "bin/activate"),
]
WINDOWS_ACTIVATE = "Scripts/activate"


def _detect_shell(override: Optional[str] = None) -> str:
    if override:
        return override.lower()
    shell = os.environ.get("SHELL", "")
    return Path(shell).name.lower() if shell else "bash"


def _activation_script(env_path: Path, shell: str) -> Optional[Path]:
    candidates: List[str] = []
    for sh, rel in ACTIVATE_FILES:
        if sh == shell:
            candidates.append(rel)
    candidates.append(WINDOWS_ACTIVATE)
    # fallback default for any shell
    candidates.append("bin/activate")

    for rel in candidates:
        candidate = env_path / rel
        if candidate.exists():
            return candidate
    return None


def _score_env(path: Path) -> int:
    """Lower score = higher priority."""
    name = path.name
    if name in PREFERRED_NAMES:
        return PREFERRED_NAMES.index(name)
    return len(PREFERRED_NAMES)


def _find_envs(base: Path) -> List[Path]:
    """Return virtualenv directories directly under base (including base itself)."""
    envs: List[Path] = []

    def is_env(dir_path: Path) -> bool:
        return (dir_path / "bin" / "activate").exists() or (dir_path / WINDOWS_ACTIVATE).exists()

    if is_env(base):
        envs.append(base)

    for entry in base.iterdir():
        if not entry.is_dir():
            continue
        if is_env(entry):
            envs.append(entry)

    # Deduplicate and sort by preference then name for determinism
    unique = {env.resolve(): env for env in envs}
    sorted_envs = sorted(unique.values(), key=lambda p: (_score_env(p), p.name.lower()))
    return sorted_envs


def _format_command(activate_script: Path, shell: str) -> str:
    script = str(activate_script)
    if shell == "fish":
        return f"source {script}"
    if shell in {"csh", "tcsh"}:
        return f"source {script}"
    if os.name == "nt":
        return script  # let caller run directly in Windows shells
    return f"source {script}"


def _pick_env(envs: List[Path], name: Optional[str]) -> Optional[Path]:
    if not envs:
        return None
    if name:
        for env in envs:
            if env.name == name:
                return env
        return None
    return envs[0]


def _build_output(env: Path, shell: str, copy: bool) -> int:
    activate = _activation_script(env, shell)
    if not activate:
        print(f"No activation script found for shell '{shell}' in {env}")
        return 1
    cmd = _format_command(activate, shell)
    print(f"Virtualenv: {env}")
    print(f"Shell: {shell}")
    print(f"Activation: {cmd}")
    if copy:
        copy_to_clipboard(cmd, verbose=False)
        print("Copied activation command to clipboard (if clipboard is available).")
    return 0


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Locate a virtualenv and print the activation command.")
    parser.add_argument(
        "-n",
        "--name",
        help="Specific environment directory name to pick (default: prefer .venv/venv/env then first found).",
    )
    parser.add_argument(
        "-d",
        "--directory",
        default=".",
        help="Directory to scan for virtualenvs (default: current directory).",
    )
    parser.add_argument(
        "-s",
        "--shell",
        help="Shell to target for the activation command (default: inferred from $SHELL).",
    )
    parser.add_argument(
        "--no-copy",
        action="store_true",
        help="Do not copy the activation command to the clipboard.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    base = Path(args.directory).expanduser().resolve()
    if not base.exists():
        print(f"Directory not found: {base}")
        return 1
    if not base.is_dir():
        print(f"Not a directory: {base}")
        return 1

    envs = _find_envs(base)
    if not envs:
        print(f"No virtualenvs found in {base}")
        return 1

    shell = _detect_shell(args.shell)
    chosen = _pick_env(envs, args.name)
    if not chosen:
        print(f"No virtualenv named '{args.name}' found in {base}. Available: {[p.name for p in envs]}")
        return 1

    print(f"Found {len(envs)} virtualenv(s): {[p.name for p in envs]}")
    return _build_output(chosen, shell, not args.no_copy)


if __name__ == "__main__":
    raise SystemExit(main())
