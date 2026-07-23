"""
File and folder backup utility with compression.

Preferred configuration is per-backup sets in `~/.config/rogkit/config.toml`
under `[[backup.set]]` entries (each with `name`, `paths`, and `destinations`).
Legacy whitelist entries from `~/.config/rogkit/backup.txt` are still supported
as a fallback when no sets are defined.

Secrets handling
----------------
Declare filename patterns that count as secrets in `[backup]`:

    [backup]
    secret_patterns = ["secrets.toml", ".env"]

Sets with `include_secrets = false` (the default) automatically exclude files
matching those patterns — use this for any cloud-synced destination. Sets with
`include_secrets = true` include them — use this for local-only destinations.

Example per-set config:

    # Cloud-synced — secrets excluded automatically
    [[backup.set]]
    name = "CloudBackup"
    destinations = ["~/Dropbox/Backups", "~/Library/Mobile Documents/..."]
    paths = ["~/.ssh", "~/.config/", "~/dev"]
    keep = 5

    # Local only — secrets included
    [[backup.set]]
    name = "LocalBackup"
    include_secrets = true
    destinations = ["~/Archive/Backups"]
    paths = ["~/.ssh", "~/.config/", "~/dev", "~/.env"]

    # Encrypted — secrets safe for Pi/off-machine storage
    [[backup.encrypted_set]]
    name = "Secrets"
    recipients_file = "~/.config/rogkit/backup-recipients.txt"
    destinations = ["~/Archive/Backups/encrypted"]
    paths = ["~/.ssh", "~/.config", "~/life/medical", "~/life/household"]
    keep = 5

Optional global overrides (shared by all sets):

    [backup]
    secret_patterns = ["secrets.toml", ".env"]
    file_excludes = [".DS_Store", "*.pyc"]
    folder_excludes = ["__pycache__", "/tmp"]
    keep = 10   # default retention for any set that doesn't set its own

Retention
---------
Set `keep = N` (per-set, or as a `[backup]`-level default above) to delete all
but the N most recent archives — and their `.manifest.json` sidecars — from
each of a set's destinations after a successful run. Pruning is per
destination (an archive present locally but not yet synced to a cloud
destination doesn't count against that cloud destination's N), runs only
after the new archive is written and copied everywhere, and never runs on
`--plan`/`--dry-run`. `--keep N` on the CLI overrides every selected set's
configured value for that invocation only.

Legacy `backup.txt` whitelist (one path per line) also works when no sets
are defined:

    ~/.zshrc
    ~/.ssh
    ~/.config/rogkit
    ~/dev
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from fnmatch import fnmatch
from pathlib import Path
from textwrap import dedent
from time import perf_counter
from typing import Iterable, List, Sequence

from .bytes import byte_size
from .seconds import convert_seconds
from .tomlr import load_rogkit_toml

USER_HOME = Path.home()
BACKUP_INCLUDE_PATH = Path.home() / ".config" / "rogkit" / "backup.txt"

try:  # Optional rich dependency for colored output
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text

    console = Console()
    RICH_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover
    console = None
    RICH_AVAILABLE = False

DEFAULT_FILE_EXCLUDES = [
    '.DS_Store', '.docker', '.exe', '.git', '.idea', '.ipynb_checkpoints', '.log', '.mp3',
    '.pyc', '.sqlite', '.virtual', '.vscode', '__pycache__', 'build', 'dist', 'node_modules',
    'package-lock.json', 'package.json', 'tar.gz', 'yarn-error.log', 'yarn.lock',
]

DEFAULT_FOLDER_EXCLUDES = [
    '.git', '.idea', '/eggs', '/venv', 'data/', 'data_dir', 'env/', 'internal_packages',
    'logs', 'mvs', 'open-webui', 'parts/', 'v27',
]


def _print_message(message: str, style: str | None = None) -> None:
    if RICH_AVAILABLE:
        console.print(Text(message, style=style) if style else message)
    else:
        print(message)


def _print_paths(title: str, paths: list[str], style: str, *, plain: bool = False) -> None:
    if not paths:
        _print_message(f"{title}: (none)")
        return

    if RICH_AVAILABLE and not plain:
        table = Table(box=None, show_header=False, padding=(0, 1))
        table.add_column(justify="right", style="bold " + style)
        table.add_column(style=style)
        for index, path in enumerate(paths, start=1):
            table.add_row(f"{index}.", path)
        console.print(Panel(table, title=title, border_style=style, padding=(0, 1)))
    else:
        print(title)
        for path in paths:
            print(f"  - {path}")


def _print_rule(title: str, *, plain: bool = False) -> None:
    if RICH_AVAILABLE and not plain:
        console.rule(f"[bold]{title}")
    else:
        underline = "-" * len(title)
        print(f"\n{title}\n{underline}")


def _render_backup_summary(file_count: int, skipped_count: int, archive_size: int, elapsed: str, *, plain: bool = False) -> None:
    summary = [
        ("Files Archived", f"{file_count:,}"),
        ("Skipped", f"{skipped_count:,}"),
        ("Archive Size", byte_size(archive_size)),
        ("Total Time", elapsed),
    ]

    if RICH_AVAILABLE and not plain:
        table = Table(show_header=False, box=None, pad_edge=False)
        table.add_column(justify="right", style="bold green")
        table.add_column(style="white")
        for label, value in summary:
            table.add_row(f"{label}:", value)
        console.print(Panel(table, title="Backup Summary", border_style="green", padding=(0, 1)))
    else:
        print("\nBackup Summary")
        print("--------------")
        for label, value in summary:
            print(f"{label}: {value}")


def _render_backup_listing(location: str, rows: list[tuple[str, str]], *, plain: bool = False) -> None:
    if RICH_AVAILABLE and not plain:
        table = Table(title=f"Backups in {location}", box=None)
        table.add_column("Size", style="cyan", justify="right", no_wrap=True)
        table.add_column("Path", style="white")
        for size, path in rows:
            table.add_row(size, path)
        console.print(table)
    else:
        print(f"\nBackups in: {location}")
        for size, path in rows:
            print(f" {size:<12} {path}")

CONFIG_HELP = dedent(
    """
    Preferred: define per-backup sets in ~/.config/rogkit/config.toml:

        [backup]
        secret_patterns = ["secrets.toml", ".env"]   # excluded from cloud sets

        [[backup.set]]
        name = "CloudBackup"
        destinations = ["~/Dropbox/Backups"]
        paths = ["~/.ssh", "~/.config/", "~/dev"]
        keep = 5   # optional: prune to the 5 most recent archives per destination

        [[backup.set]]
        name = "LocalBackup"
        include_secrets = true
        destinations = ["~/Archive/Backups"]
        paths = ["~/.ssh", "~/.config/", "~/dev", "~/.env"]

        [[backup.encrypted_set]]
        name = "Secrets"
        recipients_file = "~/.config/rogkit/backup-recipients.txt"
        destinations = ["~/Archive/Backups/encrypted"]
        paths = ["~/.ssh", "~/.config", "~/life/medical"]

    Optional global overrides:

        [backup]
        file_excludes = [".DS_Store", "*.pyc"]
        folder_excludes = ["__pycache__", "node_modules"]

    Legacy fallback whitelist in ~/.config/rogkit/backup.txt (one path per line)
    is still supported when no sets are defined:

        ~/.zshrc
        ~/.ssh
        ~/.config/rogkit
        ~/dev
    """
).strip()


@dataclass
class BackupSet:
    name: str
    sources: List[str]
    destinations: List[str]
    file_excludes: List[str]
    folder_excludes: List[str]
    secret_patterns: List[str] = field(default_factory=list)
    secrets_excluded: bool = False
    encrypted: bool = False
    recipients: List[str] | None = None
    recipients_file: str | None = None
    keep: int | None = None


@dataclass
class BackupPlan:
    settings: BackupSet
    valid_destinations: List[str]
    source_files: List[str]
    source_folders: List[str]
    missing_sources: List[str]
    included_files: List[str]
    skipped_count: int
    total_file_size: int


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


def _slugify(value: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in value)
    return safe or "backup"


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


def _build_backup_sets_from_config(backup_config: dict) -> List[BackupSet]:
    sets_raw = backup_config.get("set") or []
    if not isinstance(sets_raw, list):
        return []

    base_file_excludes = _as_list(backup_config.get("file_excludes")) or list(DEFAULT_FILE_EXCLUDES)
    base_folder_excludes = _as_list(backup_config.get("folder_excludes")) or list(DEFAULT_FOLDER_EXCLUDES)
    base_destinations = [_normalize_path(path) for path in _as_list(backup_config.get("backup_to"))]
    base_sources = [_normalize_path(path) for path in _as_list(backup_config.get("backup_from"))]
    secret_patterns = _as_list(backup_config.get("secret_patterns"))
    base_keep = backup_config.get("keep")

    def _build(entry: dict, *, encrypted: bool, default_name: str, default_include_secrets: bool) -> BackupSet:
        name = entry.get("name") or default_name
        sources_raw = _as_list(entry.get("paths") or entry.get("sources") or base_sources)
        destinations_raw = _as_list(entry.get("destinations") or base_destinations)
        file_excludes = base_file_excludes + _as_list(entry.get("file_excludes"))
        folder_excludes = base_folder_excludes + _as_list(entry.get("folder_excludes"))
        include_secrets = bool(entry.get("include_secrets", default_include_secrets))
        secrets_excluded = bool(secret_patterns) and not include_secrets
        applied_secret_patterns = list(secret_patterns) if secrets_excluded else []
        keep_raw = entry.get("keep", base_keep)
        return BackupSet(
            name=str(name),
            sources=[_normalize_path(p) for p in sources_raw],
            destinations=[_normalize_path(p) for p in destinations_raw],
            file_excludes=file_excludes,
            folder_excludes=folder_excludes,
            secret_patterns=applied_secret_patterns,
            secrets_excluded=secrets_excluded,
            encrypted=encrypted,
            recipients=_as_list(entry.get("recipients")) if encrypted else None,
            recipients_file=(
                _normalize_path(str(entry["recipients_file"]))
                if encrypted and entry.get("recipients_file")
                else None
            ),
            keep=int(keep_raw) if keep_raw is not None else None,
        )

    backup_sets: List[BackupSet] = []
    for entry in sets_raw:
        if isinstance(entry, dict):
            backup_sets.append(_build(entry, encrypted=False, default_name="backup", default_include_secrets=False))

    encrypted_sets_raw = backup_config.get("encrypted_set") or []
    if isinstance(encrypted_sets_raw, list):
        for entry in encrypted_sets_raw:
            if isinstance(entry, dict):
                backup_sets.append(_build(entry, encrypted=True, default_name="encrypted", default_include_secrets=True))
    return backup_sets


def load_backup_settings() -> List[BackupSet]:
    """Load backup settings from rogkit TOML configuration."""
    config = load_rogkit_toml()
    backup_config = config.get("backup", {})

    backup_sets = _build_backup_sets_from_config(backup_config)
    if backup_sets:
        return backup_sets

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

    keep_raw = backup_config.get("keep")

    return [
        BackupSet(
            name="default",
            sources=whitelist,
            destinations=destinations,
            file_excludes=file_excludes,
            folder_excludes=folder_excludes,
            keep=int(keep_raw) if keep_raw is not None else None,
        )
    ]


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
            _print_message(f"Unable to use '{path}': {exc}", "bold red")
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


def _matches_basename(file_name: str, patterns: Iterable[str]) -> bool:
    """Pattern matching against the file's basename only.

    Used for `secret_patterns` so a pattern like `.env` excludes files named
    exactly `.env` (or matching the glob), but NOT a sibling path containing
    `.env` as a substring (e.g. `myenv/file.txt`, `.envrc`).
    """
    for pattern in patterns:
        if not pattern:
            continue
        if fnmatch(file_name, pattern.replace('\\', '/')):
            return True
    return False


def _collect_sources(settings: BackupSet) -> tuple[List[str], List[str], List[str]]:
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

    return source_files, source_folders, missing_sources


def _collect_included_files(settings: BackupSet, source_files: list[str], source_folders: list[str]) -> tuple[List[str], int, int]:
    included_files: List[str] = []
    skipped_count = 0
    total_file_size = 0

    for file_path in source_files:
        file_name = os.path.basename(file_path)
        if _matches_any(file_path, settings.file_excludes):
            skipped_count += 1
            continue
        if _matches_basename(file_name, settings.secret_patterns):
            skipped_count += 1
            continue
        if not os.path.isfile(file_path):
            skipped_count += 1
            continue
        included_files.append(file_path)
        try:
            total_file_size += os.path.getsize(file_path)
        except (FileNotFoundError, PermissionError):
            skipped_count += 1

    for folder in source_folders:
        if _matches_any(folder, settings.folder_excludes):
            skipped_count += 1
            continue
        for root, dirs, files in os.walk(folder):
            kept_dirs = []
            for directory in dirs:
                if _matches_any(os.path.join(root, directory), settings.folder_excludes):
                    skipped_count += 1
                else:
                    kept_dirs.append(directory)
            dirs[:] = kept_dirs
            for file_name in files:
                file_path = os.path.join(root, file_name)
                if not os.path.isfile(file_path):
                    skipped_count += 1
                    continue
                if _matches_any(file_path, settings.file_excludes) or _matches_any(file_name, settings.file_excludes):
                    skipped_count += 1
                    continue
                if _matches_basename(file_name, settings.secret_patterns):
                    skipped_count += 1
                    continue
                included_files.append(file_path)
                try:
                    total_file_size += os.path.getsize(file_path)
                except (FileNotFoundError, PermissionError):
                    skipped_count += 1

    return included_files, skipped_count, total_file_size


def build_backup_plan(settings: BackupSet, *, create_destinations: bool = False) -> BackupPlan:
    """Build a backup plan without creating an archive."""
    valid_destinations = _resolve_existing_directories(settings.destinations, create=create_destinations)
    source_files, source_folders, missing_sources = _collect_sources(settings)
    included_files, skipped_count, total_file_size = _collect_included_files(settings, source_files, source_folders)

    return BackupPlan(
        settings=settings,
        valid_destinations=valid_destinations,
        source_files=source_files,
        source_folders=source_folders,
        missing_sources=missing_sources,
        included_files=included_files,
        skipped_count=skipped_count,
        total_file_size=total_file_size,
    )


def _render_plan(plan: BackupPlan, *, plain: bool = False, effective_keep: int | None = None) -> None:
    mode = "Encrypted backup" if plan.settings.encrypted else "Backup"
    _print_rule(f"{mode} Plan: {plan.settings.name}", plain=plain)
    _print_paths("Destinations", plan.valid_destinations, "green", plain=plain) if plan.valid_destinations else _print_message("No usable destinations found.", "yellow")
    _print_paths("Folders", plan.source_folders, "cyan", plain=plain) if plan.source_folders else _print_message("No folder entries in whitelist.", "yellow")
    if plan.source_files:
        _print_paths("Files", plan.source_files, "magenta", plain=plain)
    if plan.missing_sources:
        _print_paths("Missing sources", plan.missing_sources, "yellow", plain=plain)
    if plan.settings.secrets_excluded:
        _print_message("Secrets excluded (set include_secrets = true to include)", "bold yellow")
    if plan.settings.encrypted:
        recipient_count = len(plan.settings.recipients or [])
        recipient_note = f"{recipient_count} inline recipient(s)"
        if plan.settings.recipients_file:
            recipient_note += f", recipients file: {plan.settings.recipients_file}"
        _print_message(f"Encryption: age ({recipient_note})", "bold blue")
    if effective_keep:
        _print_message(f"Retention: keep last {effective_keep} archive(s) per destination", "bold blue")
    _print_message(
        f"Would archive {len(plan.included_files):,} files ({byte_size(plan.total_file_size)}). "
        f"Skipped {plan.skipped_count:,}.",
        "bold",
    )


def _sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_manifest(settings: BackupSet, archive_path: str, plan: BackupPlan) -> str:
    manifest_path = archive_path + ".manifest.json"
    payload: dict = {
        "name": settings.name,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "encrypted": settings.encrypted,
        "archive": archive_path,
        "sha256": _sha256_file(archive_path),
        "file_count": len(plan.included_files),
        "skipped_count": plan.skipped_count,
        "total_file_size": plan.total_file_size,
        "secrets_excluded": settings.secrets_excluded,
    }
    # Encrypted-set manifests omit source/destination paths — those would advertise
    # exactly what's inside the encrypted blob to anyone reading the destination directory.
    if not settings.encrypted:
        payload["sources"] = settings.sources
        payload["destinations"] = settings.destinations
    Path(manifest_path).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return manifest_path


def _copy_to_extra_destinations(primary_archive_path: str, extra_destinations: list[str], *, restrict_perms: bool) -> None:
    related_paths = [primary_archive_path]
    manifest_path = primary_archive_path + ".manifest.json"
    if os.path.exists(manifest_path):
        related_paths.append(manifest_path)

    expected_sha = _sha256_file(primary_archive_path)

    for extra_path in extra_destinations:
        try:
            os.makedirs(extra_path, exist_ok=True)
            for path in related_paths:
                target = os.path.join(extra_path, os.path.basename(path))
                shutil.copy2(path, target)
                if path == primary_archive_path:
                    if _sha256_file(target) != expected_sha:
                        os.unlink(target)
                        raise OSError(f"sha256 mismatch after copy to {target}; copy deleted")
                    if restrict_perms:
                        os.chmod(target, 0o600)
            _print_message(f"Backup copied to {extra_path}", "green")
        except OSError as exc:
            _print_message(f"Error copying backup to {extra_path}: {exc}", "bold red")


def _age_recipient_args(settings: BackupSet) -> list[str]:
    args: list[str] = []
    for recipient in (settings.recipients or []):
        args.extend(["-r", recipient])
    if settings.recipients_file:
        args.extend(["-R", settings.recipients_file])
    return args


def _age_command(settings: BackupSet, source_path: str | None, output_path: str) -> list[str]:
    """Build an age command. If `source_path` is None, age reads stdin."""
    if shutil.which("age") is None:
        raise FileNotFoundError("age")
    command = ["age", *_age_recipient_args(settings), "-o", output_path]
    if source_path is not None:
        command.append(source_path)
    return command


def _preflight_age(settings: BackupSet) -> bool:
    """Verify the age recipients are valid by encrypting an empty payload.

    Catches malformed/typo recipient strings BEFORE any plaintext is produced.
    """
    try:
        with tempfile.TemporaryDirectory() as td:
            out_path = os.path.join(td, "preflight.age")
            cmd = _age_command(settings, source_path=None, output_path=out_path)
            subprocess.run(cmd, input=b"", check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or b"").decode("utf-8", errors="replace").strip()
        _print_message(
            f"[{settings.name}] age preflight failed: {stderr or exc}", "bold red"
        )
        return False
    except FileNotFoundError:
        _print_message("age is required for encrypted backups but was not found in PATH.", "bold red")
        return False


def _stream_tar_to_age(file_list_path: str, output_path: str, settings: BackupSet) -> None:
    """Stream `tar -czf -` into `age` over a pipe.

    Plaintext never touches the filesystem; it lives only in the kernel pipe
    buffer between the two processes. On either process failing, the partial
    output is unlinked and CalledProcessError is raised.
    """
    tar_cmd = ["tar", "-czf", "-", "-T", file_list_path]
    age_cmd = _age_command(settings, source_path=None, output_path=output_path)

    tar_proc = subprocess.Popen(tar_cmd, stdout=subprocess.PIPE)
    try:
        assert tar_proc.stdout is not None
        age_proc = subprocess.Popen(age_cmd, stdin=tar_proc.stdout)
        # Let tar receive SIGPIPE if age exits early.
        tar_proc.stdout.close()
        age_rc = age_proc.wait()
        tar_rc = tar_proc.wait()
    except Exception:
        tar_proc.kill()
        tar_proc.wait()
        raise

    if tar_rc != 0 or age_rc != 0:
        if os.path.exists(output_path):
            os.unlink(output_path)
        failed = tar_cmd if tar_rc != 0 else age_cmd
        rc = tar_rc if tar_rc != 0 else age_rc
        raise subprocess.CalledProcessError(rc, failed)


def _validate_encryption_settings(settings: BackupSet) -> bool:
    if not settings.encrypted:
        return True
    if not settings.recipients and not settings.recipients_file:
        _print_message(f"[{settings.name}] No age recipients configured.", "bold red")
        return False
    if settings.recipients_file and not os.path.isfile(settings.recipients_file):
        _print_message(f"[{settings.name}] Recipients file not found: {settings.recipients_file}", "bold red")
        return False
    if shutil.which("age") is None:
        _print_message("age is required for encrypted backups but was not found in PATH.", "bold red")
        return False
    return True


def create_backup(
    settings: BackupSet,
    *,
    verbose: bool = False,
    dry_run: bool = False,
    plain: bool = False,
    keep: int | None = None,
) -> int:
    """Create a new backup for a single set."""
    if not settings.destinations:
        _print_message(f"[{settings.name}] No backup destinations configured.", "bold red")
        print(CONFIG_HELP)
        return 1

    if not settings.sources:
        _print_message(f"[{settings.name}] No backup source folders configured.", "bold red")
        print(CONFIG_HELP)
        return 1

    if not _validate_encryption_settings(settings):
        return 1

    if settings.encrypted and not dry_run and not _preflight_age(settings):
        return 1

    plan = build_backup_plan(settings, create_destinations=not dry_run)
    if not plan.valid_destinations:
        _print_message(f"[{settings.name}] No usable backup destinations were found or could be created.", "bold red")
        print(CONFIG_HELP)
        return 1

    if plan.missing_sources:
        _print_message(f"[{settings.name}] Skipped paths that do not exist:", "bold yellow")
        for path in plan.missing_sources:
            _print_message(f"  - {path}", "yellow")

    if not plan.source_files and not plan.source_folders:
        _print_message(
            f"[{settings.name}] No valid whitelist entries were found. Configure ~/.config/rogkit/backup.txt or backup.set entries.",
            "bold red",
        )
        print(CONFIG_HELP)
        return 1

    effective_keep = keep if keep is not None else settings.keep

    if dry_run:
        _render_plan(plan, plain=plain, effective_keep=effective_keep)
        return 0

    start_time = perf_counter()
    current_date = datetime.today().strftime('%Y-%m-%d-%H-%M-%S')
    backup_filename = f'backup-{_slugify(settings.name)}-{current_date}.tar.gz'
    if settings.encrypted:
        backup_filename += ".age"

    primary_archive_path = plan.valid_destinations[0]
    backup_file_path = os.path.join(primary_archive_path, backup_filename)
    encrypted_temp_path = backup_file_path + ".tmp"

    _render_plan(plan, plain=plain, effective_keep=effective_keep)
    _print_message(f"Primary backup destination: {backup_file_path}", "bold blue")

    try:
        with tempfile.TemporaryDirectory() as work_dir:
            file_list_path = os.path.join(work_dir, "files.txt")
            with open(file_list_path, "w", encoding="utf-8") as handle:
                handle.write("\n".join(plan.included_files) + "\n")
            # Restrict the file list — it enumerates every source path being backed up.
            os.chmod(file_list_path, 0o600)

            if verbose:
                for path in plan.included_files:
                    _print_message(f"Added: {path}", "dim")

            elapsed_time = convert_seconds(perf_counter() - start_time)
            _print_message(
                f"[{settings.name}] Queued {len(plan.included_files):,} files for backup "
                f"({byte_size(plan.total_file_size)}). Skipped {plan.skipped_count:,}. "
                f"Elapsed time: {elapsed_time}.",
                "bold",
            )

            if settings.encrypted:
                # tar | age pipe — plaintext never lands on disk.
                _stream_tar_to_age(file_list_path, encrypted_temp_path, settings)
                os.replace(encrypted_temp_path, backup_file_path)
                os.chmod(backup_file_path, 0o600)
            else:
                plain_temp_path = backup_file_path + ".tmp"
                subprocess.run(
                    ["tar", "-czf", plain_temp_path, "-T", file_list_path],
                    check=True,
                )
                os.replace(plain_temp_path, backup_file_path)
    except subprocess.CalledProcessError as exc:
        _print_message(f"[{settings.name}] Error while creating archive: {exc}", "bold red")
        for stale in (encrypted_temp_path, backup_file_path + ".tmp"):
            if os.path.exists(stale):
                os.unlink(stale)
        return 1

    _print_message(f"[{settings.name}] Backup saved to {backup_file_path}", "green")
    manifest_path = _write_manifest(settings, backup_file_path, plan)
    _print_message(f"[{settings.name}] Manifest saved to {manifest_path}", "green")

    extra_destinations = plan.valid_destinations[1:]
    _copy_to_extra_destinations(backup_file_path, extra_destinations, restrict_perms=settings.encrypted)

    if effective_keep:
        prune_backups(settings, plan.valid_destinations, effective_keep, plain=plain)

    total_elapsed = convert_seconds(perf_counter() - start_time)
    archive_size = os.path.getsize(backup_file_path)
    _render_backup_summary(len(plan.included_files), plan.skipped_count, archive_size, total_elapsed, plain=plain)
    _print_message(f"[{settings.name}] Primary backup path: {backup_file_path}", "bold cyan")
    return 0


def _find_backup_archives(destination: str, settings: BackupSet) -> List[str]:
    """List archives in `destination` belonging to `settings` (not sidecar manifests)."""
    prefix = f"backup-{_slugify(settings.name)}-"
    suffix = ".tar.gz.age" if settings.encrypted else ".tar.gz"
    try:
        entries = os.listdir(destination)
    except OSError:
        return []
    return [
        os.path.join(destination, entry)
        for entry in entries
        if entry.startswith(prefix) and entry.endswith(suffix)
    ]


def prune_backups(settings: BackupSet, destinations: Iterable[str], keep: int, *, plain: bool = False) -> None:
    """Delete all but the `keep` most recent archives (by mtime) in each destination.

    Runs independently per destination since cloud/local copies of the same
    set can drift out of sync (e.g. a destination added after older runs).
    """
    for destination in destinations:
        archives = _find_backup_archives(destination, settings)
        if len(archives) <= keep:
            continue
        archives.sort(key=os.path.getmtime, reverse=True)
        for stale_archive in archives[keep:]:
            for path in (stale_archive, stale_archive + ".manifest.json"):
                try:
                    if os.path.exists(path):
                        os.unlink(path)
                except OSError as exc:
                    _print_message(f"[{settings.name}] Failed to prune {path}: {exc}", "bold red")
                    continue
            _print_message(f"[{settings.name}] Pruned {stale_archive}", "yellow")


def plan_backup(settings: BackupSet, *, plain: bool = False) -> int:
    """Print the backup plan for a single set."""
    plan = build_backup_plan(settings, create_destinations=False)
    _render_plan(plan, plain=plain, effective_keep=settings.keep)
    return 0


def list_backups(settings: BackupSet, *, plain: bool = False) -> int:
    """List existing backups from all destinations for a set."""
    if not settings.destinations:
        _print_message(f"[{settings.name}] No backup destinations configured.", "bold red")
        print(CONFIG_HELP)
        return 1

    _print_rule(f"Available Backups: {settings.name}", plain=plain)
    found_any = False

    for location in settings.destinations:
        if not os.path.isdir(location):
            _print_message(f"{location}: directory not found", "yellow")
            continue

        found_any = True
        try:
            backups = [
                entry for entry in os.listdir(location)
                if entry.startswith('backup-') and (entry.endswith('.tar.gz') or entry.endswith('.tar.gz.age'))
            ]
            if backups:
                rows: list[tuple[str, str]] = []
                for backup in sorted(backups):
                    backup_path = os.path.join(location, backup)
                    backup_size = os.path.getsize(backup_path)
                    rows.append((byte_size(backup_size), backup_path))
                _render_backup_listing(location, rows, plain=plain)
            else:
                _print_message(f"No backups found in {location}.", "yellow")
        except OSError as exc:
            _print_message(f"Error listing backups in {location}: {exc}", "bold red")

    if not found_any:
        _print_message("No valid backup destinations found.", "bold red")
        print(CONFIG_HELP)
        return 1

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description='Backup, plan, and list backups')
    parser.add_argument('-b', '--backup', action='store_true', help='Create a new backup')
    parser.add_argument('-l', '--list', action='store_true', help='List existing backups')
    parser.add_argument('--plan', action='store_true', help='Show what would be backed up without creating archives')
    parser.add_argument('--dry-run', action='store_true', help='Alias for --plan when creating backups')
    parser.add_argument('--encrypted', action='store_true', help='Only select encrypted backup sets')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    parser.add_argument('-p', '--plain', action='store_true', help='Plain text output')
    parser.add_argument(
        '--set',
        dest='sets',
        action='append',
        help='Only run/list the named backup set (repeatable)',
    )
    parser.add_argument(
        '--list-sets',
        action='store_true',
        help='Show configured backup set names and exit',
    )
    parser.add_argument(
        '--keep',
        type=int,
        metavar='N',
        help=(
            'After a successful backup, delete all but the N most recent archives '
            '(per destination). Overrides each set\'s configured keep=; only applies with -b/--backup.'
        ),
    )
    args = parser.parse_args()

    if args.keep is not None and args.keep < 1:
        parser.error('--keep must be a positive integer')

    if args.dry_run and not args.backup:
        args.plan = True

    if not any((args.backup, args.list, args.plan, args.list_sets)):
        parser.print_help()
        return 0

    backup_sets = load_backup_settings()
    if not backup_sets:
        _print_message("No backup configuration found.", "bold red")
        print(CONFIG_HELP)
        return 1

    if args.list_sets:
        _print_rule("Configured Backup Sets", plain=args.plain)
        for idx, setting in enumerate(backup_sets, start=1):
            _print_message(f"{idx}. {setting.name} ({len(setting.sources)} paths -> {len(setting.destinations)} destinations)")
        return 0

    selected_sets: Sequence[BackupSet] = backup_sets
    if args.sets:
        requested = {name.lower() for name in args.sets}
        filtered = [item for item in backup_sets if item.name.lower() in requested]
        missing = requested - {item.name.lower() for item in filtered}
        if missing:
            _print_message(f"Unknown backup set(s): {', '.join(sorted(missing))}", "bold red")
        if not filtered:
            return 1
        selected_sets = filtered

    if args.encrypted:
        selected_sets = [setting for setting in selected_sets if setting.encrypted]
        if not selected_sets:
            _print_message("No encrypted backup sets selected.", "bold red")
            return 1

    exit_code = 0

    if args.plan:
        for setting in selected_sets:
            plan_code = plan_backup(setting, plain=args.plain)
            exit_code = plan_code if plan_code else exit_code
    if args.list:
        for setting in selected_sets:
            list_code = list_backups(setting, plain=args.plain)
            exit_code = list_code if list_code else exit_code
    if args.backup:
        for setting in selected_sets:
            backup_code = create_backup(
                setting, verbose=args.verbose, dry_run=args.dry_run, plain=args.plain, keep=args.keep
            )
            exit_code = backup_code if backup_code else exit_code

    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
    
