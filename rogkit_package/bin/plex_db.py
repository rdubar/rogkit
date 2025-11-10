# pyright: reportMissingImports=false
"""
Utility for inspecting the Plex Media Server SQLite database.

Features:
    - Detect whether the local machine has a Plex database in the usual places
      (Pi server install, macOS desktop, cached snapshot, or a user-specified override).
    - Seamlessly refresh a cached copy of the database from a remote Plex server
      over SSH/SFTP with `--update`.
    - Run read-only SQL queries without risking corruption. The tool first tries
      immutable read-only access; if that fails it creates a temporary snapshot
      (including WAL/SHM) and queries the snapshot instead.

Examples:
    pd --show-path
    pd --update
    pd --query "SELECT title, year FROM metadata_items WHERE title LIKE '%Dylan%'" --limit 10
"""

from __future__ import annotations

import argparse
import contextlib
import dataclasses
import os
import pickle
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path
from time import perf_counter
from typing import Any, Dict, Iterable, Iterator, List, Optional

from ..bin.bytes import byte_size
from ..bin.tomlr import load_rogkit_toml

PI_DB = Path(
    "/var/lib/plexmediaserver/Library/Application Support/"
    "Plex Media Server/Plug-in Support/Databases/com.plexapp.plugins.library.db"
)
MAC_DB = Path(
    "~/Library/Application Support/"
    "Plex Media Server/Plug-in Support/Databases/com.plexapp.plugins.library.db"
).expanduser()

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
}

CACHE_STATE: Dict[str, Optional[List[Dict[str, Any]]]] = {"records": None}


@dataclasses.dataclass(frozen=True)
class RemoteConfig:
    host: str
    username: str
    password: Optional[str]
    port: int
    db_path: Path

    @property
    def cache_path(self) -> Path:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        return CACHE_DIR / self.db_path.name


def load_remote_config() -> Optional[RemoteConfig]:
    config = load_rogkit_toml()
    plex_section = config.get("plex", {})
    remote_section = config.get("plex_remote", {})
    media_files = config.get("media_files", {})

    host = (
        remote_section.get("host")
        or plex_section.get("remote_host")
        or media_files.get("server")
        or "192.168.0.50"
    )
    username = (
        remote_section.get("user")
        or plex_section.get("remote_user")
        or media_files.get("user")
        or "rog"
    )
    password = (
        remote_section.get("password")
        or plex_section.get("remote_password")
        or media_files.get("password")
    )
    port = int(remote_section.get("port", 22))
    db_path = Path(
        remote_section.get("path")
        or plex_section.get("remote_db_path")
        or PI_DB
    )

    if not host:
        return None

    return RemoteConfig(
        host=str(host),
        username=str(username),
        password=str(password) if password else None,
        port=port,
        db_path=db_path,
    )


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
        ]
    )

    remote = load_remote_config()
    if remote:
        candidates.append(remote.cache_path)

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
    paths = candidate_db_paths()
    for path in paths:
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
    temp_dir: Optional[Path] = None
    try:
        conn = sqlite3.connect(uri, uri=True)
    except sqlite3.OperationalError:
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
        if temp_dir:
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
    seen = set()
    for path in candidate_db_paths():
        if path in seen:
            continue
        seen.add(path)
        exists = "✓" if path.exists() else "✗"
        label = "local"
        if path == PI_DB:
            label = "linux-default"
        elif path == MAC_DB:
            label = "macos-default"
        elif CACHE_DIR in path.parents:
            label = "cache"
        lines.append(f"  {exists} [{label}] {path}")

    remote = load_remote_config()
    if remote:
        lines.append(f"  ⚙︎ [remote] {remote.username}@{remote.host}:{remote.db_path}")

    return "\n".join(lines)


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect the Plex Media Server SQLite database."
    )
    parser.add_argument(
        "search",
        nargs="*",
        help="Search the Plex library (title, parent, grandparent) using built-in formatting.",
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
        "-n",
        "--number",
        type=int,
        default=10,
        help="Maximum items to display with the built-in search formatter.",
    )
    parser.add_argument(
        "-L",
        "--length",
        type=int,
        default=50,
        help="Title column width when using the built-in search formatter.",
    )
    parser.add_argument(
        "-i",
        "--info",
        action="store_true",
        help="Include item summaries when using the built-in search formatter.",
    )
    parser.add_argument(
        "-p",
        "--path",
        action="store_true",
        help="Include file paths when using the built-in search formatter.",
    )
    parser.add_argument(
        "--sort",
        choices=("added", "title", "year"),
        default="added",
        help="Sort order for built-in search results (default: added).",
    )
    parser.add_argument(
        "--reverse",
        action="store_true",
        help="Reverse the sort order for built-in search results.",
    )
    parser.add_argument(
        "--deep",
        action="store_true",
        help="Include summary, path, and tag matching (slower search).",
    )
    parser.add_argument(
        "-z",
        "--zed",
        action="store_true",
        help="Show all matches sorted by year (equivalent to plex.py -z).",
    )
    parser.add_argument(
        "--list-paths",
        action="store_true",
        help="Print all candidate database paths and whether they exist.",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="Download/refresh the Plex database from the configured remote host.",
    )
    parser.add_argument(
        "--show-path",
        action="store_true",
        help="Print the detected Plex database path and exit.",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


@contextlib.contextmanager
def _ssh_client(remote: RemoteConfig) -> Iterator[paramiko.SSHClient]:
    import paramiko  # type: ignore[import]

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        hostname=remote.host,
        port=remote.port,
        username=remote.username,
        password=remote.password,
    )
    try:
        yield client
    finally:
        client.close()


