"""Tests for note.py - timestamped note-taking utility."""

import re
from pathlib import Path

import pytest

from rogkit_package.bin.note import _get_notes_file, _parse_entries, append_note, list_notes


# ---------------------------------------------------------------------------
# append_note
# ---------------------------------------------------------------------------

def test_creates_file_if_missing(tmp_path):
    f = tmp_path / "notes.md"
    append_note("first note", f)
    assert f.exists()


def test_appended_content_contains_text(tmp_path):
    f = tmp_path / "notes.md"
    append_note("hello world", f)
    content = f.read_text()
    assert "hello world" in content


def test_date_heading_written(tmp_path):
    f = tmp_path / "notes.md"
    append_note("test entry", f)
    content = f.read_text()
    assert re.search(r"## \d{4}-\d{2}-\d{2}", content)


def test_timestamp_prefix_written(tmp_path):
    f = tmp_path / "notes.md"
    append_note("timed note", f)
    content = f.read_text()
    # Expect bold HH:MM prefix like **21:05**
    assert re.search(r"\*\*\d{2}:\d{2}\*\*", content)


def test_multiple_notes_same_day_no_duplicate_heading(tmp_path):
    f = tmp_path / "notes.md"
    append_note("note one", f)
    append_note("note two", f)
    content = f.read_text()
    from datetime import datetime
    heading = f"## {datetime.now().strftime('%Y-%m-%d')}"
    assert content.count(heading) == 1


def test_both_notes_present_after_two_appends(tmp_path):
    f = tmp_path / "notes.md"
    append_note("alpha", f)
    append_note("beta", f)
    content = f.read_text()
    assert "alpha" in content
    assert "beta" in content


def test_creates_parent_directory(tmp_path):
    f = tmp_path / "subdir" / "nested" / "notes.md"
    append_note("deep note", f)
    assert f.exists()


# ---------------------------------------------------------------------------
# _parse_entries
# ---------------------------------------------------------------------------

def test_parse_entries_empty():
    assert _parse_entries("") == []


def test_parse_entries_returns_date_and_line():
    content = "## 2026-04-12\n\n- **10:00** hello\n"
    entries = _parse_entries(content)
    assert len(entries) == 1
    assert entries[0][0] == "2026-04-12"
    assert "hello" in entries[0][1]


def test_parse_entries_multiple_dates():
    content = (
        "## 2026-04-11\n\n- **09:00** old note\n\n"
        "## 2026-04-12\n\n- **10:00** new note\n"
    )
    entries = _parse_entries(content)
    assert len(entries) == 2
    assert entries[0][0] == "2026-04-11"
    assert entries[1][0] == "2026-04-12"


def test_parse_entries_ignores_non_bullet_lines():
    content = "## 2026-04-12\n\nSome prose line\n- **10:00** real entry\n"
    entries = _parse_entries(content)
    assert len(entries) == 1


# ---------------------------------------------------------------------------
# list_notes
# ---------------------------------------------------------------------------

def test_list_notes_missing_file(tmp_path):
    f = tmp_path / "nonexistent.md"
    rc = list_notes(f)
    assert rc == 1


def test_list_notes_returns_zero_on_success(tmp_path):
    f = tmp_path / "notes.md"
    append_note("something", f)
    rc = list_notes(f, count=5)
    assert rc == 0


def test_list_notes_query_filter(tmp_path):
    f = tmp_path / "notes.md"
    append_note("buy milk", f)
    append_note("read book", f)
    # Should not raise; just verifies it runs cleanly with a query
    rc = list_notes(f, count=10, query="milk")
    assert rc == 0


def test_list_notes_count_limits_output(tmp_path, capsys):
    f = tmp_path / "notes.md"
    for i in range(5):
        append_note(f"note {i}", f)
    capsys.readouterr()  # discard append output
    list_notes(f, count=2)
    captured = capsys.readouterr()
    # Only last 2 notes should appear
    assert "note 3" in captured.out
    assert "note 4" in captured.out
    assert "note 0" not in captured.out


# ---------------------------------------------------------------------------
# _get_notes_file
# ---------------------------------------------------------------------------

def test_get_notes_file_override():
    result = _get_notes_file("/tmp/my_notes.md")
    assert result == Path("/tmp/my_notes.md")


def test_get_notes_file_default(monkeypatch):
    monkeypatch.setattr("rogkit_package.bin.note.get_config_value", lambda *_args: None)
    result = _get_notes_file()
    assert result == Path.home() / "notes.md"
