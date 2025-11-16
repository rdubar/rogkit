"""Shared helpers for the media CLI."""

from __future__ import annotations

import contextlib
import os
import shutil
import sqlite3
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, List, Optional

from ..bin.tomlr import load_rogkit_toml
from .media_cache import CACHE_DIR

PI_DB = Path(
    "/var/lib/plexmediaserver/Library/Application Support/"
    "Plex Media Server/Plug-in Support/Databases/com.plexapp.plugins.library.db"
)
MAC_DB = Path(
    "~/Library/Application Support/"
    "Plex Media Server/Plug-in Support/Databases/com.plexapp.plugins.library.db"
).expanduser()


@dataclass(frozen=True)
class RemoteConfig:
    """Configuration for connecting to a remote Plex host."""

    host: str
    username: str
    password: Optional[str]
    port: int
    db_path: Path

    @property
    def cache_path(self) -> Path:
        """Return the path to the cache directory for the remote Plex host."""
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        return CACHE_DIR / self.db_path.name


def load_remote_config() -> Optional[RemoteConfig]:
    """Load remote connection details from the rogkit configuration."""
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

    candidates.extend([PI_DB, MAC_DB])

    remote = load_remote_config()
    if remote:
        candidates.append(remote.cache_path)

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
    """Return a human-friendly representation of a byte size."""
    if num_bytes <= 0:
        return "0B"

    size = float(num_bytes)
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    for unit in units:
        if size < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(size)}{unit}"
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
