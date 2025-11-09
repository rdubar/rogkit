"""
File and folder backup utility with compression.

Reads backup settings from the rogkit TOML configuration (`[backup]`) and
creates timestamped, compressed tar.gz archives of the configured source
folders. Exclusion patterns are configurable via TOML as well.

Configuration example for `~/.config/rogkit/config.toml`:

    [backup]
    backup_from = [
      "~/Projects",
      "~/Documents",
    ]
    backup_to = [
      "/mnt/backups",
      "~/Archive/Backups",
    ]
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
from pathlib import Path
from textwrap import dedent
from time import perf_counter
from typing import Iterable, List

from .bytes import byte_size
from .seconds import convert_seconds
from .tomlr import load_rogkit_toml

USER_HOME = Path.home()

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
    Configure backup paths in ~/.config/rogkit/config.toml:

        [backup]
        backup_from = [
          "~/Projects",
          "~/Documents",
        ]
        backup_to = [
          "/mnt/backups",
        ]
        # Optional:
        # file_excludes = [".DS_Store", "*.pyc"]
        # folder_excludes = ["__pycache__"]
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


def load_backup_settings() -> BackupSettings:
    """Load backup settings from rogkit TOML configuration."""
    config = load_rogkit_toml()
    backup_config = config.get("backup", {})

    sources = _as_list(backup_config.get("backup_from"))
    destinations = _as_list(backup_config.get("backup_to"))

    file_excludes = _as_list(backup_config.get("file_excludes")) or list(DEFAULT_FILE_EXCLUDES)
    folder_excludes = _as_list(backup_config.get("folder_excludes")) or list(DEFAULT_FOLDER_EXCLUDES)

    normalized_sources = [_normalize_path(path) for path in sources]
    normalized_destinations = [_normalize_path(path) for path in destinations]

    return BackupSettings(
        sources=normalized_sources,
        destinations=normalized_destinations,
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
    return any(pattern and pattern in value for pattern in patterns)


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

    valid_sources = [path for path in settings.sources if os.path.isdir(path)]
    if not valid_sources:
        print("None of the configured backup sources exist:")
        for path in settings.sources:
            print(f"  - {path}")
        print(CONFIG_HELP)
        return 1

    start_time = perf_counter()
    current_date = datetime.today().strftime('%Y-%m-%d-%H-%M')
    backup_filename = f'backup-{current_date}.tar.gz'

    primary_archive_path = valid_destinations[0]
    backup_file_path = os.path.join(primary_archive_path, backup_filename)

    print(f"Backing up folders: {valid_sources}")
    print(f"Primary backup destination: {backup_file_path}")

    file_count = 0
    total_file_size = 0
    skipped_count = 0

    with tempfile.NamedTemporaryFile(mode='w+', delete=False) as file_list:
        for folder in valid_sources:
            for root, _, files in os.walk(folder):
                if _matches_any(root, settings.folder_excludes):
                    skipped_count += len(files)
                    continue
                for file_name in files:
                    if _matches_any(file_name, settings.file_excludes):
                        skipped_count += 1
                        continue
                    file_path = os.path.join(root, file_name)
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
    