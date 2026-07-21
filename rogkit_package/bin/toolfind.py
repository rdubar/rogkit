#!/usr/bin/env python3
"""The toolkit's own searchable index — 85+ tools makes "what was that thing
that does X" a real problem, and grepping README.md is the only fallback.

`toolfind` builds its index from source on every run (alias names parsed
from `aliases`, descriptions from each Python module's docstring or each Go
tool's header comment), so it can never drift from what's actually installed.

Usage:
    toolfind                 # list every tool, grouped by category
    toolfind "empty folders"  # fuzzy search by name or description
    toolfind --json           # structured output
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

from ..settings import root_dir

try:
    from thefuzz import fuzz

    THEFUZZ_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover
    THEFUZZ_AVAILABLE = False

try:
    from rich.console import Console
    from rich.text import Text

    console = Console()
    RICH_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover
    console = None
    RICH_AVAILABLE = False

ALIAS_RE = re.compile(r"^alias\s+([\w-]+)='([^']*)'")
HEADER_RULE_RE = re.compile(r"^# -{5,}\s*$")
GO_COMMAND_RE = re.compile(r"^//\s*Command\s+\S+\s+(?:is\s+)?(.*)$")


@dataclass(frozen=True)
class ToolEntry:
    alias: str
    target: str  # "py:rogkit_package.bin.note" or "go:sysreboot"
    description: str
    category: str
    aliases: tuple[str, ...] = ()


def _print(message: str, *, style: str | None = None) -> None:
    if RICH_AVAILABLE:
        console.print(Text(message, style=style) if style else message)
    else:
        print(message)


def _aliases_path() -> Path:
    return Path(root_dir) / "aliases"


def _parse_aliases(text: str) -> list[tuple[str, str, str]]:
    """Return (alias, command, category) triples in file order."""
    entries: list[tuple[str, str, str]] = []
    lines = text.splitlines()
    category = "Uncategorized"
    for i, line in enumerate(lines):
        if HEADER_RULE_RE.match(line) and i + 1 < len(lines):
            title = lines[i + 1].strip()
            if title.startswith("#") and not HEADER_RULE_RE.match(title):
                category = title.lstrip("#").strip()
            continue
        m = ALIAS_RE.match(line)
        if m:
            entries.append((m.group(1), m.group(2), category))
    return entries


def _python_docstring(module: str) -> str:
    """First line of a Python tool module's docstring, via ast (no import —
    fast, and side-effect free across 85+ modules)."""
    path = Path(root_dir) / (module.replace(".", "/") + ".py")
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return ""
    doc = ast.get_docstring(tree) or ""
    return doc.strip().splitlines()[0].strip() if doc.strip() else ""


def _go_description(binary: str) -> str:
    """First sentence of a Go tool's `// Command X ...` header comment."""
    path = Path(root_dir) / "go" / "cmd" / binary / "main.go"
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return ""
    parts: list[str] = []
    for line in lines:
        m = GO_COMMAND_RE.match(line)
        if m:
            parts.append(m.group(1))
            continue
        if parts and line.startswith("//"):
            parts.append(line.lstrip("/").strip())
            continue
        if parts:
            break
    return " ".join(parts).rstrip(".")


def _shell_description(path_text: str) -> str:
    """First non-shebang comment from a shell script alias target."""
    path = Path(root_dir) / path_text.replace("$ROGKIT_PACKAGE/", "rogkit_package/")
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return ""
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#!"):
            continue
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip().rstrip(".")
        break
    return ""


def _rust_description(binary: str) -> str:
    """Read a Rust binary description from its nearest Cargo manifest."""
    path = Path(root_dir) / "rust" / binary / "Cargo.toml"
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return ""
    description = data.get("package", {}).get("description", "")
    return str(description).strip().rstrip(".")


def _target_for_command(command: str) -> tuple[str, str] | None:
    """Resolve an alias's shell command to (kind, name) for description
    lookup, or None for commands toolfind doesn't know how to describe
    (raw paths, non-rogkit binaries)."""
    py_match = re.match(r"rogkit_py\s+-m\s+([\w.]+)", command)
    if py_match:
        return "py", py_match.group(1)
    go_match = re.match(r"\$ROGKIT_GO_BIN/([\w-]+)", command)
    if go_match:
        return "go", go_match.group(1)
    shell_match = re.match(r"\$ROGKIT_PACKAGE/bin/([\w.-]+)", command)
    if shell_match:
        return "sh", command
    rust_match = re.match(r"\$ROGKIT/rust/target/release/([\w-]+)", command)
    if rust_match:
        return "rust", rust_match.group(1)
    streamlit_match = re.match(r"\(cd\s+\"\$ROGKIT\"\s+&&\s+uv\s+run\s+streamlit\s+run\s+([\w./-]+)", command)
    if streamlit_match:
        return "pyfile", streamlit_match.group(1)
    return None