def _copy_remote_file(sftp: paramiko.SFTPClient, remote_path: Path, local_path: Path) -> None:
    import paramiko  # type: ignore[import]

    local_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=str(local_path.parent), delete=False) as tmp_file:
        tmp_name = tmp_file.name
    try:
        sftp.get(str(remote_path), tmp_name)
        os.replace(tmp_name, local_path)
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp_name)


def sync_remote_db(remote: RemoteConfig, *, verbose: bool = True) -> Path:
    try:
        import paramiko  # type: ignore[import]
    except ImportError as exc:  # pragma: no cover - environment-specific
        raise RuntimeError("Paramiko is required for remote sync; install paramiko to use --update") from exc

    sync_start = perf_counter()
    if verbose:
        print(
            f"Syncing Plex DB from {remote.username}@{remote.host}:{remote.db_path} "
            f"-> {remote.cache_path}"
        )

    with _ssh_client(remote) as client:
        sftp = client.open_sftp()
        try:
            sftp.stat(str(remote.db_path))
        except FileNotFoundError as exc:  # pragma: no cover - defensive
            raise FileNotFoundError(f"Remote database not found at {remote.db_path}") from exc

        _copy_remote_file(sftp, remote.db_path, remote.cache_path)

        for suffix in ("-wal", "-shm"):
            remote_sidecar = Path(str(remote.db_path) + suffix)
            local_sidecar = Path(str(remote.cache_path) + suffix)

            try:
                sftp.stat(str(remote_sidecar))
            except FileNotFoundError:
                with contextlib.suppress(FileNotFoundError):
                    os.remove(local_sidecar)
                continue

            _copy_remote_file(sftp, remote_sidecar, local_sidecar)

    if verbose:
        size = human_size(remote.cache_path.stat().st_size)
        print(f"Downloaded {size} to {remote.cache_path} in {perf_counter() - sync_start:.2f} seconds.")

    return remote.cache_path


def _initialize_cache_schema(conn: sqlite3.Connection) -> None:
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
            summary TEXT
        )"""
    )


def build_cache_table(db_path: Path) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    source_conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        source_conn.row_factory = sqlite3.Row
        rows = source_conn.execute(
            """SELECT
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
                substr(COALESCE(mi.summary, ''), 1, 280) AS summary
            FROM metadata_items mi
            LEFT JOIN metadata_items parent ON parent.id = mi.parent_id
            LEFT JOIN metadata_items grandparent ON grandparent.id = parent.parent_id
            LEFT JOIN media_items m ON m.metadata_item_id = mi.id
            LEFT JOIN media_parts mp ON mp.media_item_id = m.id
            WHERE mi.metadata_type IN (1, 2, 4)
            GROUP BY mi.id"""
        ).fetchall()
    finally:
        source_conn.close()

    dest_conn = sqlite3.connect(str(CACHE_SQLITE_PATH))
    try:
        _initialize_cache_schema(dest_conn)
        insert_sql = """
            INSERT INTO plex_search_cache (
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
                summary
            ) VALUES (
                :id,
                :title,
                :title_low,
                :metadata_type,
                :year,
                :parent_title,
                :grandparent_title,
                :added_at,
                :duration_ms,
                :duration_meta,
                :width,
                :height,
                :size_bytes,
                :file_path,
                :disk,
                :summary
            )
        """
        dest_conn.executemany(insert_sql, [dict(row) for row in rows])
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


def ensure_cache_table(db_path: Path) -> None:
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


def _write_cache_pickle_from_conn(conn: sqlite3.Connection) -> None:
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
            summary
        FROM plex_search_cache
        ORDER BY added_at DESC
        """
    ).fetchall()
    data = [dict(row) for row in rows]
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with CACHE_PICKLE_PATH.open("wb") as fh:
        pickle.dump(data, fh)
    CACHE_STATE["records"] = data


