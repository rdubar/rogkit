#!/usr/bin/env python3
"""Audit .env-style files: list keys without values, flag placeholders, diff against example."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from ..settings import get_invoking_cwd
from ._envsec import classify_value

try:
    from rich.console import Console
    from rich.table import Table
    from rich.text import Text

    console = Console()
    RICH_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover
    console = None  # type: ignore[assignment]
    RICH_AVAILABLE = False


ENV_FILENAMES = (
    ".env",
    ".env.local",
    ".env.development",
    ".env.dev",
    ".env.production",
    ".env.prod",
    ".env.staging",
    ".env.test",
    ".env.testing",
    ".env.example",
    ".env.sample",
    ".env.template",
    ".env.dist",
    ".envrc",
)

EXAMPLE_SUFFIXES = (".example", ".sample", ".template", ".dist")

SKIP_DIRS = {
    ".git",
    "node_modules",
    "__pycache__",
    "venv",
    ".venv",
    "env",
    ".tox",
    ".mypy_cache",
    ".ruff_cache",
    "dist",
    "build",
    "target",
}

LINE_RE = re.compile(
    r"""^
    (?:export\s+)?
    (?P<key>[A-Za-z_][A-Za-z0-9_]*)
    \s*=\s*
    (?P<value>.*)
    $""",
    re.VERBOSE,
)


@dataclass(frozen=True)
class EnvKey:
    """A single key parsed from a .env-style file."""

    key: str
    raw_value: str
    status: str  # "set" | "empty" | "placeholder"

    @property
    def is_real(self) -> bool:
        return self.status == "set"


def _strip_quotes(value: str) -> str:
    """Strip surrounding single or double quotes from a value."""
    value = value.strip()
    # Trim trailing inline comment for unquoted values (best-effort)
    if value and value[0] not in ("'", '"'):
        if " #" in value:
            value = value.split(" #", 1)[0].rstrip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def parse_env_file(path: Path) -> list[EnvKey]:
    """Parse an env-style file and return its keys with status."""
    keys: list[EnvKey] = []
    try:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError as exc:
        raise RuntimeError(f"cannot read {path}: {exc}") from exc
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = LINE_RE.match(line)
        if not match:
            continue
        key = match.group("key")
        value = _strip_quotes(match.group("value"))
        keys.append(EnvKey(key=key, raw_value=value, status=classify_value(value)))
    return keys


def discover_env_files(target: Path, *, recursive: bool) -> list[Path]:
    """Find env-style files at or under target."""
    if target.is_file():
        return [target]
    if not target.is_dir():
        return []

    results: list[Path] = []
    if recursive:
        for path in sorted(target.rglob(".env*")):
            if any(part in SKIP_DIRS for part in path.parts):
                continue
            if path.is_file():
                results.append(path)
    else:
        for name in ENV_FILENAMES:
            candidate = target / name
            if candidate.is_file():
                results.append(candidate)
        # Also pick up any .env.* the user named themselves
        for path in sorted(target.glob(".env*")):
            if path.is_file() and path not in results:
                results.append(path)
    return results


def find_example_for(path: Path) -> Path | None:
    """Return the sibling example file for a real .env, if any."""
    if any(path.name.endswith(suffix) for suffix in EXAMPLE_SUFFIXES):
        return None
    for suffix in EXAMPLE_SUFFIXES:
        candidate = path.with_name(path.name + suffix)
        if candidate.is_file():
            return candidate
    return None


def _status_style(status: str) -> str:
    return {"set": "green", "placeholder": "yellow", "empty": "red"}.get(status, "")


def _print(message: str = "", *, style: str | None = None) -> None:
    if RICH_AVAILABLE:
        console.print(Text(message, style=style) if style else message)
    else:
        print(message)


def render_file(keys: list[EnvKey], *, plain: bool, display_path: str) -> None:
    """Render one file's keys."""
    if not keys:
        _print(f"{display_path}: (no keys)", style="dim")
        return

    if RICH_AVAILABLE and not plain:
        table = Table(
            title=display_path,
            title_style="bold cyan",
            title_justify="left",
            header_style="bold",
            box=None,
            pad_edge=False,
        )
        table.add_column("Key", style="bold")
        table.add_column("Status")
        for entry in keys:
            table.add_row(entry.key, Text(entry.status, style=_status_style(entry.status)))
        console.print(table)
        console.print()
    else:
        print(f"# {display_path}")
        width = max(len(k.key) for k in keys)
        for entry in keys:
            print(f"{entry.key:<{width}}  {entry.status}")
        print()


