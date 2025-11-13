# pyright: reportMissingImports=false
"""Helpers for building and loading the local Plex search cache.

This module encapsulates the logic for copying metadata from the Plex
SQLite database into a lightweight cache that powers the fast search mode.
"""

from __future__ import annotations

import pickle
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

CACHE_DIR = Path.home() / ".cache" / "rogkit" / "plex_db"
CACHE_PICKLE_PATH = CACHE_DIR / "plex_search_cache.pkl"
CACHE_SQLITE_PATH = CACHE_DIR / "plex_search_cache.sqlite3"
REQUIRED_CACHE_COLUMNS = {
    "id",
    "title",
    "title_low",
    "metadata_type",
    "year",
    "parent_title",
    "grandparent_title",
    "added_at",
    "duration_ms",
    "duration_meta",
    "width",
    "height",
    "size_bytes",
    "file_path",
    "disk",
    "summary",
    "tags_text",
    "source",
    "source_id",
    "extras",
    "created_at",
    "updated_at",
}

CACHE_STATE: Dict[str, Optional[List[Dict[str, Any]]]] = {"records": None}


def _initialize_cache_schema(conn: sqlite3.Connection) -> None:
    """Create the cache table inside the local SQLite database."""

    conn.execute("DROP TABLE IF EXISTS plex_search_cache")
    conn.execute(
        """CREATE TABLE plex_search_cache (
            id INTEGER PRIMARY KEY,
            title TEXT,
            title_low TEXT,
            metadata_type INTEGER,
            year INTEGER,
            parent_title TEXT,
            grandparent_title TEXT,
            added_at INTEGER,
            duration_ms INTEGER,
            duration_meta INTEGER,
            width INTEGER,
            height INTEGER,
            size_bytes INTEGER,
            file_path TEXT,
            disk TEXT,
            summary TEXT,
            tags_text TEXT,
            source TEXT DEFAULT 'plex',
            source_id TEXT,
            extras TEXT,
            created_at TEXT,
            updated_at TEXT
        )"""
    )


