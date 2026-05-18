"""Tests for enver.py - .env-file key auditor."""

from __future__ import annotations

import sys

from rogkit_package.bin._envsec import classify_value
from rogkit_package.bin.enver import (
    _strip_quotes,
    discover_env_files,
    find_example_for,
    parse_env_file,
)


def test_classify_empty():
    assert classify_value("") == "empty"


def test_classify_nullish():
    assert classify_value("null") == "placeholder"
    assert classify_value("None") == "placeholder"
    assert classify_value("undefined") == "placeholder"


def test_classify_angle_bracket_placeholder():
    assert classify_value("<your-key-here>") == "placeholder"
    assert classify_value("<changeme>") == "placeholder"


def test_classify_word_placeholders():
    assert classify_value("xxx") == "placeholder"
    assert classify_value("changeme") == "placeholder"
    assert classify_value("your-api-key") == "placeholder"
    assert classify_value("TODO") == "placeholder"
    assert classify_value("placeholder") == "placeholder"


def test_classify_real_values():
    assert classify_value("postgres://user:pw@host/db") == "set"
    assert classify_value("sk-abc123def456") == "set"
    assert classify_value("true") == "set"
    assert classify_value("8080") == "set"


def test_strip_quotes():
    assert _strip_quotes('"hello"') == "hello"
    assert _strip_quotes("'hello'") == "hello"
    assert _strip_quotes("hello") == "hello"
    assert _strip_quotes("  hello  ") == "hello"
    assert _strip_quotes("hello # comment") == "hello"


def test_parse_env_file_basic(tmp_path):
    env = tmp_path / ".env"
    env.write_text(
        "# a comment\n"
        "\n"
        "DATABASE_URL=postgres://localhost/db\n"
        "STRIPE_KEY=<your-stripe-key>\n"
        "DEBUG=\n"
        'NAME="quoted value"\n'
        "export SECRET=real\n",
        encoding="utf-8",
    )
    keys = parse_env_file(env)
    by_name = {k.key: k for k in keys}
    assert by_name["DATABASE_URL"].status == "set"
    assert by_name["STRIPE_KEY"].status == "placeholder"
    assert by_name["DEBUG"].status == "empty"
    assert by_name["NAME"].status == "set"
    assert by_name["SECRET"].status == "set"


def test_discover_env_files_non_recursive(tmp_path):
    (tmp_path / ".env").write_text("X=1", encoding="utf-8")
    (tmp_path / ".env.example").write_text("X=<x>", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / ".env").write_text("Y=2", encoding="utf-8")

    found = discover_env_files(tmp_path, recursive=False)
    names = sorted(p.name for p in found)
    assert names == [".env", ".env.example"]


def test_discover_env_files_recursive(tmp_path):
    (tmp_path / ".env").write_text("X=1", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / ".env").write_text("Y=2", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / ".env").write_text("Z=3", encoding="utf-8")

    found = discover_env_files(tmp_path, recursive=True)
    paths = sorted(str(p.relative_to(tmp_path)) for p in found)
    assert ".env" in paths
    assert "sub/.env" in paths
    assert all("node_modules" not in p for p in paths)


def test_find_example_for(tmp_path):
    real = tmp_path / ".env"
    example = tmp_path / ".env.example"
    real.write_text("X=1", encoding="utf-8")
    example.write_text("X=<x>", encoding="utf-8")
    assert find_example_for(real) == example
    assert find_example_for(example) is None


def _run_main(argv: list[str]) -> int:
    old = sys.argv
    sys.argv = ["enver"] + argv
    try:
        from rogkit_package.bin.enver import main as _main

        return _main()
    finally:
        sys.argv = old


def test_main_keys_only(tmp_path, capsys, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("FOO=bar\nBAZ=<x>\n", encoding="utf-8")
    monkeypatch.setenv("ROGKIT_CWD", str(tmp_path))

    rc = _run_main([str(env), "--keys-only"])

    assert rc == 0
    out = capsys.readouterr().out
    assert "FOO" in out
    assert "BAZ" in out
    assert "bar" not in out


def test_main_check_flag_fails_on_placeholder(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("FOO=<placeholder>\n", encoding="utf-8")
    monkeypatch.setenv("ROGKIT_CWD", str(tmp_path))

    rc = _run_main([str(env), "--check", "--plain"])

    assert rc == 2


def test_main_check_flag_passes_when_set(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("FOO=realvalue\n", encoding="utf-8")
    monkeypatch.setenv("ROGKIT_CWD", str(tmp_path))

    rc = _run_main([str(env), "--check", "--plain"])

    assert rc == 0


def test_main_llm_format_no_values(tmp_path, capsys, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("FOO=secret123\nBAR=<x>\n", encoding="utf-8")
    monkeypatch.setenv("ROGKIT_CWD", str(tmp_path))

    rc = _run_main([str(env), "--llm"])

    assert rc == 0
    out = capsys.readouterr().out
    assert "FOO=set" in out
    assert "BAR=placeholder" in out
    assert "secret123" not in out