def render_diff(real: Path, example: Path, *, plain: bool, real_display: str, example_display: str) -> bool:
    """Render a diff between a real env file and its example. Returns True if any differences."""
    real_keys = {k.key for k in parse_env_file(real)}
    example_keys = {k.key for k in parse_env_file(example)}
    missing = sorted(example_keys - real_keys)
    extra = sorted(real_keys - example_keys)
    if not missing and not extra:
        _print(f"{real_display} ≡ {example_display}: same keys.", style="green")
        return False
    header = f"{real_display} vs {example_display}"
    if RICH_AVAILABLE and not plain:
        console.print(Text(header, style="bold cyan"))
    else:
        print(f"# {header}")
    for key in missing:
        _print(f"  - {key}  (in {example.name}, missing from {real.name})", style="red")
    for key in extra:
        _print(f"  + {key}  (in {real.name}, missing from {example.name})", style="yellow")
    _print()
    return True


def render_llm(files: list[tuple[Path, list[EnvKey]]], display: dict[Path, str]) -> None:
    """Dense single-line-per-file output for pasting into a prompt."""
    for path, keys in files:
        if not keys:
            print(f"{display[path]}: (empty)")
            continue
        parts = [f"{k.key}={k.status}" for k in keys]
        print(f"{display[path]}: " + " ".join(parts))


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "List keys from .env-style files without leaking values. Flags placeholders "
            "(<...>, xxx, your-key, changeme, etc.) and diffs against a sibling .env.example."
        ),
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="File or directory to scan (default: current directory)",
    )
    parser.add_argument("-r", "--recursive", action="store_true", help="Recurse into subdirectories")
    parser.add_argument("--plain", action="store_true", help="Plain text output (no rich)")
    parser.add_argument("--llm", action="store_true", help="Compact one-line-per-file format")
    parser.add_argument("--keys-only", action="store_true", help="Print only keys, one per line")
    parser.add_argument("--no-diff", action="store_true", help="Skip the .env vs .env.example diff")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if any key is empty or placeholder (excluding example files)",
    )
    return parser.parse_args()


def main() -> int:
    """CLI entry point."""
    args = parse_args()
    cwd = get_invoking_cwd()

    raw_path = Path(args.path).expanduser()
    target = raw_path if raw_path.is_absolute() else (cwd / raw_path)
    target = target.resolve()

    if not target.exists():
        print(f"error: path not found: {target}", file=sys.stderr)
        return 1

    files = discover_env_files(target, recursive=args.recursive)
    if not files:
        print(f"no .env-style files found in {target}", file=sys.stderr)
        return 1

    # Build display paths relative to cwd when possible
    display: dict[Path, str] = {}
    for path in files:
        try:
            display[path] = str(path.relative_to(cwd))
        except ValueError:
            display[path] = str(path)

    parsed: list[tuple[Path, list[EnvKey]]] = [(path, parse_env_file(path)) for path in files]

    if args.keys_only:
        seen: set[str] = set()
        for _, keys in parsed:
            for entry in keys:
                if entry.key not in seen:
                    print(entry.key)
                    seen.add(entry.key)
        return 0

    if args.llm:
        render_llm(parsed, display)
    else:
        for path, keys in parsed:
            render_file(keys, plain=args.plain, display_path=display[path])

        if not args.no_diff:
            for path, _ in parsed:
                if any(path.name.endswith(suffix) for suffix in EXAMPLE_SUFFIXES):
                    continue
                example = find_example_for(path)
                if example is None:
                    continue
                try:
                    example_display = str(example.relative_to(cwd))
                except ValueError:
                    example_display = str(example)
                render_diff(
                    path,
                    example,
                    plain=args.plain,
                    real_display=display[path],
                    example_display=example_display,
                )

    if args.check:
        bad = 0
        for path, keys in parsed:
            if any(path.name.endswith(suffix) for suffix in EXAMPLE_SUFFIXES):
                continue
            bad += sum(1 for k in keys if k.status != "set")
        if bad:
            print(f"check: {bad} unset or placeholder key(s)", file=sys.stderr)
            return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
