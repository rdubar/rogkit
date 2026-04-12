"""Tests for dedupe.py - duplicate file finder."""

from __future__ import annotations

import sys
from pathlib import Path

from rogkit_package.bin.dedupe import (
    ScanConfig,
    delete_empty_files,
    find_duplicate_groups,
    find_empty_files,
    render_groups,
)


def test_find_duplicate_groups(tmp_path):
    (tmp_path / "a.txt").write_text("same", encoding="utf-8")
    (tmp_path / "b.txt").write_text("same", encoding="utf-8")
    (tmp_path / "c.txt").write_text("different", encoding="utf-8")

    groups, _engine, _scanned = find_duplicate_groups(tmp_path)

    assert len(groups) == 1
    assert len(groups[0].paths) == 2
    assert {path.name for path in groups[0].paths} == {"a.txt", "b.txt"}


def test_find_empty_files(tmp_path):
    (tmp_path / "empty.txt").write_text("", encoding="utf-8")
    (tmp_path / "full.txt").write_text("data", encoding="utf-8")

    empty_files, _engine, _scanned = find_empty_files(tmp_path)

    assert [path.name for path in empty_files] == ["empty.txt"]


def test_delete_empty_files_force(tmp_path):
    empty = tmp_path / "empty.txt"
    empty.write_text("", encoding="utf-8")

    deleted = delete_empty_files([empty], force=True)

    assert deleted == 1
    assert not empty.exists()


def test_render_groups_plain_outputs_rows(capsys, tmp_path):
    (tmp_path / "a.txt").write_text("same", encoding="utf-8")
    (tmp_path / "b.txt").write_text("same", encoding="utf-8")
    groups, _engine, _scanned = find_duplicate_groups(tmp_path)

    render_groups(groups, plain=True)

    out = capsys.readouterr().out
    assert "Group 1" in out
    assert "a.txt" in out


def test_find_duplicate_groups_excludes_init_by_default(tmp_path):
    (tmp_path / "pkg1").mkdir()
    (tmp_path / "pkg2").mkdir()
    (tmp_path / "pkg1" / "__init__.py").write_text("same", encoding="utf-8")
    (tmp_path / "pkg2" / "__init__.py").write_text("same", encoding="utf-8")

    groups, _engine, _scanned = find_duplicate_groups(tmp_path)

    assert groups == []


def test_find_duplicate_groups_can_include_default_excludes(tmp_path):
    (tmp_path / "pkg1").mkdir()
    (tmp_path / "pkg2").mkdir()
    (tmp_path / "pkg1" / "__init__.py").write_text("same", encoding="utf-8")
    (tmp_path / "pkg2" / "__init__.py").write_text("same", encoding="utf-8")
    config = ScanConfig(ignore_patterns=(), engine="python", use_gitignore=False)

    groups, _engine, _scanned = find_duplicate_groups(tmp_path, config=config)

    assert len(groups) == 1


def test_find_duplicate_groups_respects_exclude_glob(tmp_path):
    (tmp_path / "a.log").write_text("same", encoding="utf-8")
    (tmp_path / "b.log").write_text("same", encoding="utf-8")
    config = ScanConfig(ignore_patterns=("*.log",), engine="python", use_gitignore=False)

    groups, _engine, _scanned = find_duplicate_groups(tmp_path, config=config)

    assert groups == []


def _run_main(argv: list[str]) -> int:
    old = sys.argv
    sys.argv = ["dedupe"] + argv
    try:
        from rogkit_package.bin.dedupe import main as _main

        return _main()
    finally:
        sys.argv = old


def test_main_duplicate_scan(tmp_path, capsys):
    (tmp_path / "a.txt").write_text("same", encoding="utf-8")
    (tmp_path / "b.txt").write_text("same", encoding="utf-8")

    rc = _run_main([str(tmp_path), "--plain"])

    assert rc == 0
    assert "Group 1" in capsys.readouterr().out


def test_main_delete_empty_force(tmp_path, capsys):
    (tmp_path / "empty.txt").write_text("", encoding="utf-8")

    rc = _run_main([str(tmp_path), "--delete-empty", "--force"])

    assert rc == 0
    assert "Deleted 1 empty file(s)." in capsys.readouterr().out


def test_main_verbose_outputs_summary(tmp_path, capsys):
    (tmp_path / "a.txt").write_text("same", encoding="utf-8")
    (tmp_path / "b.txt").write_text("same", encoding="utf-8")

    rc = _run_main([str(tmp_path), "--plain", "--verbose", "--engine", "python"])

    assert rc == 0
    out = capsys.readouterr().out
    assert "[dedupe]" in out
    assert "engine=python" in out


def test_main_missing_path(tmp_path):
    rc = _run_main([str(tmp_path / "missing")])
    assert rc == 1
