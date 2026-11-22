#!/usr/bin/env python3
"""Find a file by name for any rogkit tool, using opener's `o` command.

A tool that takes a file calls `find_file(arg)`. If `arg` is a real path it comes
straight back. Otherwise the words are handed to `o -p` (https://github.com/rdubar/opener),
which searches your folders by file name: one match is used, several give a numbered list.

    from .findfile import find_file
    path = find_file("bug-hunter", suffixes=(".md",))

Run on its own it prints the path it would pick:  findfile bug hunter
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from ..settings import get_invoking_cwd

INSTALL_HINT = (
    "Install opener's `o` to find files by name: "
    "https://github.com/rdubar/opener (one shell script)."
)


def find_o() -> str | None:
    """Locate the `o` command: $ROGKIT_O, ~/bin/o (Roger's wrapper), PATH, then the usual spots."""
    home = Path.home()
    candidates = [os.environ.get("ROGKIT_O", ""), str(home / "bin/o"), shutil.which("o") or "",
                  str(home / ".local/bin/o"), str(home / "dev/opener/o")]
    for c in candidates:
        if c and Path(c).is_file() and os.access(c, os.X_OK):
            return c
    return None


def search(words: list[str], *, o_cmd: str | None = None) -> list[Path]:
    """Return the paths `o -p` finds for these words (newest first), or [] if none."""
    o_cmd = o_cmd or find_o()
    if not o_cmd:
        raise FileNotFoundError(INSTALL_HINT)
    run = subprocess.run([o_cmd, "-p", *words], capture_output=True, text=True)
    return [Path(line) for line in run.stdout.splitlines() if line.strip()]


def choose(matches: list[Path], *, interactive: bool | None = None) -> Path | None:
    """Pick one path: the only match, or ask by number when there are several."""
    if len(matches) == 1:
        return matches[0]
    if not matches:
        return None
    if interactive is None:
        interactive = sys.stdin.isatty()
    home = str(Path.home())
    for i, m in enumerate(matches, 1):
        print(f"{i:>3}  {str(m).replace(home, '~', 1)}", file=sys.stderr)
    if not interactive:
        print("Several files match; add a word to narrow it down.", file=sys.stderr)
        return None
    try:
        answer = input("Which one? (number, Enter to cancel) ").strip()
    except EOFError:
        return None
    if answer.isdigit() and 1 <= int(answer) <= len(matches):
        return matches[int(answer) - 1]
    return None


def find_file(arg: str | list[str], *, suffixes: tuple[str, ...] = (), cwd: str | Path | None = None,
              interactive: bool | None = None) -> Path | None:
    """Turn what the user typed into one existing file, or None.

    A real path (relative to the invoking folder, or absolute, or ~) wins. Otherwise
    search by name; if `suffixes` is given and some matches have them, keep only those.
    """
    words = arg.split() if isinstance(arg, str) else list(arg)
    joined = " ".join(words)
    base = Path(cwd or get_invoking_cwd())
    p = Path(joined).expanduser()
    p = p if p.is_absolute() else base / p
    if p.is_file():
        return p
    for suf in suffixes:  # "bug-hunter" -> bug-hunter.md in this folder
        if (q := p.with_name(p.name + suf)).is_file():
            return q
    matches = search(words)
    if suffixes:
        typed = [m for m in matches if m.suffix.lower() in suffixes]
        matches = typed or matches
    return choose(matches, interactive=interactive)


def main() -> int:
    """CLI entry point: print the file that would be picked."""
    parser = argparse.ArgumentParser(description="Find a file by name (via opener's o) and print its path.")
    parser.add_argument("words", nargs="+", help="a path, or words in the file name")
    parser.add_argument("-s", "--suffix", action="append", default=[], help="prefer this extension, e.g. .md")
    args = parser.parse_args()
    try:
        path = find_file(args.words, suffixes=tuple(s if s.startswith(".") else f".{s}" for s in args.suffix))
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        return 1
    if not path:
        return 1
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
