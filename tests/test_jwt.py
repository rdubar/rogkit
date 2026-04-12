"""Tests for jwt.py - JWT decoder utility."""

from __future__ import annotations

import io
import json
import sys

import pytest

from rogkit_package.bin.jwt import annotate_time_claims, decode_jwt, render_decoded


TEST_TOKEN = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJzdWIiOiIxMjMiLCJuYW1lIjoiUm9nZXIiLCJhZG1pbiI6dHJ1ZX0."
    "signature"
)

TIME_TOKEN = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJzdWIiOiIxMjMiLCJleHAiOjE3MTI5NDcyMDAsImlhdCI6MTcxMjk0MzYwMCwibmJmIjoxNzEyOTQzNjAwfQ."
    "signature"
)


def test_decode_jwt():
    decoded = decode_jwt(TEST_TOKEN)
    assert decoded["header"]["alg"] == "HS256"
    assert decoded["payload"]["name"] == "Roger"
    assert decoded["signature"] == "signature"


def test_decode_jwt_requires_three_segments():
    with pytest.raises(ValueError, match="3 dot-separated"):
        decode_jwt("abc.def")


def test_decode_jwt_rejects_invalid_json():
    with pytest.raises(ValueError, match="valid JSON"):
        decode_jwt("bm90LWpzb24.bm90LWpzb24.sig")


def test_annotate_time_claims_adds_friendly_times():
    annotated = annotate_time_claims(decode_jwt(TIME_TOKEN))
    assert annotated["time_claims"]["exp"]["epoch"] == "1712947200"
    assert annotated["time_claims"]["exp"]["utc"].startswith("2024-04-12T")
    assert "local" in annotated["time_claims"]["iat"]


def test_render_decoded_plain_outputs_json(capsys):
    render_decoded({"header": {"alg": "HS256"}, "payload": {"sub": "123"}, "signature": "sig"}, plain=True)
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["payload"]["sub"] == "123"


def _run_main(argv: list[str]) -> int:
    old = sys.argv
    sys.argv = ["jwt"] + argv
    try:
        from rogkit_package.bin.jwt import main as _main

        return _main()
    finally:
        sys.argv = old


def test_main_token_arg(capsys):
    rc = _run_main([TEST_TOKEN, "--plain"])
    assert rc == 0
    assert "Roger" in capsys.readouterr().out


def test_main_time_claims_are_rendered(capsys):
    rc = _run_main([TIME_TOKEN, "--plain"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "time_claims" in out
    assert "1712947200" in out


def test_main_stdin(monkeypatch, capsys):
    class FakeStdin(io.StringIO):
        def isatty(self) -> bool:
            return False

    monkeypatch.setattr(sys, "stdin", FakeStdin(TEST_TOKEN))

    rc = _run_main(["--plain"])

    assert rc == 0
    assert "HS256" in capsys.readouterr().out


def test_main_invalid_token(capsys):
    rc = _run_main(["abc.def"])
    assert rc == 1
    assert "3 dot-separated" in capsys.readouterr().err
