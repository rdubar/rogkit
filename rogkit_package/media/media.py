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

import contextlib
import io
import os
import socket
import time
import sqlite3
import sys
from pathlib import Path
from time import perf_counter
from typing import Any, Dict, Iterable, Optional, Sequence, Tuple

from .extra_sources.integrate import merge_extras_into_cache
from .parse_args import parse_args
from .media_cache import (
    CACHE_DIR,
    build_cache_table,
    describe_cache_state,
    ensure_cache_table,
    get_cache_metadata,
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
from .search import (
    format_pretty_row,
    format_stats,
    run_people_search,
    run_pretty_search,
)
from .update import sync_remote_db

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

    remote: Optional[RemoteConfig] = load_remote_config()
    if remote:
        lines.append(f"  ⚙︎ [remote] {remote.username}@{remote.host}:{remote.db_path}")

    return "\n".join(lines)
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
            print(format_pretty_row(row, args))
        if args.stats:
            print(format_stats(rows))
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
            print(format_pretty_row(row, args))
        if not args.zed and not args.all and total_count is not None and total > len(visible_rows):
            print(f"...and {total - len(visible_rows)} more results. Use -z to show all.")
        if args.stats:
            print(format_stats(visible_rows))
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
