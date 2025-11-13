# pyright: reportMissingImports=false
"""
Daemon-backed media search and management utility.

Features:
    - Detect whether the local machine has a Plex database in the usual places
      (Pi server install, macOS desktop, cached snapshot, or a user-specified override).
    - Seamlessly refresh a cached copy of the database from a remote Plex server
      over SSH/SFTP with `--update` (or `--update-plex` to skip extras).
    - Run read-only SQL queries without risking corruption. The tool first tries
      immutable read-only access; if that fails it creates a temporary snapshot
      (including WAL/SHM) and queries the snapshot instead.
    - Automatically fall back to a deep metadata/tag search when the fast cache
      turns up empty, with optional deep scan triggers.
    - Merge pre-computed extras into the cache so external metadata appears in fast searches.
    - Use `--people` to query actors/directors on-demand via the live Plex database.

Examples:
    m --show-path
    m --update
    m --update-plex
    m --query "SELECT title, year FROM metadata_items WHERE title LIKE '%Dylan%'" --limit 10
"""

from __future__ import annotations

import argparse
import contextlib
import io
import os
import socket
import subprocess
import time
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path
from time import perf_counter
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, cast

from ..bin.bytes import byte_size
from .extra_sources.integrate import merge_extras_into_cache
from .media_cache import (
    CACHE_DIR,
    build_cache_table,
    describe_cache_state,
    ensure_cache_table,
    get_cache_metadata,
    load_cached_records,
)
from .daemon import (
    MediaDaemon,
    daemon_env_guard,
    request_daemon_shutdown as _daemon_request_shutdown,
    send_daemon_message as _daemon_send_message,
    spawn_daemon_process as _daemon_spawn_process,
    wait_for_daemon_startup as _daemon_wait_for_startup,
)
from .helpers import (
    MAC_DB,
    PI_DB,
    RemoteConfig,
    candidate_db_paths,
    detect_db_path,
    human_size,
    load_remote_config,
    open_database,
)

DAEMON_ENV_FLAG = "PLEX_DB_DAEMON_ACTIVE"
DAEMON_SOCKET_NAME = "media_daemon.sock"
DAEMON_STARTUP_TIMEOUT_SECONDS = 5.0
DAEMON_REQUEST_TIMEOUT_SECONDS = 30.0

def _daemon_socket_path() -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / DAEMON_SOCKET_NAME


def _send_daemon_message(payload: Dict[str, Any], *, timeout: float) -> Dict[str, Any]:
    return _daemon_send_message(_daemon_socket_path(), payload, timeout=timeout)


def _spawn_daemon_process() -> bool:
    python = sys.executable or "python3"
    module = "rogkit_package.media.media"
    return _daemon_spawn_process(python, module, DAEMON_ENV_FLAG)


def _wait_for_daemon_startup(deadline: float) -> bool:
    timeout = max(0.0, deadline - time.monotonic())
    return _daemon_wait_for_startup(_daemon_socket_path(), timeout=timeout)


def _request_daemon_shutdown() -> bool:
    return _daemon_request_shutdown(
        _daemon_socket_path(),
        timeout=DAEMON_REQUEST_TIMEOUT_SECONDS,
    )