def _write_cache_pickle_from_conn(conn: sqlite3.Connection) -> None:
    """Serialise the cache table into a pickle for lightning-fast searches."""

    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT
            id,
            title,
            title_low,
            metadata_type,
            year,
            parent_title,
            grandparent_title,
            added_at,
            duration_ms,
            duration_meta,
            width,
            height,
            size_bytes,
            file_path,
            disk,
            summary,
            tags_text,
            source,
            source_id,
            extras,
            created_at,
            updated_at
        FROM plex_search_cache
        ORDER BY added_at DESC
        """
    ).fetchall()
    data = [dict(row) for row in rows]
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with CACHE_PICKLE_PATH.open("wb") as fh:
        pickle.dump(data, fh)
    CACHE_STATE["records"] = data


def build_cache_table(db_path: Path) -> None:
    """Populate the local cache from the source Plex SQLite database."""

    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    source_conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        source_conn.row_factory = sqlite3.Row
        rows = source_conn.execute(
            """
            SELECT
                mi.id,
                mi.title,
                LOWER(mi.title) AS title_low,
                mi.metadata_type,
                mi.year,
                parent.title AS parent_title,
                grandparent.title AS grandparent_title,
                ROUND(mi.added_at) AS added_at,
                MAX(m.duration) AS duration_ms,
                MAX(mi.duration) AS duration_meta,
                MAX(m.width) AS width,
                MAX(m.height) AS height,
                MAX(mp.size) AS size_bytes,
                MIN(mp.file) AS file_path,
                CASE
                    WHEN MIN(mp.file) LIKE '/mnt/media1/%' THEN '[1]'
                    WHEN MIN(mp.file) LIKE '/mnt/media2/%' THEN '[2]'
                    WHEN MIN(mp.file) LIKE '/mnt/media3/%' THEN '[3]'
                    ELSE ''
                END AS disk,
                substr(COALESCE(mi.summary, ''), 1, 280) AS summary,
                '' AS tags_text
            FROM metadata_items mi
            LEFT JOIN metadata_items parent ON parent.id = mi.parent_id
            LEFT JOIN metadata_items grandparent ON grandparent.id = parent.parent_id
            LEFT JOIN media_items m ON m.metadata_item_id = mi.id
            LEFT JOIN media_parts mp ON mp.media_item_id = m.id
            LEFT JOIN taggings tg ON tg.metadata_item_id = mi.id
            LEFT JOIN tags tag ON tag.id = tg.tag_id
            WHERE mi.metadata_type IN (1, 2, 4)
            GROUP BY mi.id
            """
        ).fetchall()
    finally:
        source_conn.close()

    dest_conn = sqlite3.connect(str(CACHE_SQLITE_PATH))
    try:
        _initialize_cache_schema(dest_conn)
        for record in rows:
            record_keys = record.keys()
            dest_conn.execute(
                "INSERT INTO plex_search_cache (id, title, title_low, metadata_type, year, parent_title, grandparent_title, added_at, duration_ms, duration_meta, width, height, size_bytes, file_path, disk, summary, tags_text, source, source_id, extras, created_at, updated_at) VALUES (?, ?, LOWER(?), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'plex', NULL, NULL, NULL, NULL)",
                (
                    record["id"],
                    record["title"],
                    record["title"],
                    record["metadata_type"],
                    record["year"],
                    record["parent_title"] if "parent_title" in record_keys else None,
                    record["grandparent_title"] if "grandparent_title" in record_keys else None,
                    record["added_at"] if "added_at" in record_keys else None,
                    record["duration_ms"] if "duration_ms" in record_keys else None,
                    record["duration_meta"] if "duration_meta" in record_keys else None,
                    record["width"] if "width" in record_keys else None,
                    record["height"] if "height" in record_keys else None,
                    record["size_bytes"] if "size_bytes" in record_keys else None,
                    record["file_path"] if "file_path" in record_keys else None,
                    record["disk"] if "disk" in record_keys else None,
                    record["summary"] if "summary" in record_keys else None,
                    record["tags_text"] if "tags_text" in record_keys else None,
                ),
            )
        dest_conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_plex_cache_title_low ON plex_search_cache(title_low)"
        )
        dest_conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_plex_cache_added ON plex_search_cache(added_at)"
        )
        dest_conn.commit()
        _write_cache_pickle_from_conn(dest_conn)
    finally:
        dest_conn.close()

    CACHE_STATE["records"] = None


def write_cache_pickle() -> None:
    """Rebuild only the pickle cache from the local SQLite cache database."""

    if not CACHE_SQLITE_PATH.exists():
        return
    conn = sqlite3.connect(str(CACHE_SQLITE_PATH))
    try:
        _write_cache_pickle_from_conn(conn)
    finally:
        conn.close()


def ensure_cache_pickle() -> None:
    """Ensure the pickle cache exists and reset the in-memory cache state."""

    if not CACHE_PICKLE_PATH.exists():
        write_cache_pickle()
    else:
        CACHE_STATE["records"] = None


def ensure_cache_table(db_path: Path) -> None:
    """Verify the cache table exists locally, rebuilding it if necessary."""

    if not CACHE_SQLITE_PATH.exists():
        build_cache_table(db_path)
        return

    rebuild = False
    conn = sqlite3.connect(str(CACHE_SQLITE_PATH))
    try:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='plex_search_cache'"
        ).fetchone()
        if row is None:
            rebuild = True
        else:
            info = conn.execute("PRAGMA table_info(plex_search_cache)").fetchall()
            existing_cols = {col[1] for col in info}
            if not REQUIRED_CACHE_COLUMNS.issubset(existing_cols):
                rebuild = True
    finally:
        conn.close()

    if rebuild:
        build_cache_table(db_path)
    else:
        ensure_cache_pickle()


def load_cached_records(db_path: Path) -> List[Dict[str, Any]]:
    """Load cached records into memory, rebuilding if necessary."""

    records = CACHE_STATE.get("records")
    if records is None:
        if not CACHE_PICKLE_PATH.exists():
            build_cache_table(db_path)
        with CACHE_PICKLE_PATH.open("rb") as fh:
            CACHE_STATE["records"] = pickle.load(fh)
    return CACHE_STATE["records"] or []


def _format_cache_age(seconds: Optional[float]) -> str:
    """Return a human-readable clock string for cache age."""

    if seconds is None:
        return "unknown"
    seconds = max(0, int(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours}:{minutes:02}:{secs:02}"


def describe_cache_state(total_items: int, cache_age_seconds: Optional[float]) -> str:
    """Return the banner text describing the cache state."""

    age_str = _format_cache_age(cache_age_seconds)
    return (
        "Rog's Fast Media Tool\n"
        f"Library of {total_items:,} items last updated {age_str} ago."
    )


def get_cache_metadata(db_path: Path) -> tuple[int, Optional[float]]:
    """Return total cached items and cache age in seconds."""

    records = load_cached_records(db_path)
    total_items = len(records)
    if CACHE_PICKLE_PATH.exists():
        age_seconds = time.time() - CACHE_PICKLE_PATH.stat().st_mtime
    else:
        age_seconds = None
    return total_items, age_seconds
