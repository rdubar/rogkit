"""Search and formatting helpers for the media CLI."""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, cast

from ..bin.bytes import byte_size
from .helpers import open_database
from .media_cache import load_cached_records

PEOPLE_TAG_TYPES = (4, 5, 6, 7, 10)


def _sort_key_title(record: Dict[str, Any]) -> str:
    return (record.get("title") or "").lower()


def _sort_key_year(record: Dict[str, Any]) -> int:
    value = record.get("year")
    return int(value) if value is not None else 0


def _sort_key_added(record: Dict[str, Any]) -> int:
    value = record.get("added_at")
    return int(value) if value is not None else 0


def _record_matches_deep(record: Dict[str, Any], terms: Sequence[str]) -> bool:
    if not terms:
        return True

    haystacks = [
        (record.get("title_low") or ""),
        (record.get("title") or "").lower(),
        (record.get("parent_title") or "").lower(),
        (record.get("grandparent_title") or "").lower(),
        (record.get("summary") or "").lower(),
        (record.get("file_path") or "").lower(),
    ]

    tags_text = record.get("tags_text")
    if tags_text:
        haystacks.append(tags_text.lower())

    for term in terms:
        if not any(term in hay for hay in haystacks):
            return False
    return True


def _truncate_summary(summary: Optional[str], max_length: int = 140) -> str:
    if not summary:
        return ""
    squashed = " ".join(summary.split())
    if len(squashed) <= max_length:
        return squashed
    return f"{squashed[: max_length - 1]}…"


def _format_duration(duration_ms: Optional[int]) -> str:
    if not duration_ms:
        return ""
    seconds = duration_ms // 1000
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    return f"{hours:02}:{minutes:02}"


def _row_value(row: Any, key: str, default: Any = None) -> Any:
    if isinstance(row, dict):
        return row.get(key, default)
    try:
        keys = row.keys()  # type: ignore[attr-defined]
    except AttributeError:
        return default
    if key in keys:
        return row[key]
    return default


def _infer_resolution(width: Optional[int], height: Optional[int]) -> str:
    if width is None:
        return ""

    if width >= 3800 or (height is not None and height >= 2000):
        return "4k"
    if width >= 2500 or (height is not None and height >= 1400):
        return "1440"
    if width >= 1900 or (height is not None and height >= 1000):
        return "1080"
    if width >= 1200 or (height is not None and height >= 700):
        return "720"
    if width >= 1000 or (height is not None and height >= 600):
        return "576"
    if width >= 600 or (height is not None and height >= 400):
        return "480"
    return "sd"


def _format_disk(path: Optional[str]) -> str:
    if not path or len(path) <= 10:
        return ""
    return f"[{path[10]}]"


def _compose_title(row: sqlite3.Row) -> str:
    title = row["title"] or "<untitled>"
    if row["metadata_type"] == 4:  # episode
        show = row["grandparent_title"]
        season = row["parent_title"]
        prefix = " · ".join(p for p in (show, season) if p)
        if prefix:
            title = f"{prefix} – {title}"
    year = row["year"]
    if year:
        title += f" ({year})"
    return title


def format_pretty_row(row: sqlite3.Row, args: argparse.Namespace) -> str:
    """Format a row of media data into a pretty string."""
    title = _compose_title(row)
    if len(title) > args.length:
        title_display = title[: args.length - 1] + "…"
    else:
        title_display = title.ljust(args.length)

    size_bytes = row["size_bytes"]
    size_str = byte_size(size_bytes, unit="GB") if size_bytes is not None else ""
    resolution = _infer_resolution(row["width"], row["height"])
    duration_ms = row["duration_ms"] or row["duration_meta"]
    duration_str = _format_duration(duration_ms)
    path = row["file_path"]
    disk = _format_disk(path)
    source_value = (_row_value(row, "source") or "plex").lower()
    disk_token = (disk or "").strip("[]")
    if disk_token:
        source_label = f"{source_value} {disk_token}"
    else:
        source_label = source_value

    lines = [
        f"{source_label:<7}  {size_str:>9}  {resolution:>5}  {duration_str}  {title_display}"
    ]

    if args.info:
        summary = _truncate_summary(row["summary"])
        if summary:
            lines.append(f"  {summary}")
    if args.path and path:
        lines.append(f"  {path}")

    return "\n".join(lines)


def _format_duration_human(total_seconds: int) -> str:
    if total_seconds <= 0:
        return "0 seconds"

    parts: List[str] = []
    remainder = total_seconds
    days, remainder = divmod(remainder, 86400)
    if days:
        parts.append(f"{days:,} day{'s' if days != 1 else ''}")
    hours, remainder = divmod(remainder, 3600)
    if hours:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    minutes, seconds = divmod(remainder, 60)
    if minutes:
        parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    if seconds or not parts:
        parts.append(f"{seconds} second{'s' if seconds != 1 else ''}")

    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return " and ".join(parts)
    return ", ".join(parts[:-1]) + f" and {parts[-1]}"


def format_stats(rows: Sequence[Any]) -> str:
    """Format aggregate stats (count, total runtime, total size) for the displayed items."""
    count = len(rows)

    total_duration_ms = 0
    total_size_bytes = 0
    for row in rows:
        duration_ms = _row_value(row, "duration_ms")
        if duration_ms is None:
            duration_ms = _row_value(row, "duration_meta")
        if duration_ms:
            try:
                total_duration_ms += int(duration_ms)
            except (TypeError, ValueError):
                pass

        size_bytes = _row_value(row, "size_bytes")
        if size_bytes:
            try:
                total_size_bytes += int(size_bytes)
            except (TypeError, ValueError):
                pass

    total_seconds = total_duration_ms // 1000 if total_duration_ms else 0
    duration_str = _format_duration_human(total_seconds)
    size_str = byte_size(total_size_bytes) if total_size_bytes else "0 bytes"
    label = "item" if count == 1 else "items"
    return f"{count:,} {label}: {duration_str} ({size_str})"


