"""Tests for envr.py - environment variable viewer."""

import sys

from rogkit_package.bin.envr import list_env, main, render_env


def test_list_env_returns_sorted_pairs(monkeypatch):
    monkeypatch.setattr(
        "os.environ",
        {"ZETA": "3", "ALPHA": "1", "BETA": "2"},
    )
    assert list_env() == [("ALPHA", "1"), ("BETA", "2"), ("ZETA", "3")]


def test_list_env_filters_key(monkeypatch):
    monkeypatch.setattr(
        "os.environ",
        {"PATH": "/bin", "PYTHONPATH": "/tmp", "HOME": "/Users/test"},
    )
    assert list_env(pattern="path") == [("PATH", "/bin"), ("PYTHONPATH", "/tmp")]


def test_list_env_filters_value(monkeypatch):
    monkeypatch.setattr(
        "os.environ",
        {"PATH": "/bin", "EDITOR": "nvim", "SHELL": "/bin/zsh"},
    )
    assert list_env(val_pattern="nvim") == [("EDITOR", "nvim")]


def test_render_env_plain_outputs_rows(capsys):
    render_env([("PATH", "/bin"), ("SHELL", "/bin/zsh")], plain=True)
    out = capsys.readouterr().out
    assert "PATH" in out
    assert "/bin/zsh" in out


def _run_main(argv: list[str]) -> int:
    old = sys.argv
    sys.argv = ["env"] + argv
    try:
        from rogkit_package.bin.envr import main as _main

        return _main()
    finally:
        sys.argv = old


def test_main_count(monkeypatch, capsys):
    monkeypatch.setattr(
        "os.environ",
        {"PATH": "/bin", "SHELL": "/bin/zsh"},
    )
    rc = _run_main(["--count"])
    assert rc == 0
    assert capsys.readouterr().out.strip() == "2"


def test_main_key_filter(monkeypatch, capsys):
    monkeypatch.setattr(
        "os.environ",
        {"PATH": "/bin", "SHELL": "/bin/zsh"},
    )
    rc = _run_main(["PATH", "--plain"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "PATH" in out
    assert "SHELL" not in out
