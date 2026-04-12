"""Tests for archive.py - archive inspection and extraction."""

from __future__ import annotations

import gzip
import io
import sys
import tarfile
import zipfile
from pathlib import Path

from rogkit_package.bin.archive import extract_all, list_archive, read_member, render_listing


def _make_zip(path: Path) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("folder/hello.txt", "hello zip")
        archive.writestr("root.txt", "root zip")


def _make_tar(path: Path) -> None:
    with tarfile.open(path, "w:gz") as archive:
        data = b"hello tar"
        info = tarfile.TarInfo("folder/hello.txt")
        info.size = len(data)
        archive.addfile(info, io.BytesIO(data))


def _make_gzip(path: Path, contents: bytes = b"hello gzip") -> None:
    with gzip.open(path, "wb") as handle:
        handle.write(contents)


def test_list_archive_zip(tmp_path):
    archive_path = tmp_path / "sample.zip"
    _make_zip(archive_path)

    assert list_archive(archive_path) == ["folder/hello.txt", "root.txt"]


def test_list_archive_tar(tmp_path):
    archive_path = tmp_path / "sample.tar.gz"
    _make_tar(archive_path)

    assert list_archive(archive_path) == ["folder/hello.txt"]


def test_list_archive_gzip(tmp_path):
    archive_path = tmp_path / "sample.txt.gz"
    _make_gzip(archive_path)

    assert list_archive(archive_path) == ["sample.txt"]


def test_read_member_zip(tmp_path):
    archive_path = tmp_path / "sample.zip"
    _make_zip(archive_path)

    assert read_member(archive_path, "folder/hello.txt") == b"hello zip"


def test_read_member_tar(tmp_path):
    archive_path = tmp_path / "sample.tar.gz"
    _make_tar(archive_path)

    assert read_member(archive_path, "folder/hello.txt") == b"hello tar"


def test_read_member_gzip(tmp_path):
    archive_path = tmp_path / "sample.txt.gz"
    _make_gzip(archive_path)

    assert read_member(archive_path) == b"hello gzip"


def test_extract_all_zip(tmp_path):
    archive_path = tmp_path / "sample.zip"
    _make_zip(archive_path)
    destination = tmp_path / "out"

    written = extract_all(archive_path, destination)

    assert (destination / "folder" / "hello.txt").read_text() == "hello zip"
    assert len(written) == 2


def test_extract_all_tar(tmp_path):
    archive_path = tmp_path / "sample.tar.gz"
    _make_tar(archive_path)
    destination = tmp_path / "out"

    written = extract_all(archive_path, destination)

    assert (destination / "folder" / "hello.txt").read_text() == "hello tar"
    assert len(written) == 1


def test_extract_all_gzip(tmp_path):
    archive_path = tmp_path / "sample.txt.gz"
    _make_gzip(archive_path)
    destination = tmp_path / "out"

    written = extract_all(archive_path, destination)

    assert (destination / "sample.txt").read_text() == "hello gzip"
    assert len(written) == 1


def test_render_listing_plain_outputs_names(capsys, tmp_path):
    archive_path = tmp_path / "sample.zip"
    render_listing(archive_path, ["folder/hello.txt", "root.txt"], plain=True)
    out = capsys.readouterr().out
    assert "folder/hello.txt" in out
    assert "root.txt" in out


def _run_main(argv: list[str]) -> int:
    old = sys.argv
    sys.argv = ["archive"] + argv
    try:
        from rogkit_package.bin.archive import main as _main

        return _main()
    finally:
        sys.argv = old


def test_main_lists_zip(tmp_path, capsys):
    archive_path = tmp_path / "sample.zip"
    _make_zip(archive_path)

    rc = _run_main([str(archive_path), "--plain"])

    assert rc == 0
    assert "root.txt" in capsys.readouterr().out


def test_main_extracts_all(tmp_path):
    archive_path = tmp_path / "sample.zip"
    _make_zip(archive_path)
    destination = tmp_path / "out"

    rc = _run_main(["-x", str(archive_path), str(destination)])

    assert rc == 0
    assert (destination / "folder" / "hello.txt").read_text() == "hello zip"