def run_people_search(
    db_path: Path,
    terms: List[str],
    *,
    limit: Optional[int],
    sort: str,
    reverse: bool,
) -> Tuple[List[Any], Optional[int]]:
    """Run a people search (actor/director lookup) against the Plex database."""
    if not terms:
        return [], 0

    where_fragments: List[str] = []
    params: List[str] = []
    for term in terms:
        pattern = f"%{term}%"
        where_fragments.append("LOWER(tag.tag) LIKE ?")
        params.append(pattern)

    where_clause = " AND ".join(where_fragments)
    sort_alias_mapping = {"added": "mi.added_at", "title": "mi.title", "year": "mi.year"}
    order_column = sort_alias_mapping.get(sort, "mi.added_at")
    direction = "ASC" if sort == "title" else "DESC"
    if reverse:
        direction = "DESC" if direction == "ASC" else "ASC"

    tag_type_sql = ", ".join(str(t) for t in PEOPLE_TAG_TYPES)
    data_sql = f"""
        SELECT
            mi.id,
            mi.title,
            mi.year,
            mi.metadata_type,
            MAX(parent.title) AS parent_title,
            MAX(grandparent.title) AS grandparent_title,
            MAX(m.duration) AS duration_ms,
            MAX(mi.duration) AS duration_meta,
            MAX(m.width) AS width,
            MAX(m.height) AS height,
            MAX(mp.size) AS size_bytes,
            MIN(mp.file) AS file_path,
            MAX(mi.summary) AS summary,
            MAX(mi.added_at) AS added_at,
            CASE
                WHEN MIN(mp.file) LIKE '/mnt/media1/%' THEN '[1]'
                WHEN MIN(mp.file) LIKE '/mnt/media2/%' THEN '[2]'
                WHEN MIN(mp.file) LIKE '/mnt/media3/%' THEN '[3]'
                ELSE ''
            END AS disk
        FROM metadata_items mi
        LEFT JOIN metadata_items parent ON parent.id = mi.parent_id
        LEFT JOIN metadata_items grandparent ON grandparent.id = parent.parent_id
        LEFT JOIN media_items m ON m.metadata_item_id = mi.id
        LEFT JOIN media_parts mp ON mp.media_item_id = m.id
        LEFT JOIN taggings tg ON tg.metadata_item_id = mi.id
        LEFT JOIN tags tag ON tag.id = tg.tag_id
        WHERE mi.metadata_type IN (1, 2, 4)
          AND mp.file IS NOT NULL
          AND tag.tag_type IN ({tag_type_sql})
          AND {where_clause}
        GROUP BY mi.id
        ORDER BY {order_column} {direction}
    """

    data_params = cast(List[Any], list(params))
    if limit and limit > 0:
        data_sql += " LIMIT ?"
        data_params.append(limit)

    total_sql = f"""
        SELECT COUNT(DISTINCT mi.id)
        FROM metadata_items mi
        LEFT JOIN media_items m ON m.metadata_item_id = mi.id
        LEFT JOIN media_parts mp ON mp.media_item_id = m.id
        LEFT JOIN taggings tg ON tg.metadata_item_id = mi.id
        LEFT JOIN tags tag ON tag.id = tg.tag_id
        WHERE mi.metadata_type IN (1, 2, 4)
          AND mp.file IS NOT NULL
          AND tag.tag_type IN ({tag_type_sql})
          AND {where_clause}
    """

    with open_database(db_path) as conn:
        total_row = conn.execute(total_sql, params).fetchone()
        total_matches = int(total_row[0]) if total_row else None
        rows = conn.execute(data_sql, data_params).fetchall()

    return rows, total_matches


def run_pretty_search(
    db_path: Path,
    terms: List[str],
    *,
    limit: Optional[int],
    sort: str,
    reverse: bool,
    deep: bool,
) -> Tuple[List[Any], Optional[int]]:
    """Run a pretty search (title, parent, grandparent) against the Plex database."""
    records = load_cached_records(db_path)

    def _apply_sort(items: List[Dict[str, Any]]) -> None:
        if sort == "title":
            items.sort(key=_sort_key_title, reverse=reverse)
        elif sort == "year":
            items.sort(key=_sort_key_year, reverse=not reverse)
        else:
            items.sort(key=_sort_key_added, reverse=not reverse)

    if not deep:
        if terms:
            term_list = [term.lower() for term in terms]
            filtered_full: List[Dict[str, Any]] = []
            for record in records:
                title_low = record.get("title_low", "")
                summary = (record.get("summary") or "").lower()
                disk = (record.get("disk") or "").lower()
                year = str(record.get("year") or "").lower()
                source = (record.get("source") or "").lower()
                tags = (record.get("tags_text") or "").lower()
                combined = " ".join(
                    [
                        title_low,
                        summary,
                        disk,
                        year,
                        source,
                        tags,
                    ]
                )
                if all(term in combined for term in term_list):
                    filtered_full.append(record)
        else:
            filtered_full = list(records)

        _apply_sort(filtered_full)
        total_matches = len(filtered_full)
        if limit and limit > 0:
            filtered_full = filtered_full[:limit]

        return filtered_full, total_matches

    term_list = [term.lower() for term in terms]
    filtered_full = [record for record in records if _record_matches_deep(record, term_list)]

    _apply_sort(filtered_full)
    total_matches = len(filtered_full)
    if limit and limit > 0:
        filtered_full = filtered_full[:limit]

    return filtered_full, total_matches
