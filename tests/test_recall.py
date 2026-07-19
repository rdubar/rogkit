"""Tests for recall.py - unified recent-activity timeline."""

from __future__ import annotations

from datetime import datetime

from rogkit_package.bin.recall import (
    TimelineEntry,
    collect_notes,
    collect_shell_history,
    filter_entries,
    main,
    resolve_period,
)


def test_main_is_callable():
    assert callable(main)


def test_collect_shell_history_empty_without_extended_format(tmp_path):
    histfile = tmp_path / ".zsh_history"
    histfile.write_text("z running\ncodex\nclaude\n")
    assert collect_shell_history(histfile) == []


def test_collect_shell_history_parses_extended_format(tmp_path):
    histfile = tmp_path / ".zsh_history"
    histfile.write_text(": 1752800000:0;git status\n")
    entries = collect_shell_history(histfile)
    assert len(entries) == 1
    assert entries[0].source == "shell"
    assert entries[0].text == "git status"


def test_collect_shell_history_missing_file(tmp_path):
    assert collect_shell_history(tmp_path / "nope") == []


def test_collect_notes_reads_timestamped_entries(tmp_path, monkeypatch):
    notes_file = tmp_path / "notes.md"
    notes_file.write_text("## 2026-07-18\n\n- **09:30** fixed the thing\n")
    monkeypatch.setattr("rogkit_package.bin.recall._get_notes_file", lambda: notes_file)
    entries = collect_notes()
    assert len(entries) == 1
    assert entries[0].source == "note"
    assert entries[0].text == "fixed the thing"
    assert entries[0].timestamp == datetime(2026, 7, 18, 9, 30)


def test_collect_notes_empty_when_no_file(tmp_path, monkeypatch):
    monkeypatch.setattr("rogkit_package.bin.recall._get_notes_file", lambda: tmp_path / "nope.md")
    assert collect_notes() == []


def test_resolve_period_today_and_yesterday():
    today = resolve_period("today")
    yesterday = resolve_period("yesterday")
    assert today > yesterday
    assert today.hour == 0 and today.minute == 0


def test_resolve_period_duration():
    since = resolve_period("3d")
    assert (datetime.now() - since).days in (2, 3)


def test_resolve_period_invalid_raises():
    import pytest

    with pytest.raises(ValueError):
        resolve_period("not-a-period")


def test_filter_entries_by_since_and_grep():
    entries = [
        TimelineEntry(datetime(2026, 7, 18, 9, 0), "git:rogkit", "commit: fix bug"),
        TimelineEntry(datetime(2026, 7, 10, 9, 0), "git:rogkit", "commit: old work"),
        TimelineEntry(datetime(2026, 7, 18, 10, 0), "note", "unrelated note"),
    ]
    since = datetime(2026, 7, 15)
    filtered = filter_entries(entries, since=since, grep="fix")
    assert len(filtered) == 1
    assert filtered[0].text == "commit: fix bug"
