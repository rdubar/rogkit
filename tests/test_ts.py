"""Tests for ts.py - timestamp conversion utility."""

from __future__ import annotations

import io
import sys
from datetime import UTC, datetime

from rogkit_package.bin.ts import convert_timestamp, render_timestamp


def test_convert_timestamp_from_epoch():
    info = convert_timestamp("1712947200")
    assert info.epoch == 1712947200
    assert info.utc_iso.startswith("2024-04-12T")


def test_convert_timestamp_from_iso_z():
    info = convert_timestamp("2026-04-12T10:30:00Z")
    assert info.epoch == int(datetime(2026, 4, 12, 10, 30, tzinfo=UTC).timestamp())
    assert info.utc_iso == "2026-04-12T10:30:00Z"


def test_convert_timestamp_from_naive_iso():
    info = convert_timestamp("2026-04-12T10:30:00")
    assert info.epoch > 0
    assert "T10:30:00" in info.local_iso


def test_convert_timestamp_invalid_epoch_raises():
    import pytest

    with pytest.raises(ValueError, match="Invalid epoch timestamp"):
        convert_timestamp("39803890284938948290")


def test_convert_timestamp_invalid_string_raises():
    import pytest

    with pytest.raises(ValueError, match="Invalid timestamp"):
        convert_timestamp("not-a-date")


def test_render_timestamp_plain_outputs_rows(capsys):
    info = convert_timestamp("2026-04-12T10:30:00Z")
    render_timestamp(info, plain=True)
    out = capsys.readouterr().out
    assert "epoch:" in out
    assert "utc:" in out
    assert "local:" in out


def _run_main(argv: list[str]) -> int:
    old = sys.argv
    sys.argv = ["ts"] + argv
    try:
        from rogkit_package.bin.ts import main as _main

        return _main()
    finally:
        sys.argv = old


def test_main_epoch(capsys):
    rc = _run_main(["1712947200", "--plain"])
    assert rc == 0
    assert "epoch: 1712947200" in capsys.readouterr().out


def test_main_stdin(monkeypatch, capsys):
    class FakeStdin(io.StringIO):
        def isatty(self) -> bool:
            return False

    monkeypatch.setattr(sys, "stdin", FakeStdin("2026-04-12T10:30:00Z"))

    rc = _run_main(["--plain"])

    assert rc == 0
    assert "utc: 2026-04-12T10:30:00Z" in capsys.readouterr().out


def test_main_invalid_epoch(capsys):
    rc = _run_main(["39803890284938948290"])
    assert rc == 1
    assert "Invalid epoch timestamp" in capsys.readouterr().err
