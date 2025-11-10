# pyright: reportMissingImports=false
"""
Utility for inspecting the Plex Media Server SQLite database.

Features:
    - Detect whether the local machine has a Plex database in the usual places
      (Pi server install, macOS desktop, or a user-specified override).
    - Run read-only SQL queries against the database without risking corruption.
      By default the tool will attempt to open the live database in immutable
      read-only mode; if that fails (e.g. older SQLite versions) it falls back
      to copying the database (and its WAL/SHM files) to a temporary directory
      before querying.

Example usage:
    pb --query "SELECT title, year FROM metadata_items WHERE title LIKE '%Dylan%'" --limit 10
"""

from __future__ import annotations

import argparse
import contextlib
import os
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path
from typing import Iterable, Iterator, List, Optional

PI_DB = Path(
    "/var/lib/plexmediaserver/Library/Application Support/"
    "Plex Media Server/Plug-in Support/Databases/com.plexapp.plugins.library.db"
)
MAC_DB = Path(
    "~/Library/Application Support/"
    "Plex Media Server/Plug-in Support/Databases/com.plexapp.plugins.library.db"
).expanduser()


def candidate_db_paths() -> List[Path]:
    """Return an ordered list of possible Plex database locations."""
    candidates: List[Path] = []
    env = os.environ.get("PLEX_DB_PATH")
    if env:
        candidates.append(Path(env).expanduser())

    candidates.extend(
        [
            PI_DB,
            MAC_DB,
            Path.home()
            / "Library/Application Support/Plex Media Server/Plug-in Support/Databases/com.plexapp.plugins.library.db",
        ]
    )

    # Ensure uniqueness while preserving order
    seen = set()
    ordered: List[Path] = []
    for path in candidates:
        if path not in seen:
            ordered.append(path)
            seen.add(path)
    return ordered


def detect_db_path() -> Optional[Path]:
    """Return the first Plex database path that exists on disk."""
    for path in candidate_db_paths():
        if path.exists():
            return path
    return None


def human_size(num_bytes: int) -> str:
    """Return a human-friendly representation of a file size."""
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(num_bytes)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{num_bytes}B"


@contextlib.contextmanager
def open_database(path: Path) -> Iterator[sqlite3.Connection]:
    """Yield a read-only sqlite3 connection to the Plex database."""
    uri = f"file:{path}?mode=ro&immutable=1"
    try:
        conn = sqlite3.connect(uri, uri=True)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
        return
    except sqlite3.OperationalError:
        # Fall back to copying the DB (and its write-ahead log) into temp storage
        temp_dir = Path(tempfile.mkdtemp(prefix="plex_db_snapshot_"))
        snapshot = temp_dir / path.name
        shutil.copy2(path, snapshot)
        for suffix in ("-wal", "-shm"):
            sidecar = path.parent / f"{path.name}{suffix}"
            if sidecar.exists():
                shutil.copy2(sidecar, temp_dir / f"{path.name}{suffix}")

        conn = sqlite3.connect(snapshot)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
            shutil.rmtree(temp_dir, ignore_errors=True)


def run_query(db_path: Path, sql: str, limit: int) -> None:
    """Execute a SQL query and print results."""
    with open_database(db_path) as conn:
        cursor = conn.execute(sql)
        if limit > 0:
            rows = cursor.fetchmany(limit)
            truncated = bool(cursor.fetchmany(1))
        else:
            rows = cursor.fetchall()
            truncated = False

    if not rows:
        print("No rows returned.")
        return

    headers = rows[0].keys()
    print(" | ".join(str(h) for h in headers))
    print("-" * (len(headers) * 3 + 4))

    for row in rows:
        values = [row[h] for h in headers]
        print(" | ".join("" if v is None else str(v) for v in values))

    if limit > 0 and truncated:
        print(f"... truncated to first {limit} rows.")


def format_candidates() -> str:
    lines = []
    for path in candidate_db_paths():
        exists = "✓" if path.exists() else "✗"
        lines.append(f"  {exists} {path}")
    return "\n".join(lines)


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect the Plex Media Server SQLite database."
    )
    parser.add_argument(
        "-q",
        "--query",
        help="SQL to execute against the Plex database (read-only).",
    )
    parser.add_argument(
        "-l",
        "--limit",
        type=int,
        default=20,
        help="Maximum rows to display when running a query (0 for no limit).",
    )
    parser.add_argument(
        "--list-paths",
        action="store_true",
        help="Print all candidate database paths and whether they exist.",
    )
    parser.add_argument(
        "--show-path",
        action="store_true",
        help="Print the detected Plex database path and exit.",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = parse_args(argv)

    if args.list_paths:
        print("Candidate Plex database paths:")
        print(format_candidates())
        return 0

    db_path = detect_db_path()

    if args.show_path:
        if not db_path:
            print("No Plex database detected on this machine.", file=sys.stderr)
            return 1
        print(db_path)
        return 0

    if not db_path:
        print(
            "No Plex database found. Set PLEX_DB_PATH or run with --list-paths to "
            "see the locations that were checked.",
            file=sys.stderr,
        )
        return 1

    if not args.query:
        size = human_size(db_path.stat().st_size)
        print(f"Plex database detected at: {db_path}")
        print(f"Size: {size}")
        print(
            "Use `plex_db --query \"...\"` (or alias `pb`) to run read-only SQL."
        )
        return 0

    try:
        run_query(db_path, args.query, args.limit)
    except sqlite3.OperationalError as exc:
        print(f"SQLite error: {exc}", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

