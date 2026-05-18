"""Tests for envr.py - environment variable viewer."""

import sys

from rogkit_package.bin.envr import apply_mask, list_env, render_env


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


def test_apply_mask_hides_secrets():
    items = [
        ("PATH", "/bin"),
        ("OPENAI_API_KEY", "sk-real-secret-value"),
        ("HOME", "/Users/test"),
    ]
    masked = apply_mask(items, show=False)
    assert ("PATH", "/bin") in masked
    assert ("HOME", "/Users/test") in masked
    # secret value replaced
    masked_dict = dict(masked)
    assert "sk-real-secret-value" not in masked_dict["OPENAI_API_KEY"]
    assert masked_dict["OPENAI_API_KEY"] == "********"


def test_apply_mask_show_reveals_everything():
    items = [("OPENAI_API_KEY", "sk-real")]
    assert apply_mask(items, show=True) == items


def test_main_masks_secrets_by_default(monkeypatch, capsys):
    monkeypatch.setattr(
        "os.environ",
        {"PATH": "/bin", "OPENAI_API_KEY": "sk-real-secret"},
    )
    rc = _run_main(["--plain"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "sk-real-secret" not in out
    assert "********" in out
    assert "/bin" in out  # non-secret unchanged


def test_main_show_flag_reveals(monkeypatch, capsys):
    monkeypatch.setattr(
        "os.environ",
        {"OPENAI_API_KEY": "sk-real-secret"},
    )
    rc = _run_main(["--show", "--plain"])
    assert rc == 0
    assert "sk-real-secret" in capsys.readouterr().out


def test_main_keys_only(monkeypatch, capsys):
    monkeypatch.setattr(
        "os.environ",
        {"OPENAI_API_KEY": "sk-real", "PATH": "/bin"},
    )
    rc = _run_main(["--keys-only"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "OPENAI_API_KEY" in out
    assert "PATH" in out
    assert "sk-real" not in out
    assert "/bin" not in out


def test_main_val_filter_uses_real_values(monkeypatch, capsys):
    """--val should match against real values even when display is masked."""
    monkeypatch.setattr(
        "os.environ",
        {"OPENAI_API_KEY": "sk-abc123", "PATH": "/bin"},
    )
    rc = _run_main(["--val", "abc123", "--plain"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "OPENAI_API_KEY" in out
    assert "PATH" not in out
    # value still masked in output
    assert "abc123" not in out