def _execute_cli_in_daemon(argv: Sequence[str]) -> Tuple[int, str, str]:
    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()
    try:
        with daemon_env_guard(DAEMON_ENV_FLAG):
            with contextlib.redirect_stdout(stdout_buffer), contextlib.redirect_stderr(
                stderr_buffer
            ):
                exit_code = main(argv)  # type: ignore[name-defined]
    except SystemExit as exc:
        code = exc.code
        exit_code = int(code) if isinstance(code, int) else 0
    except Exception as exc:  # pragma: no cover - defensive  # pylint: disable=broad-except
        stderr_buffer.write(f"media daemon execution failure: {exc}\n")
        return 1, stdout_buffer.getvalue(), stderr_buffer.getvalue()
    return exit_code, stdout_buffer.getvalue(), stderr_buffer.getvalue()

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
    """Return a human-readable list of known Plex database paths."""
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
    """Parse command-line arguments for the `pd` utility."""
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
        "-a",
        "--all",
        action="store_true",
        help="Show all results instead of limiting to --number.",
    )
    parser.add_argument(
        "-L",
        "--length",
        type=int,
        default=40,
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
        "-r",
        action="store_true",
        help="Reverse the sort order for built-in search results.",
    )
    parser.add_argument(
        "--deep",
        "-d_",
        action="store_true",
        help="Include summary, path, and tag matching (slower search; tried automatically if cache search has no matches).",
    )
    parser.add_argument(
        "--zed",
        "-z",
        action="store_true",
        help="Show all matches sorted by year.",
    )
    parser.add_argument(
        "--list-paths",
        action="store_true",
        help="Print all candidate database paths and whether they exist.",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="Refresh the Plex database and merge extra media sources into the cache.",
    )
    parser.add_argument(
        "--update-plex",
        action="store_true",
        help="Refresh the Plex database snapshot without merging extras.",
    )
    parser.add_argument(
        "--show-path",
        action="store_true",
        help="Print the detected Plex database path and exit.",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show aggregate stats (count, total runtime, total size) for the displayed items.",
    )
    parser.add_argument(
        "--people",
        action="store_true",
        help="Search actors/directors via the live Plex database.",
    )
    parser.add_argument(
        "--daemon",
        action="store_true",
        help="Run the media daemon in the foreground, serving subsequent CLI requests.",
    )
    parser.add_argument(
        "--stop-daemon",
        action="store_true",
        help="Ask the running media daemon to exit.",
    )
    parser.add_argument(
        "--no-daemon",
        action="store_true",
        help="Run locally without attempting to use the background daemon.",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


@contextlib.contextmanager
def _ssh_client(remote: RemoteConfig):
    """Yield an SSH client connected to the remote Plex host."""
    try:
        import paramiko  # type: ignore[import]  # pylint: disable=import-outside-toplevel
    except ImportError as exc:  # pragma: no cover - environment-specific
        raise RuntimeError("Paramiko is required for remote sync; install paramiko to use --update") from exc

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




def _remote_file_state(remote: RemoteConfig, path: Path, *, sftp=None) -> tuple[int, int]:
    """Return (size, mtime) for a remote file."""
    remote_path = str(path)
    if sftp is not None:
        attrs = sftp.stat(remote_path)
        return attrs.st_size, int(attrs.st_mtime)

    with _ssh_client(remote) as client:
        _, stdout, stderr = client.exec_command(f"stat -c '%s %Y' {remote_path}")
        output = stdout.read().decode().strip()
        if not output:
            raise FileNotFoundError(
                f"stat failed for {remote_path}: {stderr.read().decode().strip()}")
        size_str, mtime_str = output.split()
        return int(size_str), int(mtime_str)


def _local_file_state(path: Path) -> tuple[int, int]:
    if not path.exists():
        return -1, -1
    stat_result = path.stat()
    return stat_result.st_size, int(stat_result.st_mtime)


def _state_path(path: Path) -> Path:
    return Path(f"{path}.state")


def _read_cached_state(path: Path) -> Optional[tuple[int, int]]:
    state_file = _state_path(path)
    if not state_file.exists():
        return None
    try:
        size_str, mtime_str = state_file.read_text(encoding="utf-8").strip().split()
        return int(size_str), int(mtime_str)
    except (OSError, ValueError):
        return None


def _write_cached_state(path: Path, size: int, mtime: int) -> None:
    state_file = _state_path(path)
    state_file.write_text(f"{size} {mtime}\n", encoding="utf-8")


def _remove_cached_state(path: Path) -> None:
    state_file = _state_path(path)
    with contextlib.suppress(FileNotFoundError):
        state_file.unlink()


def _copy_remote_file_rsync(remote: RemoteConfig, remote_path: Path, local_path: Path) -> bool:
    """Attempt to copy a remote file using rsync for efficiency."""
    rsync_path = shutil.which('rsync')
    if not rsync_path:
        return False

    local_path.parent.mkdir(parents=True, exist_ok=True)
    remote_spec = f"{remote.username}@{remote.host}:{str(remote_path)}"
    command = [
        rsync_path,
        '--archive',
        '--compress',
        '--partial',
        '--inplace',
        '--protect-args',
        '-e',
        f"ssh -p {remote.port}",
        remote_spec,
        str(local_path),
    ]
    try:
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except subprocess.CalledProcessError:
        return False


def _copy_remote_file(sftp, remote_path: Path, local_path: Path) -> None:
    """Copy a single file from the remote host via SFTP."""
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
    """Sync the remote Plex database to the local cache."""
    sync_start = perf_counter()
    if verbose:
        print(
            f"Syncing Plex DB from {remote.username}@{remote.host}:{remote.db_path} "
            f"-> {remote.cache_path}"
        )

    performed_transfer = False

    if remote.db_path.exists():  # Local access available; no SSH needed
        src_state = _local_file_state(remote.db_path)
        cached_state = _read_cached_state(remote.cache_path)
        if cached_state != src_state or not remote.cache_path.exists():
            remote.cache_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(remote.db_path, remote.cache_path)
            _write_cached_state(remote.cache_path, *src_state)
            performed_transfer = True
        for suffix in ('-wal', '-shm'):
            source_sidecar = Path(str(remote.db_path) + suffix)
            dest_sidecar = Path(str(remote.cache_path) + suffix)
            if source_sidecar.exists():
                side_state = _local_file_state(source_sidecar)
                cached_side = _read_cached_state(dest_sidecar)
                if cached_side != side_state or not dest_sidecar.exists():
                    shutil.copy2(source_sidecar, dest_sidecar)
                    _write_cached_state(dest_sidecar, *side_state)
                    performed_transfer = True
            else:
                with contextlib.suppress(FileNotFoundError):
                    os.remove(dest_sidecar)
                _remove_cached_state(dest_sidecar)
    else:
        with _ssh_client(remote) as client:
            sftp = client.open_sftp()
            try:
                remote_state = _remote_file_state(remote, remote.db_path, sftp=sftp)
            except FileNotFoundError as exc:  # pragma: no cover - defensive
                sftp.close()
                raise FileNotFoundError(f"Remote database not found at {remote.db_path}") from exc

            cached_state = _read_cached_state(remote.cache_path)
            if cached_state != remote_state or not remote.cache_path.exists():
                if not _copy_remote_file_rsync(remote, remote.db_path, remote.cache_path):
                    _copy_remote_file(sftp, remote.db_path, remote.cache_path)
                _write_cached_state(remote.cache_path, *remote_state)
                performed_transfer = True

            for suffix in ('-wal', '-shm'):
                remote_sidecar = Path(str(remote.db_path) + suffix)
                local_sidecar = Path(str(remote.cache_path) + suffix)

                try:
                    attrs = sftp.stat(str(remote_sidecar))
                except FileNotFoundError:
                    with contextlib.suppress(FileNotFoundError):
                        os.remove(local_sidecar)
                    _remove_cached_state(local_sidecar)
                    continue

                side_state = (attrs.st_size, int(attrs.st_mtime))
                cached_side = _read_cached_state(local_sidecar)
                if cached_side == side_state and local_sidecar.exists():
                    continue

                if not _copy_remote_file_rsync(remote, remote_sidecar, local_sidecar):
                    _copy_remote_file(sftp, remote_sidecar, local_sidecar)
                _write_cached_state(local_sidecar, *side_state)
                performed_transfer = True

            sftp.close()

    elapsed = perf_counter() - sync_start
    if verbose:
        size = human_size(remote.cache_path.stat().st_size) if remote.cache_path.exists() else '0B'
        if performed_transfer:
            print(f"Downloaded {size} to {remote.cache_path} in {elapsed:.2f} seconds.")
        else:
            print(f"Cache already up to date ({size}); checked in {elapsed:.2f} seconds.")

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


def _sort_key_title(record: Dict[str, Any]) -> str:
    """Sort cached records alphabetically by title."""
    return (record.get("title") or "").lower()


def _sort_key_year(record: Dict[str, Any]) -> int:
    """Sort cached records by release year (ascending)."""
    value = record.get("year")
    return int(value) if value is not None else 0


def _sort_key_added(record: Dict[str, Any]) -> int:
    """Sort cached records by the time they were added to Plex (descending)."""
    value = record.get("added_at")
    return int(value) if value is not None else 0


def _record_matches_deep(record: Dict[str, Any], terms: Sequence[str]) -> bool:
    """Check if a cached record matches a list of search terms."""
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
    """Collapse whitespace and shorten long summaries for CLI output."""

    if not summary:
        return ""
    squashed = " ".join(summary.split())
    if len(squashed) <= max_length:
        return squashed
    return f"{squashed[: max_length - 1]}…"


def _format_cache_age(seconds: Optional[float]) -> str:
    """Format a cache age in seconds as a string in the format HH:MM:SS."""
    if seconds is None:
        return "unknown"
    seconds = max(0, int(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours}:{minutes:02}:{secs:02}"


def _format_duration(duration_ms: Optional[int]) -> str:
    """Format a duration in milliseconds as a string in the format HH:MM."""
    if not duration_ms:
        return ""
    seconds = duration_ms // 1000
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    return f"{hours:02}:{minutes:02}"


def _row_value(row: Any, key: str, default: Any = None) -> Any:
    """Return a field from a sqlite3.Row or mapping, falling back to a default."""

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
    """Infer the resolution from a width and height."""
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
    """Format a disk label from a file path."""
    if not path or len(path) <= 10:
        return ""
    return f"[{path[10]}]"


def _compose_title(row: sqlite3.Row) -> str:
    """Compose a title from a row of media data."""
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
    """Format a row of media data for pretty printing."""
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

    lines = [f"{source_label:<7}  {size_str:>9}  {resolution:>5}  {duration_str}  {title_display}"]

    if args.info:
        summary = _truncate_summary(row["summary"])
        if summary:
            lines.append(f"  {summary}")
    if args.path and path:
        lines.append(f"  {path}")

    return "\n".join(lines)


def _format_duration_human(total_seconds: int) -> str:
    """Format a duration in seconds as a human-readable string."""
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


def _format_stats(rows: Sequence[Any]) -> str:
    """Format statistics for a list of media items."""
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




PEOPLE_TAG_TYPES = (4, 5, 6, 7, 10)


def run_people_search(
    db_path: Path,
    terms: list[str],
    *,
    limit: Optional[int],
    sort: str,
    reverse: bool,
) -> tuple[list[Any], Optional[int]]:
    """Run a SQL search focused on people (actors, directors, writers)."""

    if not terms:
        return [], 0

    where_fragments: list[str] = []
    params: list[str] = []
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
) -> tuple[List[Any], Optional[int]]:
    """Execute the fast or deep search path and return matching records."""
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
            filtered_full = []
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
    filtered_full = [
        record
        for record in records
        if _record_matches_deep(record, term_list)
    ]

    _apply_sort(filtered_full)
    total_matches = len(filtered_full)
    if limit and limit > 0:
        filtered_full = filtered_full[:limit]

    return filtered_full, total_matches


def run_daemon() -> int:
    """Run the media daemon."""
    socket_path = _daemon_socket_path()
    daemon = MediaDaemon(socket_path, _execute_cli_in_daemon)
    try:
        daemon.serve_forever()
    except KeyboardInterrupt:  # pragma: no cover - manual interruption
        daemon.stop()
        print("Media daemon interrupted.")
    return 0


def _forward_to_daemon(argv_list: Sequence[str], *, auto_start: bool = True) -> Optional[int]:
    """Forward a command to the media daemon."""
    try:
        response = _send_daemon_message(
            {"action": "execute", "argv": list(argv_list)},
            timeout=DAEMON_REQUEST_TIMEOUT_SECONDS,
        )
    except (FileNotFoundError, ConnectionError, OSError, socket.timeout):
        if not auto_start:
            return None
        print(
            "media: starting background daemon and warming cache...",
            file=sys.stderr,
        )
        sys.stderr.flush()
        if not _spawn_daemon_process():
            print(
                "media: unable to launch daemon automatically; running locally.",
                file=sys.stderr,
            )
            return None
        deadline = time.monotonic() + DAEMON_STARTUP_TIMEOUT_SECONDS
        if not _wait_for_daemon_startup(deadline):
            print(
                "media: daemon did not become ready; running locally.",
                file=sys.stderr,
            )
            return None
        try:
            response = _send_daemon_message(
                {"action": "execute", "argv": list(argv_list)},
                timeout=DAEMON_REQUEST_TIMEOUT_SECONDS,
            )
        except (FileNotFoundError, ConnectionError, OSError, socket.timeout):
            print(
                "media: daemon connection failed after startup; running locally.",
                file=sys.stderr,
            )
            return None
    status = response.get("status")
    if status != "ok":
        error = response.get("error", "Unknown daemon error")
        print(f"[media daemon] {error}", file=sys.stderr)
        return int(response.get("exit_code", 1))
    stdout_text = response.get("stdout") or ""
    stderr_text = response.get("stderr") or ""
    if stdout_text:
        sys.stdout.write(stdout_text)
    if stderr_text:
        sys.stderr.write(stderr_text)
    return int(response.get("exit_code", 0))


def main(argv: Optional[Iterable[str]] = None) -> int:
    """Entry point for the `pd` command-line interface."""
    argv_list = list(argv) if argv is not None else sys.argv[1:]
    args = parse_args(argv_list)

    if os.environ.get(DAEMON_ENV_FLAG) != "1" and not args.no_daemon and not args.daemon and not args.stop_daemon:
        forwarded_exit = _forward_to_daemon(argv_list)
        if forwarded_exit is not None:
            return forwarded_exit

    if args.daemon:
        return run_daemon()

    if args.update and args.update_plex:
        print(
            "Specify only one of --update or --update-plex.",
            file=sys.stderr,
        )
        return 2

    if args.stop_daemon:
        if _request_daemon_shutdown():
            print("Requested media daemon shutdown.")
            return 0
        print("No media daemon appears to be running.", file=sys.stderr)
        return 1

    if args.list_paths:
        print("Candidate Plex database paths:")
        print(format_candidates())
        return 0

    remote = load_remote_config()

    if args.update or args.update_plex:
        if not remote:
            print(
                "Remote configuration not found. Add a [plex_remote] section to your rogkit config.",
                file=sys.stderr,
            )
            return 1
        include_extras = args.update
        total_steps = 3 if include_extras else 2
        current_step = 1
        try:
            print(f"[Step {current_step}/{total_steps}] Refreshing Plex snapshot...", flush=True)
            synced_db_path = sync_remote_db(remote, verbose=True)
            current_step += 1
            print(f"[Step {current_step}/{total_steps}] Rebuilding fast media cache...", flush=True)
            build_cache_table(synced_db_path)
            if include_extras:
                current_step += 1
                print(f"[Step {current_step}/{total_steps}] Integrating extras catalog...", flush=True)
                inserted = merge_extras_into_cache(None, None, None)
                if inserted:
                    print(f"Integrated {inserted} extra record(s) into the cache.")
                else:
                    print("No extras catalog entries were merged.")
            else:
                print("Extras integration skipped (--update-plex).")
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        except (OSError, sqlite3.Error) as exc:
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

    if db_path is None:
        if remote:
            print("No local Plex database found; attempting to pull from remote host...")
            pull_start = perf_counter()
            try:
                synced_db_path = sync_remote_db(remote, verbose=True)
                duration = perf_counter() - pull_start
                build_cache_table(synced_db_path)
                db_path = synced_db_path
            except RuntimeError as exc:
                print(str(exc), file=sys.stderr)
                return 2
            except (OSError, sqlite3.Error) as exc:
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

    total_items, cache_age = get_cache_metadata(db_path)
    print(describe_cache_state(total_items, cache_age))

    if not args.query and not args.search:
        rows, _ = run_pretty_search(
            db_path,
            [],
            limit=None if args.all else args.number,
            sort="added",
            reverse=args.reverse,
            deep=False,
        )
        if not rows:
            print("No media found in the Plex database.")
            return 0
        if args.all:
            print(f"Showing all {len(rows)} items added:")
        else:
            print(f"Showing last {min(len(rows), args.number)} items added:")
        for row in rows:
            print(_format_pretty_row(row, args))
        if args.stats:
            print(_format_stats(rows))
        return 0


    if args.search and not args.query:
        search_terms = [term.lower() for term in args.search]
        sort = "year" if args.zed else args.sort
        limit = None if args.all or args.zed else args.number
        reverse_value = args.reverse if not args.zed else False

        mode_label = ""
        if args.people:
            rows, total_count = run_people_search(
                db_path,
                search_terms,
                limit=limit,
                sort=sort,
                reverse=reverse_value,
            )
            mode_label = " (people search)"
        else:
            rows, total_count = run_pretty_search(
                db_path,
                search_terms,
                limit=limit,
                sort=sort,
                reverse=reverse_value,
                deep=args.deep,
            )
            if not rows and not args.deep:
                print("No cached matches found; running deep search...")
                rows, total_count = run_pretty_search(
                    db_path,
                    search_terms,
                    limit=limit,
                    sort=sort,
                    reverse=reverse_value,
                    deep=True,
                )
                mode_label = " (deep search)"
            elif args.deep:
                mode_label = " (deep search)"

        if not rows:
            print("No matching media found.")
            return 0

        visible_rows = rows
        total = total_count if total_count is not None else len(rows)
        match_label = "match" if total == 1 else "matches"
        if args.zed or args.all or (total_count is not None and len(visible_rows) >= total):
            heading = f"Showing all {total} {match_label}"
        elif total_count is not None:
            heading = f"Showing {len(visible_rows)} of {total} {match_label}"
        else:
            heading = f"Showing {len(visible_rows)} {match_label}"
        print(f"{heading}{mode_label} for {' '.join(args.search)!r}:")

        for row in visible_rows:
            print(_format_pretty_row(row, args))
        if not args.zed and not args.all and total_count is not None and total > len(visible_rows):
            print(f"...and {total - len(visible_rows)} more results. Use -z to show all.")
        if args.stats:
            print(_format_stats(visible_rows))
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

def main_timer():
    """Main entry point for the plex_db command with timing."""
    start_time = perf_counter()
    exit_code = main()
    elapsed_time = perf_counter() - start_time
    print(f"Operation completed in {elapsed_time:.4f} seconds.")
    return exit_code

if __name__ == "__main__":
    raise SystemExit(main_timer())
