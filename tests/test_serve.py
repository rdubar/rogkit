"""Tests for serve.py - simple local file server."""

from __future__ import annotations

import sys
from pathlib import Path

from rogkit_package.bin.serve import local_url, resolve_directory


def test_local_url():
    assert local_url("127.0.0.1", 9000) == "http://127.0.0.1:9000/"


def test_resolve_directory_defaults_to_invoking_cwd(monkeypatch, tmp_path):
    monkeypatch.setattr("rogkit_package.bin.serve.get_invoking_cwd", lambda: tmp_path)
    assert resolve_directory(None) == tmp_path


def test_resolve_directory_relative(monkeypatch, tmp_path):
    monkeypatch.setattr("rogkit_package.bin.serve.get_invoking_cwd", lambda: tmp_path)
    nested = tmp_path / "site"
    nested.mkdir()
    assert resolve_directory("site") == nested.resolve()


def _run_main(argv: list[str]) -> int:
    old = sys.argv
    sys.argv = ["serve"] + argv
    try:
        from rogkit_package.bin.serve import main as _main

        return _main()
    finally:
        sys.argv = old


def test_main_missing_directory(tmp_path):
    rc = _run_main(["--path", str(tmp_path / "missing")])
    assert rc == 1


def test_main_not_directory(tmp_path):
    file_path = tmp_path / "file.txt"
    file_path.write_text("hello", encoding="utf-8")
    rc = _run_main(["--path", str(file_path)])
    assert rc == 1


def test_main_bind_error(monkeypatch, tmp_path):
    monkeypatch.setattr("rogkit_package.bin.serve.resolve_directory", lambda _path: tmp_path)

    def _boom(directory: Path, host: str = "127.0.0.1", port: int = 8000):
        raise OSError("port in use")

    monkeypatch.setattr("rogkit_package.bin.serve.make_server", _boom)

    rc = _run_main([])

    assert rc == 1