def write_cache_pickle() -> None:
    if not CACHE_SQLITE_PATH.exists():
        return
    conn = sqlite3.connect(str(CACHE_SQLITE_PATH))
    try:
        _write_cache_pickle_from_conn(conn)
    finally:
        conn.close()


def ensure_cache_pickle() -> None:
    if not CACHE_PICKLE_PATH.exists():
        write_cache_pickle()
    else:
        CACHE_STATE["records"] = None


def load_cached_records(db_path: Path) -> List[Dict[str, Any]]:
    records = CACHE_STATE.get("records")
    if records is None:
        if not CACHE_PICKLE_PATH.exists():
            build_cache_table(db_path)
        with CACHE_PICKLE_PATH.open("rb") as fh:
            CACHE_STATE["records"] = pickle.load(fh)
    return CACHE_STATE["records"] or []


def _sort_key_title(record: Dict[str, Any]) -> str:
    return (record.get("title") or "").lower()


def _sort_key_year(record: Dict[str, Any]) -> int:
    value = record.get("year")
    return int(value) if value is not None else 0


def _sort_key_added(record: Dict[str, Any]) -> int:
    value = record.get("added_at")
    return int(value) if value is not None else 0


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


def _format_pretty_row(row: sqlite3.Row, args: argparse.Namespace) -> str:
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

    lines = [f"{title_display}  {size_str:>9}  {resolution:>5}  {duration_str} {disk}"]

    if args.info:
        summary = _truncate_summary(row["summary"])
        if summary:
            lines.append(f"  {summary}")
    if args.path and path:
        lines.append(f"  {path}")

    return "\n".join(lines)