def _description_for_target(kind: str, name: str) -> str:
    if kind == "py":
        return _python_docstring(name)
    if kind == "pyfile":
        path = Path(name)
        module = ".".join(path.with_suffix("").parts)
        return _python_docstring(module)
    if kind == "go":
        return _go_description(name)
    if kind == "sh":
        return _shell_description(name)
    if kind == "rust":
        return _rust_description(name)
    return ""


def build_index() -> list[ToolEntry]:
    path = _aliases_path()
    if not path.exists():
        return []
    entries = []
    for alias, command, category in _parse_aliases(path.read_text(encoding="utf-8")):
        target = _target_for_command(command)
        if target is None:
            entries.append(ToolEntry(alias, command, "", category))
            continue
        kind, name = target
        description = _description_for_target(kind, name)
        entries.append(ToolEntry(alias, f"{kind}:{name}", description, category))

    aliases_by_target: dict[str, tuple[str, ...]] = {}
    for entry in entries:
        aliases_by_target.setdefault(entry.target, tuple())
        aliases_by_target[entry.target] = aliases_by_target[entry.target] + (entry.alias,)
    return [
        ToolEntry(entry.alias, entry.target, entry.description, entry.category, aliases_by_target[entry.target])
        for entry in entries
    ]


def search(index: list[ToolEntry], query: str, limit: int = 8) -> list[tuple[ToolEntry, int]]:
    if not THEFUZZ_AVAILABLE:
        needle = query.lower()
        matches = [e for e in index if needle in e.alias.lower() or needle in e.description.lower()]
        return [(e, 100) for e in matches[:limit]]

    query_lower = query.lower().strip()
    query_tokens = set(re.findall(r"[a-z0-9]+", query_lower))
    scored = []
    for entry in index:
        alias_lower = entry.alias.lower()
        related_aliases_lower = [alias.lower() for alias in entry.aliases if alias != entry.alias]
        aliases_lower = " ".join(related_aliases_lower)
        description_lower = entry.description.lower()
        corpus = f"{alias_lower} {aliases_lower} {description_lower}"
        related_alias_score = max(
            (
                fuzz.WRatio(query_lower, related_alias)
                for related_alias in related_aliases_lower
                if len(related_alias) > 1 or query_lower == related_alias
            ),
            default=0,
        )
        alias_score = 100 if query_lower == alias_lower else 0
        if len(alias_lower) > 1:
            alias_score = fuzz.WRatio(query_lower, alias_lower)
        # WRatio against a long description can bury an exact tool-name
        # match. Combine it with token overlap and make direct name matches
        # win, which is what an agent expects from `toolfind "disk space"`.
        score = max(
            alias_score,
            related_alias_score,
            fuzz.token_set_ratio(query_lower, description_lower),
            fuzz.token_set_ratio(query_lower, corpus),
        )
        if query_lower == alias_lower:
            score = 100
        elif query_lower in entry.aliases:
            score = max(score, 98)
        elif alias_lower in query_tokens or alias_lower in query_lower.split():
            score = max(score, 95)
        elif query_tokens and query_tokens.issubset(set(re.findall(r"[a-z0-9]+", corpus))):
            score = max(score, 90)
        scored.append((entry, score))
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored[:limit]


def render_list(index: list[ToolEntry]) -> None:
    by_category: dict[str, list[ToolEntry]] = {}
    for entry in index:
        by_category.setdefault(entry.category, []).append(entry)
    for category, entries in by_category.items():
        _print(f"\n{category}", style="bold cyan")
        for entry in entries:
            desc = entry.description or "(no description available)"
            _print(f"  {entry.alias:<16} {desc}")


def render_search(results: list[tuple[ToolEntry, int]]) -> None:
    if not results:
        _print("No matching tools.", style="yellow")
        return
    for entry, score in results:
        desc = entry.description or "(no description available)"
        _print(f"  {entry.alias:<16} {desc}", style="bold" if score >= 80 else None)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Search rogkit's own tool catalogue.")
    parser.add_argument("query", nargs="?", help="Fuzzy search text; omit to list everything")
    parser.add_argument("--json", action="store_true", help="Structured JSON output")
    parser.add_argument("-n", "--limit", type=int, default=8, help="Max search results (default 8)")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    index = build_index()

    if args.query:
        results = search(index, args.query, limit=args.limit)
        if args.json:
            print(json.dumps([{"alias": e.alias, "description": e.description, "score": s} for e, s in results], indent=2))
        else:
            render_search(results)
        return 0

    if args.json:
        print(json.dumps([{"alias": e.alias, "description": e.description, "category": e.category} for e in index], indent=2))
    else:
        render_list(index)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
