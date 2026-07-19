from __future__ import annotations

from pathlib import Path

from rogkit_package.bin import vido


def test_update_yt_dlp_runs_uv_lock_then_sync(monkeypatch):
    calls: list[list[str]] = []
    reports = iter(
        [
            ("2026.2.21", "2026.6.1", True),
            ("2026.6.1", "2026.6.1", False),
        ]
    )

    monkeypatch.setattr(vido, "report_yt_dlp_versions", lambda: next(reports))
    monkeypatch.setattr(vido, "run_uv_command", lambda args, cwd=None: calls.append(args) or 0)

    assert vido.update_yt_dlp() == 0
    assert calls == [
        ["lock", "--upgrade-package", "yt-dlp"],
        ["sync", "--all-extras", "--reinstall-package", "yt-dlp"],
    ]


def test_update_yt_dlp_stops_when_lock_update_fails(monkeypatch):
    calls: list[list[str]] = []

    monkeypatch.setattr(vido, "report_yt_dlp_versions", lambda: ("2026.2.21", "2026.6.1", True))
    monkeypatch.setattr(vido, "run_uv_command", lambda args, cwd=None: calls.append(args) or 23)

    assert vido.update_yt_dlp() == 23
    assert calls == [["lock", "--upgrade-package", "yt-dlp"]]


def test_check_update_uses_uv_dry_run(monkeypatch):
    calls: list[list[str]] = []

    monkeypatch.setattr(vido, "report_yt_dlp_versions", lambda: ("2026.2.21", "2026.6.1", True))
    monkeypatch.setattr(vido, "run_uv_command", lambda args, cwd=None: calls.append(args) or 0)

    assert vido.update_yt_dlp(check_only=True) == 0
    assert calls == [["lock", "--upgrade-package", "yt-dlp", "--dry-run"]]


def test_main_update_exits_before_config_loading(monkeypatch, tmp_path):
    config_path = tmp_path / "missing.toml"
    calls: list[bool] = []

    monkeypatch.setattr(vido, "update_yt_dlp", lambda *, check_only=False: calls.append(check_only) or 0)

    assert vido.main(["--update", "--config", str(config_path)]) == 0
    assert calls == [False]


def test_run_uv_command_reports_missing_uv(monkeypatch):
    monkeypatch.setattr(vido.shutil, "which", lambda _name: None)

    assert vido.run_uv_command(["lock"], cwd=Path("/tmp")) == 1


def test_plain_flag_suppresses_rich_styling(monkeypatch, capsys):
    """--plain sets the module-level flag so _print_message falls back to plain print."""
    calls: list[bool] = []
    monkeypatch.setattr(vido, "update_yt_dlp", lambda *, check_only=False: calls.append(check_only) or 0)

    assert vido.main(["--update", "--plain"]) == 0
    assert vido._PLAIN_OUTPUT is True

    vido._print_message("plain output check", style="green")
    out = capsys.readouterr().out
    assert out.strip() == "plain output check"

    # Reset the module flag so other tests aren't affected by ordering.
    vido._PLAIN_OUTPUT = False
