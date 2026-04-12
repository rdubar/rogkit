"""Tests for jsonr.py — JSON pretty-printer and query tool."""

import json
import sys
from io import StringIO
from pathlib import Path

import pytest

from rogkit_package.bin.jsonr import apply_path, load_json, _tokenise_path, main


# ---------------------------------------------------------------------------
# _tokenise_path
# ---------------------------------------------------------------------------

def test_tokenise_dot_only():
    assert _tokenise_path(".") == []

def test_tokenise_empty():
    assert _tokenise_path("") == []

def test_tokenise_single_key():
    assert _tokenise_path(".name") == ["name"]

def test_tokenise_nested_keys():
    assert _tokenise_path(".a.b.c") == ["a", "b", "c"]

def test_tokenise_array_index():
    assert _tokenise_path(".[0]") == [0]

def test_tokenise_key_then_index():
    assert _tokenise_path(".users[2]") == ["users", 2]

def test_tokenise_key_index_key():
    assert _tokenise_path(".users[0].name") == ["users", 0, "name"]

def test_tokenise_iterate_sentinel():
    tokens = _tokenise_path(".items[]")
    assert tokens == ["items", None]


# ---------------------------------------------------------------------------
# apply_path
# ---------------------------------------------------------------------------

DATA = {
    "name": "Alice",
    "age": 30,
    "address": {"city": "London", "zip": "EC1A"},
    "tags": ["python", "go", "rust"],
    "scores": [{"val": 10}, {"val": 20}],
}


def test_apply_identity():
    assert apply_path(DATA, ".") == DATA

def test_apply_top_level_key():
    assert apply_path(DATA, ".name") == "Alice"

def test_apply_nested_key():
    assert apply_path(DATA, ".address.city") == "London"

def test_apply_array_index():
    assert apply_path(DATA, ".tags[0]") == "python"

def test_apply_array_negative_conceptually_fails():
    # Negative indices not supported — should raise TypeError or IndexError
    with pytest.raises((TypeError, KeyError, ValueError)):
        apply_path(DATA, ".tags[-1]")

def test_apply_key_then_index_then_key():
    assert apply_path(DATA, ".scores[1].val") == 20

def test_apply_iterate_returns_list():
    result = apply_path(DATA, ".tags[]")
    assert result == ["python", "go", "rust"]

def test_apply_missing_key_raises():
    with pytest.raises(KeyError):
        apply_path(DATA, ".nonexistent")

def test_apply_index_out_of_range_raises():
    with pytest.raises(IndexError):
        apply_path(DATA, ".tags[99]")

def test_apply_index_into_non_list_raises():
    with pytest.raises(TypeError):
        apply_path(DATA, ".name[0]")

def test_apply_on_list_root():
    data = [1, 2, 3]
    assert apply_path(data, ".[1]") == 2

def test_apply_numeric_string_key():
    data = {"1": "one"}
    assert apply_path(data, ".1") == "one"


# ---------------------------------------------------------------------------
# load_json
# ---------------------------------------------------------------------------

def test_load_json_from_file(tmp_path):
    f = tmp_path / "data.json"
    f.write_text(json.dumps({"key": "value"}))
    result = load_json(str(f))
    assert result == {"key": "value"}

def test_load_json_file_not_found():
    with pytest.raises(FileNotFoundError):
        load_json("/nonexistent/path/data.json")

def test_load_json_from_stdin(monkeypatch):
    monkeypatch.setattr(sys, "stdin", StringIO('{"x": 42}'))
    result = load_json(None)
    assert result == {"x": 42}

def test_load_json_invalid_raises(tmp_path):
    f = tmp_path / "bad.json"
    f.write_text("not json {{{")
    with pytest.raises(json.JSONDecodeError):
        load_json(str(f))


# ---------------------------------------------------------------------------
# main() integration
# ---------------------------------------------------------------------------

def test_main_pretty_prints_file(tmp_path, capsys):
    f = tmp_path / "test.json"
    f.write_text(json.dumps({"hello": "world"}))
    rc = main.__wrapped__(f.as_posix()) if hasattr(main, "__wrapped__") else _run_main([str(f)])
    # Just check it exits cleanly — output tested separately
    assert rc == 0 or rc is None


def _run_main(argv: list[str]) -> int:
    import sys
    old = sys.argv
    sys.argv = ["json"] + argv
    try:
        from rogkit_package.bin.jsonr import main as _main
        return _main()
    finally:
        sys.argv = old


def test_main_returns_zero_for_valid_file(tmp_path):
    f = tmp_path / "a.json"
    f.write_text('{"a": 1}')
    assert _run_main([str(f)]) == 0


def test_main_returns_one_for_missing_file(tmp_path):
    assert _run_main([str(tmp_path / "nope.json")]) == 1


def test_main_returns_one_for_invalid_json(tmp_path):
    f = tmp_path / "bad.json"
    f.write_text("not json")
    assert _run_main([str(f)]) == 1


def test_main_query_valid(tmp_path, capsys):
    f = tmp_path / "a.json"
    f.write_text('{"name": "Bob"}')
    rc = _run_main([str(f), "-q", ".name", "--plain"])
    assert rc == 0
    assert "Bob" in capsys.readouterr().out


def test_main_query_missing_key_returns_one(tmp_path):
    f = tmp_path / "a.json"
    f.write_text('{"name": "Bob"}')
    assert _run_main([str(f), "-q", ".missing"]) == 1


def test_main_keys_dict(tmp_path, capsys):
    f = tmp_path / "a.json"
    f.write_text('{"alpha": 1, "beta": 2}')
    rc = _run_main([str(f), "--keys"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "alpha" in out
    assert "beta" in out


def test_main_keys_list(tmp_path, capsys):
    f = tmp_path / "a.json"
    f.write_text('[1, 2, 3]')
    rc = _run_main([str(f), "--keys"])
    assert rc == 0
    assert "3" in capsys.readouterr().out


def test_main_compact(tmp_path, capsys):
    f = tmp_path / "a.json"
    f.write_text('{"a": 1, "b": 2}')
    rc = _run_main([str(f), "-c", "--plain"])
    assert rc == 0
    out = capsys.readouterr().out.strip()
    assert "\n" not in out
