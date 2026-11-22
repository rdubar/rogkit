"""Tests for findfile.py - finding a file by name via opener's o."""

from __future__ import annotations

from pathlib import Path

from rogkit_package.bin import findfile


def test_real_path_wins(tmp_path):
    f = tmp_path / "post.md"
    f.write_text("x")
    assert findfile.find_file("post.md", cwd=tmp_path) == f


def test_suffix_added_in_folder(tmp_path):
    f = tmp_path / "bug-hunter.md"
    f.write_text("x")
    assert findfile.find_file("bug-hunter", suffixes=(".md",), cwd=tmp_path) == f


def test_search_single_match(tmp_path, monkeypatch):
    target = tmp_path / "elsewhere" / "kairos1.md"
    monkeypatch.setattr(findfile, "search", lambda words: [target])
    assert findfile.find_file(["kairos1"], cwd=tmp_path) == target


def test_suffix_filter_prefers_markdown(tmp_path, monkeypatch):
    md, png = Path("/a/notes.md"), Path("/a/notes.png")
    monkeypatch.setattr(findfile, "search", lambda words: [png, md])
    assert findfile.find_file("notes", suffixes=(".md",), cwd=tmp_path) == md


def test_several_matches_not_interactive(tmp_path, monkeypatch):
    monkeypatch.setattr(findfile, "search", lambda words: [Path("/a/x.md"), Path("/b/x.md")])
    assert findfile.find_file("x", cwd=tmp_path, interactive=False) is None


def test_search_uses_o(tmp_path):
    fake = tmp_path / "o"
    fake.write_text("#!/bin/sh\n[ \"$1\" = -p ] && echo /found/it.md\n")
    fake.chmod(0o755)
    assert findfile.search(["it"], o_cmd=str(fake)) == [Path("/found/it.md")]
