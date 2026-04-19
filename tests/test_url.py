"""Tests for url.py - URL encode/decode/parse utility."""

from __future__ import annotations

import io
import sys

from rogkit_package.bin.url import decode_value, encode_value, normalize_url, parse_url, render_parsed


def test_encode_value():
    assert encode_value("hello world") == "hello%20world"


def test_encode_value_plus():
    assert encode_value("hello world", plus=True) == "hello+world"


def test_decode_value():
    assert decode_value("hello%20world") == "hello world"


def test_decode_value_plus():
    assert decode_value("hello+world", plus=True) == "hello world"


def test_parse_url():
    parsed = parse_url("https://example.com/path?a=1&b=2#frag")
    assert parsed["scheme"] == "https"
    assert parsed["netloc"] == "example.com"
    assert parsed["path"] == "/path"
    assert parsed["fragment"] == "frag"
    assert parsed["query_items"] == [("a", "1"), ("b", "2")]


def test_normalize_url():
    assert normalize_url("HTTPS://Example.COM/path?b=2&a=1") == "https://example.com/path?a=1&b=2"


def test_normalize_url_preserves_credential_casing():
    result = normalize_url("https://MyUser:MyPass@EXAMPLE.COM/path")
    assert result.startswith("https://MyUser:MyPass@example.com")


def test_normalize_url_preserves_port():
    result = normalize_url("HTTPS://EXAMPLE.COM:8443/path?b=2&a=1")
    assert result == "https://example.com:8443/path?a=1&b=2"


def test_render_parsed_plain_outputs_rows(capsys):
    render_parsed(parse_url("https://example.com?a=1"), plain=True)
    out = capsys.readouterr().out
    assert "scheme: https" in out
    assert "query_item: a=1" in out


def _run_main(argv: list[str]) -> int:
    old = sys.argv
    sys.argv = ["url"] + argv
    try:
        from rogkit_package.bin.url import main as _main

        return _main()
    finally:
        sys.argv = old


def test_main_encode(capsys):
    rc = _run_main(["encode", "hello world"])
    assert rc == 0
    assert capsys.readouterr().out.strip() == "hello%20world"


def test_main_parse(capsys):
    rc = _run_main(["parse", "https://example.com?a=1", "--plain"])
    assert rc == 0
    assert "query_item: a=1" in capsys.readouterr().out


def test_main_stdin(monkeypatch, capsys):
    class FakeStdin(io.StringIO):
        def isatty(self) -> bool:
            return False

    monkeypatch.setattr(sys, "stdin", FakeStdin("hello world"))

    rc = _run_main(["encode"])

    assert rc == 0
    assert capsys.readouterr().out.strip() == "hello%20world"
