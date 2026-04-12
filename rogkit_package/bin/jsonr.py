"""
JSON pretty-printer and lightweight query tool.

Reads JSON from a file or stdin, pretty-prints with syntax highlighting,
and supports simple path queries without requiring jq.

Usage:
    json file.json                  # pretty-print
    echo '{"a":1}' | json           # from stdin
    json file.json -q .name         # extract a field
    json file.json -q .users[0]     # array element
    json file.json -q .meta.tags[]  # iterate an array
    json file.json --keys           # list top-level keys
    json file.json -c               # compact (no indentation)
    json file.json --plain          # no colour
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Any, Optional

try:
    from rich.console import Console
    from rich.syntax import Syntax

    console = Console()
    RICH_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover
    console = None  # type: ignore[assignment]
    RICH_AVAILABLE = False


def _print_json(data: Any, *, compact: bool = False, plain: bool = False) -> None:
    indent = None if compact else 2
    text = json.dumps(data, indent=indent, ensure_ascii=False)
    if RICH_AVAILABLE and not plain:
        console.print(Syntax(text, "json", theme="monokai", word_wrap=True))
    else:
        print(text)


def _tokenise_path(path: str) -> list[str | int]:
    """
    Convert a dot/bracket path string into a list of keys/indices.

    ".users[0].name"  →  ["users", 0, "name"]
    ".[1]"            →  [1]
    "."               →  []
    """
    path = path.lstrip(".")
    if not path:
        return []
    tokens: list[str | int] = []
    for part in re.split(r"\.", path):
        # each part may be "key", "key[0]", "[0]", "key[]"
        segments = re.split(r"\[(\d*)\]", part)
        for i, seg in enumerate(segments):
            if i % 2 == 0:
                if seg:
                    tokens.append(seg)
            else:
                if seg == "":
                    tokens.append(None)  # type: ignore[arg-type]  # sentinel: iterate
                else:
                    tokens.append(int(seg))
    return tokens


def apply_path(data: Any, path: str) -> Any:
    """
    Walk *data* using a simple dot/bracket path expression.

    Supports:
      .key          dict key
      .key.sub      nested keys
      .[N] / .k[N]  array index
      .key[]        iterate (returns list of values at that key across items)
    """
    tokens = _tokenise_path(path)
    current = data
    for token in tokens:
        if token is None:
            # iterate: collect the next level across a list
            if isinstance(current, list):
                return current
            raise ValueError(f"Cannot iterate non-list value: {type(current).__name__}")
        if isinstance(current, dict):
            if token not in current:
                raise KeyError(f"Key not found: {token!r}")
            current = current[token]
        elif isinstance(current, list):
            if not isinstance(token, int):
                raise TypeError(f"Expected integer index for list, got {token!r}")
            current = current[token]
        else:
            raise TypeError(
                f"Cannot index into {type(current).__name__} with {token!r}"
            )
    return current


def load_json(source: Optional[str]) -> Any:
    """Load JSON from a file path or stdin."""
    if source:
        with open(source, encoding="utf-8") as fh:
            return json.load(fh)
    return json.load(sys.stdin)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Pretty-print JSON and run lightweight path queries."
    )
    parser.add_argument("file", nargs="?", help="JSON file (omit to read from stdin)")
    parser.add_argument(
        "-q", "--query",
        metavar="PATH",
        help="Path expression, e.g. .name or .users[0].email",
    )
    parser.add_argument(
        "--keys",
        action="store_true",
        help="List top-level keys (objects) or length (arrays)",
    )
    parser.add_argument(
        "-c", "--compact",
        action="store_true",
        help="Compact output — no indentation",
    )
    parser.add_argument(
        "--plain",
        action="store_true",
        help="Plain text output — no syntax highlighting",
    )
    args = parser.parse_args()

    if not args.file and sys.stdin.isatty():
        parser.print_help()
        return 0

    try:
        data = load_json(args.file)
    except FileNotFoundError:
        print(f"error: file not found: {args.file}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as exc:
        print(f"error: invalid JSON: {exc}", file=sys.stderr)
        return 1

    if args.keys:
        if isinstance(data, dict):
            for key in data.keys():
                print(key)
        elif isinstance(data, list):
            print(f"array of {len(data)} items")
        else:
            print(type(data).__name__)
        return 0

    if args.query:
        try:
            result = apply_path(data, args.query)
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        _print_json(result, compact=args.compact, plain=args.plain)
        return 0

    _print_json(data, compact=args.compact, plain=args.plain)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
