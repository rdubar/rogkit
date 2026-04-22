from __future__ import annotations

from rogkit_package.bin import rogkit


def test_main_prints_version(capsys):
    rc = rogkit.main(["--version"])

    assert rc == 0
    assert "rogkit 0.1.0" in capsys.readouterr().out


def test_main_prints_credits(capsys):
    rc = rogkit.main(["--credits"])

    output = capsys.readouterr().out
    assert rc == 0
    assert "rogkit v0.1.0" in output
    assert "Author: Roger D" in output


def test_main_without_args_prints_command_overview(capsys):
    rc = rogkit.main([])

    output = capsys.readouterr().out
    assert rc == 0
    assert "Personal utility toolkit with 85+ commands." in output
    assert "Common commands:" in output
    assert "doctor  setup  update" in output
    assert "Use `rogkit --help` for CLI help" in output


def test_main_dispatches_doctor(monkeypatch):
    calls: list[list[str]] = []
    monkeypatch.setattr(rogkit.doctor_cmd, "main", lambda argv=None: calls.append(argv or []) or 0)

    rc = rogkit.main(["doctor", "--json"])

    assert rc == 0
    assert calls == [["--json"]]


def test_main_dispatches_setup(monkeypatch):
    calls: list[list[str]] = []
    monkeypatch.setattr(rogkit.setup_cmd, "main", lambda argv=None: calls.append(argv or []) or 0)

    rc = rogkit.main(["setup", "--apply"])

    assert rc == 0
    assert calls == [["--apply"]]


def test_main_dispatches_update(monkeypatch):
    calls: list[list[str]] = []
    monkeypatch.setattr(rogkit, "_run_update", lambda argv=None: calls.append(argv or []) or 0)

    rc = rogkit.main(["update", "--full", "-y"])

    assert rc == 0
    assert calls == [["--full", "-y"]]


def test_main_dispatches_update_flag_with_extra_args(monkeypatch):
    calls: list[list[str]] = []
    monkeypatch.setattr(rogkit, "_run_update", lambda argv=None: calls.append(argv or []) or 0)

    rc = rogkit.main(["--update", "--full", "-y"])

    assert rc == 0
    assert calls == [["--full", "-y"]]


def test_help_topic_dispatches_to_doctor_help(monkeypatch):
    calls: list[list[str]] = []
    monkeypatch.setattr(rogkit.doctor_cmd, "parse_args", lambda argv=None: calls.append(argv or []))

    rc = rogkit.main(["help", "doctor"])

    assert rc == 0
    assert calls == [["--help"]]
