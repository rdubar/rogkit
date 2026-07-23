"""Tests for backup.py."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tarfile
import time
from pathlib import Path

import pytest

from rogkit_package.bin import backup


def test_build_backup_sets_from_config_excludes_secrets_for_plain_sets(tmp_path):
    config = {
        "secret_patterns": [".env", "secrets.toml"],
        "file_excludes": ["*.tmp"],
        "folder_excludes": ["cache"],
        "set": [
            {
                "name": "plain",
                "paths": [str(tmp_path / "src")],
                "destinations": [str(tmp_path / "dest")],
            }
        ],
        "encrypted_set": [
            {
                "name": "secrets",
                "paths": [str(tmp_path / "private")],
                "destinations": [str(tmp_path / "encrypted")],
                "recipients": ["age1example"],
            }
        ],
    }

    plain, encrypted = backup._build_backup_sets_from_config(config)

    assert plain.name == "plain"
    assert plain.encrypted is False
    assert plain.secrets_excluded is True
    assert ".env" in plain.secret_patterns
    assert "secrets.toml" in plain.secret_patterns
    # secret_patterns live in their own basename-only field, not file_excludes
    assert ".env" not in plain.file_excludes
    assert encrypted.name == "secrets"
    assert encrypted.encrypted is True
    assert encrypted.secrets_excluded is False
    assert encrypted.secret_patterns == []
    assert encrypted.recipients == ["age1example"]


def test_build_backup_plan_filters_files_and_folders(tmp_path):
    src = tmp_path / "src"
    dest = tmp_path / "dest"
    src.mkdir()
    dest.mkdir()
    (src / "keep.txt").write_text("keep", encoding="utf-8")
    (src / ".env").write_text("secret", encoding="utf-8")
    cache = src / "cache"
    cache.mkdir()
    (cache / "ignored.txt").write_text("ignored", encoding="utf-8")

    settings = backup.BackupSet(
        name="test",
        sources=[str(src), str(tmp_path / "missing")],
        destinations=[str(dest)],
        file_excludes=[".env"],
        folder_excludes=["cache"],
    )

    plan = backup.build_backup_plan(settings)

    assert plan.valid_destinations == [str(dest)]
    assert plan.missing_sources == [str(tmp_path / "missing")]
    assert plan.included_files == [str(src / "keep.txt")]
    assert plan.skipped_count == 2


def test_create_backup_writes_tar_and_manifest(tmp_path):
    src = tmp_path / "src"
    dest = tmp_path / "dest"
    src.mkdir()
    dest.mkdir()
    (src / "keep.txt").write_text("keep", encoding="utf-8")

    settings = backup.BackupSet(
        name="test",
        sources=[str(src)],
        destinations=[str(dest)],
        file_excludes=[],
        folder_excludes=[],
    )

    assert backup.create_backup(settings) == 0

    archives = list(dest.glob("backup-test-*.tar.gz"))
    assert len(archives) == 1
    with tarfile.open(archives[0], "r:gz") as archive:
        assert any(member.name.endswith("keep.txt") for member in archive.getmembers())

    manifest = Path(str(archives[0]) + ".manifest.json")
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload["name"] == "test"
    assert payload["encrypted"] is False
    assert payload["file_count"] == 1
    assert payload["sha256"]


def test_plan_backup_plain_outputs_no_box_drawing(tmp_path, capsys):
    src = tmp_path / "src"
    dest = tmp_path / "dest"
    src.mkdir()
    dest.mkdir()
    (src / "keep.txt").write_text("keep", encoding="utf-8")

    settings = backup.BackupSet(
        name="test",
        sources=[str(src)],
        destinations=[str(dest)],
        file_excludes=[],
        folder_excludes=[],
    )

    assert backup.plan_backup(settings, plain=True) == 0
    out = capsys.readouterr().out
    assert str(src) in out
    assert "Would archive 1 files" in out
    assert "─" not in out  # no rich box-drawing chars leak through


def test_validate_encryption_requires_recipient_or_file(monkeypatch, tmp_path):
    monkeypatch.setattr(backup.shutil, "which", lambda name: "/opt/homebrew/bin/age")
    settings = backup.BackupSet(
        name="secrets",
        sources=[str(tmp_path)],
        destinations=[str(tmp_path)],
        file_excludes=[],
        folder_excludes=[],
        encrypted=True,
    )

    assert backup._validate_encryption_settings(settings) is False


def test_age_command_uses_inline_and_file_recipients(monkeypatch, tmp_path):
    recipients = tmp_path / "recipients.txt"
    recipients.write_text("age1example\n", encoding="utf-8")
    monkeypatch.setattr(backup.shutil, "which", lambda name: "/opt/homebrew/bin/age")
    settings = backup.BackupSet(
        name="secrets",
        sources=[str(tmp_path)],
        destinations=[str(tmp_path)],
        file_excludes=[],
        folder_excludes=[],
        encrypted=True,
        recipients=["age1inline"],
        recipients_file=str(recipients),
    )

    command = backup._age_command(settings, "plain.tar.gz", "plain.tar.gz.age")

    assert command == [
        "age",
        "-r",
        "age1inline",
        "-R",
        str(recipients),
        "-o",
        "plain.tar.gz.age",
        "plain.tar.gz",
    ]


def test_secret_patterns_match_basename_only(tmp_path):
    """`.env` in secret_patterns must exclude files named .env, NOT sibling
    paths that happen to contain ".env" as a substring."""
    src = tmp_path / "src"
    dest = tmp_path / "dest"
    src.mkdir()
    dest.mkdir()
    (src / ".env").write_text("real secret", encoding="utf-8")
    (src / ".envrc").write_text("direnv config — not a secret", encoding="utf-8")
    (src / "file.env.example").write_text("template", encoding="utf-8")
    nested_env_dir = src / "myenv"
    nested_env_dir.mkdir()
    (nested_env_dir / "data.txt").write_text("not a secret", encoding="utf-8")

    settings = backup.BackupSet(
        name="test",
        sources=[str(src)],
        destinations=[str(dest)],
        file_excludes=[],
        folder_excludes=[],
        secret_patterns=[".env"],
        secrets_excluded=True,
    )

    plan = backup.build_backup_plan(settings)
    included = {Path(p).name for p in plan.included_files}

    assert ".env" not in included          # excluded
    assert ".envrc" in included            # kept — different basename
    assert "file.env.example" in included  # kept — substring of .env shouldn't trigger
    assert "data.txt" in included          # kept — parent dir contains ".env" but file doesn't


def test_encrypted_manifest_redacts_source_paths(tmp_path):
    if shutil.which("age") is None or shutil.which("age-keygen") is None:
        pytest.skip("age tools are not installed")

    identity = tmp_path / "identity.txt"
    keygen = subprocess.run(
        ["age-keygen", "-o", str(identity)],
        check=True,
        capture_output=True,
        text=True,
    )
    public_key = (keygen.stdout + keygen.stderr).strip().split("Public key: ", 1)[1]

    src = tmp_path / "private"
    dest = tmp_path / "dest"
    src.mkdir()
    dest.mkdir()
    (src / "secret.txt").write_text("not a real secret", encoding="utf-8")

    settings = backup.BackupSet(
        name="secrets",
        sources=[str(src)],
        destinations=[str(dest)],
        file_excludes=[],
        folder_excludes=[],
        encrypted=True,
        recipients=[public_key],
    )

    assert backup.create_backup(settings) == 0

    manifest_files = list(dest.glob("backup-secrets-*.tar.gz.age.manifest.json"))
    assert len(manifest_files) == 1
    payload = json.loads(manifest_files[0].read_text(encoding="utf-8"))

    assert payload["encrypted"] is True
    assert "sha256" in payload
    assert "file_count" in payload
    # Source/destination paths must NOT appear in the side-by-side manifest
    # of an encrypted archive — they leak what's inside.
    assert "sources" not in payload
    assert "destinations" not in payload


def _touch_with_mtime(path: Path, contents: bytes, mtime: float) -> None:
    path.write_bytes(contents)
    os.utime(path, (mtime, mtime))


def test_build_backup_sets_from_config_parses_keep(tmp_path):
    config = {
        "keep": 10,
        "set": [
            {
                "name": "explicit",
                "paths": [str(tmp_path)],
                "destinations": [str(tmp_path)],
                "keep": 3,
            },
            {
                "name": "inherited",
                "paths": [str(tmp_path)],
                "destinations": [str(tmp_path)],
            },
        ],
    }

    sets = backup._build_backup_sets_from_config(config)
    by_name = {item.name: item for item in sets}

    assert by_name["explicit"].keep == 3
    assert by_name["inherited"].keep == 10  # falls back to [backup].keep


def test_prune_backups_keeps_only_the_n_most_recent(tmp_path):
    dest = tmp_path / "dest"
    dest.mkdir()
    now = time.time()

    names = [
        "backup-test-2026-01-01-00-00-00.tar.gz",
        "backup-test-2026-02-01-00-00-00.tar.gz",
        "backup-test-2026-03-01-00-00-00.tar.gz",
    ]
    for offset, name in enumerate(names):
        _touch_with_mtime(dest / name, b"data", now - (len(names) - offset) * 60)
        (dest / f"{name}.manifest.json").write_text("{}", encoding="utf-8")

    settings = backup.BackupSet(
        name="test",
        sources=[],
        destinations=[str(dest)],
        file_excludes=[],
        folder_excludes=[],
    )

    backup.prune_backups(settings, [str(dest)], keep=1)

    remaining = sorted(p.name for p in dest.glob("backup-test-*.tar.gz"))
    assert remaining == [names[-1]]
    assert not (dest / f"{names[0]}.manifest.json").exists()
    assert not (dest / f"{names[1]}.manifest.json").exists()
    assert (dest / f"{names[-1]}.manifest.json").exists()


def test_create_backup_prunes_old_archives_with_keep_override(tmp_path):
    src = tmp_path / "src"
    dest = tmp_path / "dest"
    src.mkdir()
    dest.mkdir()
    (src / "keep.txt").write_text("keep", encoding="utf-8")

    now = time.time()
    stale_names = [
        "backup-test-2026-01-01-00-00-00.tar.gz",
        "backup-test-2026-02-01-00-00-00.tar.gz",
    ]
    for offset, name in enumerate(stale_names):
        _touch_with_mtime(dest / name, b"stale", now - (len(stale_names) - offset) * 60)
        (dest / f"{name}.manifest.json").write_text("{}", encoding="utf-8")

    settings = backup.BackupSet(
        name="test",
        sources=[str(src)],
        destinations=[str(dest)],
        file_excludes=[],
        folder_excludes=[],
    )

    assert backup.create_backup(settings, keep=1) == 0

    archives = sorted(dest.glob("backup-test-*.tar.gz"))
    assert len(archives) == 1
    assert archives[0].name not in stale_names
    assert len(list(dest.glob("backup-test-*.tar.gz.manifest.json"))) == 1


def test_create_backup_uses_configured_keep_when_no_override(tmp_path):
    src = tmp_path / "src"
    dest = tmp_path / "dest"
    src.mkdir()
    dest.mkdir()
    (src / "keep.txt").write_text("keep", encoding="utf-8")

    stale = dest / "backup-test-2020-01-01-00-00-00.tar.gz"
    _touch_with_mtime(stale, b"stale", time.time() - 3600)
    (dest / f"{stale.name}.manifest.json").write_text("{}", encoding="utf-8")

    settings = backup.BackupSet(
        name="test",
        sources=[str(src)],
        destinations=[str(dest)],
        file_excludes=[],
        folder_excludes=[],
        keep=1,
    )

    assert backup.create_backup(settings) == 0

    archives = sorted(dest.glob("backup-test-*.tar.gz"))
    assert len(archives) == 1
    assert archives[0].name != stale.name


def test_create_backup_dry_run_does_not_prune(tmp_path):
    src = tmp_path / "src"
    dest = tmp_path / "dest"
    src.mkdir()
    dest.mkdir()
    (src / "keep.txt").write_text("keep", encoding="utf-8")

    stale = dest / "backup-test-2020-01-01-00-00-00.tar.gz"
    _touch_with_mtime(stale, b"stale", time.time() - 3600)
    (dest / f"{stale.name}.manifest.json").write_text("{}", encoding="utf-8")

    settings = backup.BackupSet(
        name="test",
        sources=[str(src)],
        destinations=[str(dest)],
        file_excludes=[],
        folder_excludes=[],
        keep=1,
    )

    assert backup.create_backup(settings, dry_run=True, keep=1) == 0

    assert stale.exists()
    # Dry-run writes nothing, so the stale archive is the only one present.
    assert len(list(dest.glob("backup-test-*.tar.gz"))) == 1


def test_create_encrypted_backup_writes_age_archive_and_manifest(tmp_path):
    if shutil.which("age") is None or shutil.which("age-keygen") is None:
        pytest.skip("age tools are not installed")

    identity = tmp_path / "identity.txt"
    keygen = subprocess.run(
        ["age-keygen", "-o", str(identity)],
        check=True,
        capture_output=True,
        text=True,
    )
    keygen_output = keygen.stdout + keygen.stderr
    public_key = keygen_output.strip().split("Public key: ", 1)[1]

    src = tmp_path / "src"
    dest = tmp_path / "dest"
    src.mkdir()
    dest.mkdir()
    (src / "secret.txt").write_text("not a real secret", encoding="utf-8")
    settings = backup.BackupSet(
        name="secrets",
        sources=[str(src)],
        destinations=[str(dest)],
        file_excludes=[],
        folder_excludes=[],
        encrypted=True,
        recipients=[public_key],
    )

    assert backup.create_backup(settings) == 0

    archives = list(dest.glob("backup-secrets-*.tar.gz.age"))
    assert len(archives) == 1
    manifest = Path(str(archives[0]) + ".manifest.json")
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload["encrypted"] is True
    assert payload["file_count"] == 1
