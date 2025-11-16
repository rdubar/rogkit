"""Utilities for synchronising and refreshing the Plex database snapshot."""

from __future__ import annotations

import contextlib
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from time import perf_counter
from typing import Optional, Tuple

from .helpers import RemoteConfig, human_size


@contextlib.contextmanager
def _ssh_client(remote: RemoteConfig):
    """Yield an SSH client connected to the remote Plex host."""
    try:
        print("Importing paramiko")
        import paramiko  # type: ignore[import]  # pylint: disable=import-outside-toplevel
    except ImportError as exc:  # pragma: no cover - environment-specific
        raise RuntimeError(
            "Paramiko is required for remote sync; install paramiko to use --update"
        ) from exc

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


def _remote_file_state(
    remote: RemoteConfig,
    path: Path,
    *,
    sftp=None,
) -> Tuple[int, int]:
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
                f"stat failed for {remote_path}: {stderr.read().decode().strip()}"
            )
        size_str, mtime_str = output.split()
        return int(size_str), int(mtime_str)


def _local_file_state(path: Path) -> Tuple[int, int]:
    if not path.exists():
        return -1, -1
    stat_result = path.stat()
    return stat_result.st_size, int(stat_result.st_mtime)


def _state_path(path: Path) -> Path:
    return Path(f"{path}.state")


def _read_cached_state(path: Path) -> Optional[Tuple[int, int]]:
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


def _copy_remote_file_rsync(
    remote: RemoteConfig,
    remote_path: Path,
    local_path: Path,
) -> bool:
    """Attempt to copy a remote file using rsync for efficiency."""
    rsync_path = shutil.which("rsync")
    if not rsync_path:
        return False

    local_path.parent.mkdir(parents=True, exist_ok=True)
    remote_spec = f"{remote.username}@{remote.host}:{str(remote_path)}"
    command = [
        rsync_path,
        "--archive",
        "--compress",
        "--partial",
        "--inplace",
        "--protect-args",
        "-e",
        f"ssh -p {remote.port}",
        remote_spec,
        str(local_path),
    ]
    try:
        subprocess.run(
            command,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
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


def sync_remote_db(remote: RemoteConfig, *, prefer_rsync: bool = False, verbose: bool = True) -> Path:
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
        for suffix in ("-wal", "-shm"):
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
                raise FileNotFoundError(
                    f"Remote database not found at {remote.db_path}"
                ) from exc

            cached_state = _read_cached_state(remote.cache_path)
            local_state = _local_file_state(remote.cache_path)
            needs_copy = (
                cached_state != remote_state
                or local_state != remote_state
                or not remote.cache_path.exists()
            )
            if needs_copy:
                copied = False
                if prefer_rsync:
                    copied = _copy_remote_file_rsync(remote, remote.db_path, remote.cache_path)
                if not copied:
                    _copy_remote_file(sftp, remote.db_path, remote.cache_path)
                    copied = True
                if copied:
                    os.utime(remote.cache_path, (remote_state[1], remote_state[1]))
                    _write_cached_state(remote.cache_path, *remote_state)
                    performed_transfer = True

            for suffix in ("-wal", "-shm"):
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
        size = human_size(remote.cache_path.stat().st_size) if remote.cache_path.exists() else "0B"
        if performed_transfer:
            print(f"Downloaded {size} to {remote.cache_path} in {elapsed:.2f} seconds.")
        else:
            print(f"Cache already up to date ({size}); checked in {elapsed:.2f} seconds.")

    return remote.cache_path
