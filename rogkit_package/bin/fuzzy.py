"""
Reusable fuzzy search helper with CLI interface.

Provides flexible file and directory discovery using substring or
RapidFuzz-based scoring. Designed for both direct import and CLI use.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Sequence

try:
    from rapidfuzz import fuzz  # type: ignore
except ImportError:  # pragma: no cover - rapidfuzz is optional
    fuzz = None


@dataclass(frozen=True)
class MatchResult:
    """Represents a fuzzy match result."""

    path: Path
    score: float = 1.0

    def __str__(self) -> str:
        if self.score is None:
            return str(self.path)
        return f"{self.score:6.1f}  {self.path}"


def find_candidates(
    search_roots: Iterable[Path],
    needle: str,
    *,
    strategy: str = "substring",
    threshold: float = 70.0,
) -> Sequence[MatchResult]:
    """
    Return candidate paths whose names match ``needle``.

    Parameters
    ----------
    search_roots:
        Directories to scan recursively.
    needle:
        Text to match against directory names.
    strategy:
        Matching strategy: ``"substring"`` (default) or ``"fuzz"`` (requires rapidfuzz).
    threshold:
        Minimum RapidFuzz ratio (0–100) when using ``strategy="fuzz"``.
    """

    needle_lower = needle.lower()
    roots = [root.expanduser().resolve() for root in search_roots if root.exists()]

    if strategy == "substring":
        return list(_substring_matches(roots, needle_lower))

    if strategy == "fuzz":
        if fuzz is None:
            raise RuntimeError(
                "RapidFuzz is not installed; add it to the rogkit environment with `uv add rapidfuzz` "
                "or install it in the active uv-managed environment."
            )
        return list(_fuzzy_matches(roots, needle, threshold))

    raise ValueError(f"Unknown strategy '{strategy}'. Try 'substring' or 'fuzz'.")


def _substring_matches(roots: Sequence[Path], needle_lower: str) -> Iterator[MatchResult]:
    """Yield matches where the directory name contains ``needle`` (case-insensitive)."""

    for base in roots:
        for entry in base.rglob("*"):
            if entry.is_dir() and needle_lower in entry.name.lower():
                yield MatchResult(entry)


def _fuzzy_matches(roots: Sequence[Path], needle: str, threshold: float) -> Iterator[MatchResult]:
    """Yield RapidFuzz matches meeting the threshold."""

    for base in roots:
        for entry in base.rglob("*"):
            if not entry.is_dir():
                continue
            score = fuzz.ratio(needle, entry.name, score_cutoff=threshold)
            if score:
                yield MatchResult(entry, score)


def main(argv: Sequence[str] | None = None) -> None:
    """CLI entry point for fuzzy directory matching."""

    parser = argparse.ArgumentParser(description="Search for directories using fuzzy matching.")
    parser.add_argument("needle", help="Text to search for (case-insensitive substring by default).")
    parser.add_argument(
        "search_roots",
        nargs="+",
        type=Path,
        help="One or more directories to search within.",
    )
    parser.add_argument(
        "--strategy",
        choices=("substring", "fuzz"),
        default="substring",
        help="Match strategy to use (default: substring).",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=70.0,
        help="Minimum score when using --strategy fuzz (0-100).",
    )
    parser.add_argument(
        "--first",
        action="store_true",
        help="Return only the first match (exits with 1 if none).",
    )
    parser.add_argument(
        "--relative",
        action="store_true",
        help="Print paths relative to their search root when possible.",
    )
    args = parser.parse_args(argv)

    matches = find_candidates(
        args.search_roots,
        args.needle,
        strategy=args.strategy,
        threshold=args.threshold,
    )

    if not matches:
        parser.exit(1, "No matches found.\n")

    results = matches[:1] if args.first else matches

    for result in results:
        path = result.path
        if args.relative:
            path = _relative_to_any(path, args.search_roots) or path
        print(result if args.strategy == "fuzz" else path)


def _relative_to_any(path: Path, roots: Iterable[Path]) -> Path | None:
    """Return ``path`` relative to the first root it sits under, if any."""

    for root in roots:
        try:
            return path.relative_to(root)
        except ValueError:
            continue
    return None


if __name__ == "__main__":  # pragma: no cover
    main()
