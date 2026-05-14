from __future__ import annotations

import hashlib
import json
from pathlib import Path

from rogkit_package.bin import doctor


def test_shell_startup_candidates_zsh(monkeypatch, tmp_path):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    paths = doctor._shell_startup_candidates("/bin/zsh")

    assert paths == [tmp_path / ".zshrc", tmp_path / ".zprofile"]


def test_profile_sources_aliases_accepts_common_patterns(tmp_path):
    profile = tmp_path / ".zshrc"
    aliases_path = tmp_path / "dev" / "rogkit" / "aliases"
    profile.write_text('source "$ROGKIT/aliases"\n', encoding="utf-8")

    assert doctor._profile_sources_aliases(profile, aliases_path=aliases_path) is True


def test_mask_value():
    assert doctor._mask_value("") == "<empty>"
    assert doctor._mask_value(None) == "<empty>"
    assert doctor._mask_value("secret") == "<set>"


def test_run_checks_uses_all_checkers(monkeypatch):
    expected = [
        doctor.CheckResult("config", "ok", "config ok"),
        doctor.CheckResult("shell", "ok", "shell ok"),
        doctor.CheckResult("binaries", "ok", "binaries ok"),
        doctor.CheckResult("backup", "ok", "backup ok"),
        doctor.CheckResult("media", "warn", "media warn"),
    ]
    monkeypatch.setattr(doctor, "_check_config", lambda: expected[0])
    monkeypatch.setattr(doctor, "_check_shell_setup", lambda: expected[1])
    monkeypatch.setattr(doctor, "_check_binaries", lambda: expected[2])
    monkeypatch.setattr(doctor, "_check_backup_health", lambda: expected[3])
    monkeypatch.setattr(doctor, "_check_media", lambda: expected[4])

    assert doctor.run_checks() == expected


def test_main_json_output_returns_failure_when_any_check_fails(monkeypatch, capsys):
    results = [
        doctor.CheckResult("config", "ok", "config ok"),
        doctor.CheckResult("media", "fail", "media failed", ["ssh unreachable"]),
    ]
    monkeypatch.setattr(doctor, "run_checks", lambda: results)
    monkeypatch.setattr(
        doctor.argparse.ArgumentParser,
        "parse_args",
        lambda _self: doctor.argparse.Namespace(json=True),
    )

    rc = doctor.main()

    payload = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert payload[1]["name"] == "media"
    assert payload[1]["details"] == ["ssh unreachable"]


def test_check_shell_setup_reports_sourced_profile(monkeypatch, tmp_path):
    zshrc = tmp_path / ".zshrc"
    zprofile = tmp_path / ".zprofile"
    zshrc.write_text("source ~/dev/rogkit/aliases\n", encoding="utf-8")
    zprofile.write_text("# empty\n", encoding="utf-8")

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("SHELL", "/bin/zsh")

    result = doctor._check_shell_setup()

    assert result.status == "ok"
    assert any(str(zshrc) in detail for detail in result.details)


def test_check_config_missing_includes_setup_hint(monkeypatch, tmp_path):
    config_path = tmp_path / "config.toml"
    secrets_path = tmp_path / "secrets.toml"
    monkeypatch.setattr(doctor, "get_rogkit_toml_path", lambda: config_path)
    monkeypatch.setattr(doctor, "get_rogkit_secrets_path", lambda: secrets_path)

    result = doctor._check_config()

    assert result.status == "fail"
    assert any("setup --apply" in detail for detail in result.details)


def _write_backup_archive(dest: Path, filename: str, content: bytes) -> Path:
    archive = dest / filename
    archive.write_bytes(content)
    manifest = Path(str(archive) + ".manifest.json")
    manifest.write_text(
        json.dumps(
            {
                "name": "test",
                "encrypted": filename.endswith(".age"),
                "sha256": hashlib.sha256(content).hexdigest(),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return archive


def test_check_backup_health_reports_ok_for_verified_archives(
    monkeypatch, tmp_path
):
    home = tmp_path
    monkeypatch.setattr(Path, "home", lambda: home)
    monkeypatch.setattr(
        doctor.shutil,
        "which",
        lambda name: "/opt/homebrew/bin/age" if name == "age" else f"/usr/bin/{name}",
    )

    plain_dest = tmp_path / "archive" / "backups"
    encrypted_dest = plain_dest / "encrypted"
    plain_dest.mkdir(parents=True)
    encrypted_dest.mkdir(parents=True)

    plain_archive = _write_backup_archive(
        plain_dest,
        "backup-neo-2026-05-14-20-48-00.tar.gz",
        b"plain-archive",
    )
    encrypted_archive = _write_backup_archive(
        encrypted_dest,
        "backup-neo-secrets-2026-05-14-20-49-03.tar.gz.age",
        b"encrypted-archive",
    )

    recipients = tmp_path / ".config" / "rogkit" / "backup-recipients.txt"
    identity = tmp_path / ".config" / "age" / "keys.txt"
    recipients.parent.mkdir(parents=True)
    identity.parent.mkdir(parents=True)
    recipients.write_text("age1example\n", encoding="utf-8")
    identity.write_text("AGE-SECRET-KEY-1...", encoding="utf-8")

    plain = doctor.backup_cmd.BackupSet(
        name="neo",
        sources=[str(tmp_path / "dev")],
        destinations=[str(plain_dest)],
        file_excludes=[],
        folder_excludes=[],
    )
    encrypted = doctor.backup_cmd.BackupSet(
        name="neo-secrets",
        sources=[str(tmp_path / "private")],
        destinations=[str(encrypted_dest)],
        file_excludes=[],
        folder_excludes=[],
        encrypted=True,
        recipients=["age1example"],
        recipients_file=str(recipients),
    )
    monkeypatch.setattr(
        doctor.backup_cmd,
        "load_backup_settings",
        lambda: [plain, encrypted],
    )

    result = doctor._check_backup_health()

    assert result.status == "ok"
    assert str(plain_archive) in "\n".join(result.details)
    assert str(encrypted_archive) in "\n".join(result.details)


def test_check_backup_health_fails_when_checksum_does_not_match(monkeypatch, tmp_path):
    home = tmp_path
    monkeypatch.setattr(Path, "home", lambda: home)
    monkeypatch.setattr(
        doctor.shutil,
        "which",
        lambda name: "/opt/homebrew/bin/age" if name == "age" else f"/usr/bin/{name}",
    )

    dest = tmp_path / "archive" / "backups"
    dest.mkdir(parents=True)
    _write_backup_archive(dest, "backup-neo-2026-05-14-20-48-00.tar.gz", b"plain-archive")
    (dest / "backup-neo-2026-05-14-20-48-00.tar.gz.manifest.json").write_text(
        json.dumps(
            {
                "name": "test",
                "encrypted": False,
                "sha256": "deadbeef",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    plain = doctor.backup_cmd.BackupSet(
        name="neo",
        sources=[str(tmp_path / "dev")],
        destinations=[str(dest)],
        file_excludes=[],
        folder_excludes=[],
    )
    monkeypatch.setattr(doctor.backup_cmd, "load_backup_settings", lambda: [plain])

    result = doctor._check_backup_health()

    assert result.status == "fail"
    assert "checksum mismatch" in "\n".join(result.details)
