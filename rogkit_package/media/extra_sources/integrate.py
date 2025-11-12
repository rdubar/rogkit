"""Merge external media records into the Plex cache."""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, UTC
from pathlib import Path
from typing import Optional

from rogkit_package.media.media_cache import CACHE_SQLITE_PATH, write_cache_pickle
from .cache import EXTRAS_CACHE_PATH, load_extras_cache

REQUIRED_EXTRA_COLUMNS = {
    "source": "TEXT DEFAULT 'plex'",
    "source_id": "TEXT",
    "extras": "TEXT",
    "created_at": "TEXT",
    "updated_at": "TEXT",
}

LEGACY_SOURCE_LABELS = ("tmdb_csv", "csv")


def _ensure_extra_columns(conn: sqlite3.Connection) -> None:
    """Ensure the cache table has the extra columns needed for external sources."""

    rows = conn.execute("PRAGMA table_info(plex_search_cache)").fetchall()
    existing = {row[1] for row in rows}

    if not existing:
        conn.execute(
            """
            CREATE TABLE plex_search_cache (
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
                source TEXT DEFAULT 'plex',
                source_id TEXT,
                extras TEXT,
                created_at TEXT,
                updated_at TEXT
            )
            """
        )
        return

    for column, ddl in REQUIRED_EXTRA_COLUMNS.items():
        if column not in existing:
            conn.execute(f"ALTER TABLE plex_search_cache ADD COLUMN {column} {ddl}")


def merge_extras_into_cache(
    default_source: Optional[str],
    extras_path: Optional[Path],
    sqlite_path: Optional[Path],
) -> int:
    """Insert extra records into ``plex_search_cache`` with a source label."""

    cache_db = Path(sqlite_path or CACHE_SQLITE_PATH)
    if not cache_db.exists():
        raise RuntimeError(
            f"Cache database {cache_db} not found. Run `pd` at least once to build the cache."
        )

    extras_file = Path(extras_path) if extras_path else EXTRAS_CACHE_PATH
    extras = load_extras_cache(extras_file)
    if not extras:
        print(f"No extras found to merge (looked in {extras_file}).")
        return 0

    print(f"Merging extras from {extras_file} ...")

    conn = sqlite3.connect(str(cache_db))
    try:
        _ensure_extra_columns(conn)

        inserted = 0
        seen: set[tuple[str, str]] = set()
        legacy_labels = {label.lower() for label in LEGACY_SOURCE_LABELS}
        if default_source:
            legacy_labels.add(str(default_source).strip().lower())
        for record in extras:
            title = record.get("title")
            if not title:
                continue

            year = record.get("year")
            runtime_minutes = record.get("runtime_minutes")
            duration_ms = runtime_minutes * 60 * 1000 if isinstance(runtime_minutes, (int, float)) else None
            summary = record.get("summary")
            csv_payload = record.get("csv", {})
            file_path = csv_payload.get("file_path") if isinstance(csv_payload, dict) else None
            disk = csv_payload.get("disk") if isinstance(csv_payload, dict) else None
            source_id = str(record.get("tmdb_id") or record.get("id") or f"{title}_{year}")
            created_at = record.get("created_at") or datetime.now(UTC).isoformat()
            updated_at = record.get("updated_at") or created_at

            provider = record.get("provider")
            if not provider and isinstance(csv_payload, dict):
                provider = (
                    csv_payload.get("platform")
                    or csv_payload.get("source")
                    or csv_payload.get("provider")
                )
            raw_source = provider or default_source or "extras"
            source_label = str(raw_source).strip().lower()

            for legacy in legacy_labels:
                conn.execute(
                    "DELETE FROM plex_search_cache WHERE source = ? AND source_id = ?",
                    (legacy, source_id),
                )
            conn.execute(
                "DELETE FROM plex_search_cache WHERE source = ? AND source_id = ?",
                (source_label, source_id),
            )
            key = (source_label, source_id)
            if key in seen:
                continue
            seen.add(key)

            insert_data = {
                "title": title,
                "title_low": title.lower(),
                "metadata_type": record.get("metadata_type", 1),
                "year": year,
                "parent_title": None,
                "grandparent_title": None,
                "added_at": None,
                "duration_ms": duration_ms,
                "duration_meta": duration_ms,
                "width": None,
                "height": None,
                "size_bytes": None,
                "file_path": file_path,
                "disk": disk,
                "summary": summary,
                "source": source_label,
                "source_id": source_id,
                "extras": json.dumps(record, ensure_ascii=False),
                "created_at": created_at,
                "updated_at": updated_at,
            }
            conn.execute(
                """
                INSERT OR REPLACE INTO plex_search_cache (
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
                    source,
                    source_id,
                    extras,
                    created_at,
                    updated_at
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                tuple(insert_data.values()),
            )
            inserted += 1

        conn.commit()
    finally:
        conn.close()

    write_cache_pickle()
    return inserted


def main():
    parser = argparse.ArgumentParser(description="Merge extras into Plex cache")
    parser.add_argument(
        "--source",
        help="Override provider label applied to imported records (defaults to per-record provider)",
    )
    parser.add_argument("--extras", help="Path to extras JSON cache")
    parser.add_argument("--sqlite", help="Path to plex_search_cache SQLite database")
    args = parser.parse_args()

    inserted = merge_extras_into_cache(args.source, args.extras, args.sqlite)
    label = args.source or "per-record providers"
    print(f"Inserted {inserted} records into plex_search_cache ({label})")


if __name__ == "__main__":
    main()
