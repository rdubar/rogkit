"""Tests for hash.py - file and stdin hashing utility."""

from __future__ import annotations

import hashlib
import io
import sys

from rogkit_package.bin.hash import hash_bytes, hash_file, hash_stdin, render_results


def test_hash_bytes_sha256():
    assert hash_bytes(b"hello") == hashlib.sha256(b"hello").hexdigest()


def test_hash_bytes_md5():
    assert hash_bytes(b"hello", "md5") == hashlib.md5(b"hello").hexdigest()


def test_hash_file(tmp_path):
    path = tmp_path / "sample.txt"
    path.write_text("hello world", encoding="utf-8")

    assert hash_file(path, "sha1") == hashlib.sha1(b"hello world").hexdigest()


def test_hash_stdin(monkeypatch):
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(b"from stdin"), encoding="utf-8"))

    assert hash_stdin("sha512") == hashlib.sha512(b"from stdin").hexdigest()


def test_render_results_plain_outputs_rows(capsys):
    render_results([("abc123", "/tmp/file.txt")], plain=True)
    out = capsys.readouterr().out
    assert "abc123" in out
    assert "/tmp/file.txt" in out


def _run_main(argv: list[str]) -> int:
    old = sys.argv
    sys.argv = ["hash"] + argv
    try:
        from rogkit_package.bin.hash import main as _main

        return _main()
    finally:
        sys.argv = old


def test_main_file(tmp_path, capsys):
    path = tmp_path / "sample.txt"
    path.write_text("hello", encoding="utf-8")

    rc = _run_main([str(path), "--algo", "sha256", "--plain"])

    assert rc == 0
    out = capsys.readouterr().out
    assert hashlib.sha256(b"hello").hexdigest() in out


def test_main_missing_file(tmp_path):
    rc = _run_main([str(tmp_path / "missing.txt")])
    assert rc == 1


def test_main_stdin(monkeypatch, capsys):
    class FakeStdin:
        def __init__(self, data: bytes):
            self.buffer = io.BytesIO(data)

        def isatty(self) -> bool:
            return False

    monkeypatch.setattr(sys, "stdin", FakeStdin(b"piped"))

    rc = _run_main(["--plain"])

    assert rc == 0
    assert hashlib.sha256(b"piped").hexdigest() in capsys.readouterr().out
