"""
File and folder backup utility with compression.

Reads whitelist entries from `~/.config/rogkit/backup.txt` (one file/folder
per line) and creates timestamped, compressed tar.gz archives of those
paths. Backup destinations and exclusion overrides still live in the rogkit
TOML configuration (`[backup]`).

Example `backup.txt`:

    ~/.zshrc
    ~/.config/rogkit
    ~/dev
    ~/bin

`config.toml` still provides destinations and optional overrides:

    [backup]
    backup_to = ["/mnt/backups", "~/Archive/Backups"]
    file_excludes = [".DS_Store", "*.pyc"]
    folder_excludes = ["__pycache__", "/tmp"]
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime
from fnmatch import fnmatch
from pathlib import Path
from textwrap import dedent
from time import perf_counter
from typing import Iterable, List

from .bytes import byte_size
from .seconds import convert_seconds
from .tomlr import load_rogkit_toml

USER_HOME = Path.home()
BACKUP_INCLUDE_PATH = Path.home() / ".config" / "rogkit" / "backup.txt"

DEFAULT_FILE_EXCLUDES = [
    '.DS_Store', '.docker', '.exe', '.git', '.idea', '.ipynb_checkpoints', '.log', '.mp3',
    '.pyc', '.sqlite', '.virtual', '.vscode', '__pycache__', 'build', 'dist', 'node_modules',
    'package-lock.json', 'package.json', 'tar.gz', 'yarn-error.log', 'yarn.lock',
]

DEFAULT_FOLDER_EXCLUDES = [
    '.git', '.idea', '/eggs', '/venv', 'data/', 'data_dir', 'env/', 'internal_packages',
    'logs', 'mvs', 'open-webui', 'parts/', 'v27',
]

CONFIG_HELP = dedent(
    """
    Configure the whitelist in ~/.config/rogkit/backup.txt (one path per line):

        ~/.zshrc
        ~/.config/rogkit
        ~/dev
        ~/bin

    Backup destinations are still read from ~/.config/rogkit/config.toml:

        [backup]
        backup_to = ["/mnt/backups", "~/Archive/Backups"]
        # Optional overrides:
        # file_excludes = [".DS_Store", "*.pyc"]
        # folder_excludes = ["__pycache__", "node_modules"]
    """
).strip()


@dataclass
class BackupSettings:
    sources: List[str]
    destinations: List[str]
    file_excludes: List[str]
    folder_excludes: List[str]


def _as_list(value: object) -> List[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value]
    return [str(value)]


def _normalize_path(path: str) -> str:
    expanded = os.path.expandvars(os.path.expanduser(path))
    if not os.path.isabs(expanded):
        expanded = os.path.join(USER_HOME, expanded)
    return os.path.abspath(expanded)


def _load_whitelist(path: Path = BACKUP_INCLUDE_PATH) -> List[str]:
    try:
        contents = path.read_text(encoding='utf-8')
    except FileNotFoundError:
        return []

    entries: List[str] = []
    for raw_line in contents.splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#'):
            continue
        entries.append(_normalize_path(line))
    return entries


def load_backup_settings() -> BackupSettings:
    """Load backup settings from rogkit TOML configuration."""
    config = load_rogkit_toml()
    backup_config = config.get("backup", {})

    whitelist = _load_whitelist()
    if not whitelist:
        whitelist = [_normalize_path(path) for path in _as_list(backup_config.get("backup_from"))]

    destinations = [_normalize_path(path) for path in _as_list(backup_config.get("backup_to"))]

    file_excludes_raw = backup_config.get("file_excludes")
    folder_excludes_raw = backup_config.get("folder_excludes")

    file_excludes = _as_list(file_excludes_raw)
    folder_excludes = _as_list(folder_excludes_raw)

    if file_excludes_raw is None:
        file_excludes = list(DEFAULT_FILE_EXCLUDES)
    if folder_excludes_raw is None:
        folder_excludes = list(DEFAULT_FOLDER_EXCLUDES)

    return BackupSettings(
        sources=whitelist,
        destinations=destinations,
        file_excludes=file_excludes,
        folder_excludes=folder_excludes,
    )


def _resolve_existing_directories(paths: Iterable[str], *, create: bool = False) -> List[str]:
    resolved: List[str] = []
    for path in paths:
        try:
            if create:
                os.makedirs(path, exist_ok=True)
                resolved.append(path)
            elif os.path.isdir(path):
                resolved.append(path)
        except OSError as exc:
            print(f"Unable to use '{path}': {exc}")
    return resolved


def _matches_any(value: str, patterns: Iterable[str]) -> bool:
    norm_value = value.replace('\\', '/')
    basename = os.path.basename(value.rstrip(os.sep))
    for pattern in patterns:
        if not pattern:
            continue
        normalized_pattern = pattern.replace('\\', '/')
        if fnmatch(norm_value, normalized_pattern):
            return True
        if fnmatch(basename, normalized_pattern):
            return True
        if normalized_pattern in norm_value:
            return True
    return False


def create_backup(settings: BackupSettings, *, verbose: bool = False) -> int:
    """Create a new backup."""
    if not settings.destinations:
        print("No backup destinations configured.")
        print(CONFIG_HELP)
        return 1

    if not settings.sources:
        print("No backup source folders configured.")
        print(CONFIG_HELP)
        return 1

    valid_destinations = _resolve_existing_directories(settings.destinations, create=True)
    if not valid_destinations:
        print("No usable backup destinations were found or could be created.")
        print(CONFIG_HELP)
        return 1

    ordered_sources = list(dict.fromkeys(settings.sources))
    source_files: List[str] = []
    source_folders: List[str] = []
    missing_sources: List[str] = []

    for path in ordered_sources:
        if os.path.isfile(path):
            source_files.append(path)
        elif os.path.isdir(path):
            source_folders.append(path)
        else:
            missing_sources.append(path)

    if missing_sources:
        print("Skipped paths that do not exist:")
        for path in missing_sources:
            print(f"  - {path}")

    if not source_files and not source_folders:
        print("No valid whitelist entries were found. Configure ~/.config/rogkit/backup.txt.")
        print(CONFIG_HELP)
        return 1

    start_time = perf_counter()
    current_date = datetime.today().strftime('%Y-%m-%d-%H-%M')
    backup_filename = f'backup-{current_date}.tar.gz'

    primary_archive_path = valid_destinations[0]
    backup_file_path = os.path.join(primary_archive_path, backup_filename)

    if source_folders:
        print("Backing up folders:")
        for path in source_folders:
            print(f"  - {path}")
    else:
        print("No folder entries in whitelist.")

    if source_files:
        print("Backing up files:")
        for path in source_files:
            print(f"  - {path}")

    print(f"Primary backup destination: {backup_file_path}")

    file_count = 0
    total_file_size = 0
    skipped_count = 0

    with tempfile.NamedTemporaryFile(mode='w+', delete=False) as file_list:
        for file_path in source_files:
            if _matches_any(file_path, settings.file_excludes):
                skipped_count += 1
                continue
            if not os.path.isfile(file_path):
                skipped_count += 1
                continue
            file_list.write(file_path + '\n')
            file_count += 1
            try:
                total_file_size += os.path.getsize(file_path)
            except (FileNotFoundError, PermissionError):
                skipped_count += 1

        for folder in source_folders:
            if _matches_any(folder, settings.folder_excludes):
                continue
            for root, dirs, files in os.walk(folder):
                dirs[:] = [
                    directory for directory in dirs
                    if not _matches_any(os.path.join(root, directory), settings.folder_excludes)
                ]
                for file_name in files:
                    file_path = os.path.join(root, file_name)
                    if _matches_any(file_path, settings.file_excludes) or _matches_any(file_name, settings.file_excludes):
                        skipped_count += 1
                        continue
                    file_list.write(file_path + '\n')
                    file_count += 1
                    try:
                        total_file_size += os.path.getsize(file_path)
                    except (FileNotFoundError, PermissionError):
                        skipped_count += 1

    if verbose:
        with open(file_list.name, 'r', encoding='utf-8') as fh:
            for line in fh:
                print(f"Added: {line.strip()}")

    elapsed_time = convert_seconds(perf_counter() - start_time)
    print(
        f"Queued {file_count:,} files for backup ({byte_size(total_file_size)}). "
        f"Skipped {skipped_count:,}. Elapsed time: {elapsed_time}."
    )

    temp_backup_path = backup_file_path + '.tmp'
    try:
        subprocess.run(
            ["tar", "-czf", temp_backup_path, "-T", file_list.name],
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        print(f"Error while creating archive: {exc}")
        os.unlink(temp_backup_path)
        return 1
    finally:
        os.unlink(file_list.name)

    os.replace(temp_backup_path, backup_file_path)

    extra_destinations = valid_destinations[1:]
    for extra_path in extra_destinations:
        try:
            os.makedirs(extra_path, exist_ok=True)
            shutil.copy2(backup_file_path, os.path.join(extra_path, backup_filename))
            print(f"Backup copied to {extra_path}")
        except OSError as exc:
            print(f"Error copying backup to {extra_path}: {exc}")

    total_elapsed = convert_seconds(perf_counter() - start_time)
    archive_size = os.path.getsize(backup_file_path)
    print(
        f"Backup created with {file_count:,} files ({byte_size(archive_size)}) "
        f"in {total_elapsed}."
    )
    print(f"Primary backup path: {backup_file_path}")
    return 0


def list_backups(settings: BackupSettings) -> int:
    """List existing backups from all destinations."""
    if not settings.destinations:
        print("No backup destinations configured.")
        print(CONFIG_HELP)
        return 1

    print("Listing backups from configured destinations...\n")
    found_any = False

    for location in settings.destinations:
        if not os.path.isdir(location):
            print(f"{location}: directory not found")
            continue

        found_any = True
        print(f"\nBackups in: {location}")
        try:
            backups = [
                entry for entry in os.listdir(location)
                if entry.startswith('backup-') and entry.endswith('.tar.gz')
            ]
            if backups:
                for backup in sorted(backups):
                    backup_path = os.path.join(location, backup)
                    backup_size = os.path.getsize(backup_path)
                    print(f" {byte_size(backup_size):<10}    {backup_path}")
            else:
                print(" No backups found in this location.")
        except OSError as exc:
            print(f" Error listing backups in {location}: {exc}")

    if not found_any:
        print("\nNo valid backup destinations found.")
        print(CONFIG_HELP)
        return 1

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description='Backup and list backups')
    parser.add_argument('-b', '--backup', action='store_true', help='Create a new backup')
    parser.add_argument('-l', '--list', action='store_true', help='List existing backups')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    args = parser.parse_args()

    if not any(vars(args).values()):
        parser.print_help()
        return 0

    settings = load_backup_settings()
    exit_code = 0

    if args.list:
        exit_code = list_backups(settings)
    if args.backup:
        backup_code = create_backup(settings, verbose=args.verbose)
        exit_code = backup_code if backup_code else exit_code

    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
    
