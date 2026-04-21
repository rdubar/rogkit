from __future__ import annotations

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
        doctor.CheckResult("media", "warn", "media warn"),
    ]
    monkeypatch.setattr(doctor, "_check_config", lambda: expected[0])
    monkeypatch.setattr(doctor, "_check_shell_setup", lambda: expected[1])
    monkeypatch.setattr(doctor, "_check_binaries", lambda: expected[2])
    monkeypatch.setattr(doctor, "_check_media", lambda: expected[3])

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