def run_pretty_search(
    db_path: Path,
    terms: List[str],
    *,
    limit: Optional[int],
    sort: str,
    reverse: bool,
    deep: bool,
) -> tuple[List[Any], Optional[int]]:
    sort_alias_mapping = {
        "added": "added_at",
        "title": "title",
        "year": "year",
    }
    order_column = sort_alias_mapping.get(sort, "added_at")
    direction = "ASC" if sort == "title" else "DESC"
    if reverse:
        direction = "DESC" if direction == "ASC" else "ASC"

    if not deep:
        records = load_cached_records(db_path)
        if terms:
            term_list = [term.lower() for term in terms]
            filtered_full = [
                record
                for record in records
                if all(term in record["title_low"] for term in term_list)
            ]
        else:
            filtered_full = list(records)

        if sort == "title":
            reverse_flag = reverse
            filtered_full.sort(key=_sort_key_title, reverse=reverse_flag)
        elif sort == "year":
            reverse_flag = not reverse
            filtered_full.sort(key=_sort_key_year, reverse=reverse_flag)
        else:
            reverse_flag = not reverse
            filtered_full.sort(key=_sort_key_added, reverse=reverse_flag)
        total_matches = len(filtered_full)
        if limit and limit > 0:
            filtered_visible = filtered_full[:limit]
        else:
            filtered_visible = filtered_full

        return filtered_visible, total_matches

    deep_clauses: List[str] = []
    filter_params: List[object] = []

    for term in terms:
        pattern = f"%{term.lower()}%"
        deep_clauses.append(
            "(" + " OR ".join(
                [
                    "LOWER(mi.title) LIKE ?",
                    "LOWER(COALESCE(parent.title, '')) LIKE ?",
                    "LOWER(COALESCE(grandparent.title, '')) LIKE ?",
                    "LOWER(COALESCE(mi.summary, '')) LIKE ?",
                    "LOWER(COALESCE(mp.file, '')) LIKE ?",
                    "LOWER(COALESCE(tag.tag, '')) LIKE ?",
                ]
            ) + ")"
        )
        filter_params.extend([pattern, pattern, pattern, pattern, pattern, pattern])

    where_clause = " AND ".join(deep_clauses) if deep_clauses else "1=1"

    if order_column == "title":
        deep_order_column = "mi.title"
    elif order_column == "year":
        deep_order_column = "mi.year"
    else:
        deep_order_column = "mi.added_at"

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
          AND {where_clause}
        GROUP BY mi.id
        ORDER BY {deep_order_column} {direction}
    """

    data_params = list(filter_params)
    if limit and limit > 0:
        data_sql += " LIMIT ?"
        data_params.append(limit)

    total_sql = f"""
        SELECT COUNT(DISTINCT mi.id)
        FROM metadata_items mi
        LEFT JOIN metadata_items parent ON parent.id = mi.parent_id
        LEFT JOIN metadata_items grandparent ON grandparent.id = parent.parent_id
        LEFT JOIN media_items m ON m.metadata_item_id = mi.id
        LEFT JOIN media_parts mp ON mp.media_item_id = m.id
        LEFT JOIN taggings tg ON tg.metadata_item_id = mi.id
        LEFT JOIN tags tag ON tag.id = tg.tag_id
        WHERE mi.metadata_type IN (1, 2, 4)
          AND mp.file IS NOT NULL
          AND {where_clause}
    """

    with open_database(db_path) as conn:
        total_row = conn.execute(total_sql, filter_params).fetchone()
        total_matches_optional = int(total_row[0]) if total_row else None
        rows = conn.execute(data_sql, data_params).fetchall()

    return rows, total_matches_optional


def main(argv: Optional[Iterable[str]] = None) -> int:
    """Main entry point for the plex_db command."""
    args = parse_args(argv)

    if args.list_paths:
        print("Candidate Plex database paths:")
        print(format_candidates())
        return 0

    remote = load_remote_config()

    if args.update:
        if not remote:
            print(
                "Remote configuration not found. Add a [plex_remote] section to your rogkit config.",
                file=sys.stderr,
            )
            return 1
        try:
            db_path = sync_remote_db(remote, verbose=True)
            build_cache_table(db_path)
        except (Exception) as exc:
            print(f"Failed to refresh remote database: {exc}", file=sys.stderr)
            return 2
        if not args.query and not args.show_path and not args.search:
            return 0

    db_path = detect_db_path()

    if args.show_path:
        if not db_path:
            print("No Plex database detected on this machine.", file=sys.stderr)
            return 1
        print(db_path)
        return 0

    if not db_path:
        if remote:
            print("No local Plex database found; attempting to pull from remote host...")
            pull_start = perf_counter()
            try:
                db_path = sync_remote_db(remote, verbose=True)
                duration = perf_counter() - pull_start
                build_cache_table(db_path)
            except RuntimeError as exc:
                print(str(exc), file=sys.stderr)
                return 2
            except Exception as exc:
                print(f"Failed to sync remote database: {exc}", file=sys.stderr)
                return 2
            print(f"Synced remote database in {duration:.2f} seconds.")
        else:
            print(
                "No Plex database found. Set PLEX_DB_PATH, configure [plex_remote], "
                "or run with --list-paths to see checked locations.",
                file=sys.stderr,
            )
            return 1

    ensure_cache_table(db_path)

    if not args.query and not args.search:
        rows, _ = run_pretty_search(
            db_path,
            [],
            limit=args.number,
            sort="added",
            reverse=args.reverse,
            deep=False,
        )
        if not rows:
            print("No media found in the Plex database.")
            return 0
        print(f"Showing last {min(len(rows), args.number)} items added:")
        for row in rows:
            print(_format_pretty_row(row, args))
        return 0

    if args.search and not args.query:
        search_terms = [term.lower() for term in args.search]
        sort = "year" if args.zed else args.sort
        limit = None if args.zed else args.number
        rows, total_count = run_pretty_search(
            db_path,
            search_terms,
            limit=limit,
            sort=sort,
            reverse=args.reverse if not args.zed else False,
            deep=args.deep,
        )
        if not rows:
            if args.search and not args.deep:
                print("No matching media found. Try --deep for summary/tag matching.")
            else:
                print("No matching media found.")
            return 0

        visible_rows = rows if args.zed else rows[: args.number]
        total = total_count if total_count is not None else len(rows)
        match_label = "match" if total == 1 else "matches"
        if args.zed or (total_count is not None and len(visible_rows) >= total):
            heading = f"Showing all {total} {match_label}"
        elif total_count is not None:
            heading = f"Showing {len(visible_rows)} of {total} {match_label}"
        else:
            heading = f"Showing {len(visible_rows)} {match_label}"
        print(f"{heading} for {' '.join(args.search)!r}:")

        for row in visible_rows:
            print(_format_pretty_row(row, args))
        if not args.zed and total_count is not None and total > len(visible_rows):
            print(f"...and {total - len(visible_rows)} more results. Use -z to show all.")
        return 0

    if not args.query:
        size = human_size(db_path.stat().st_size)
        print(f"Plex database detected at: {db_path}")
        print(f"Size: {size}")
        print("Use `plex_db --query \"...\"` (alias `pd`) to run read-only SQL.")
        return 0

    try:
        run_query(db_path, args.query, args.limit)
    except sqlite3.OperationalError as exc:
        print(f"SQLite error: {exc}", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    start_time = perf_counter()
    result = main()
    elapsed_time = perf_counter() - start_time
    print(f"Operation completed in {elapsed_time:.4f} seconds.")
    raise SystemExit(result)
