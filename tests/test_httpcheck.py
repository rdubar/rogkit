"""Tests for httpcheck.py - HTTP status checker."""

from __future__ import annotations

import sys
from io import StringIO
from types import SimpleNamespace

import pytest

from rogkit_package.bin.httpcheck import CheckResult, _normalize_url, _read_urls, check_url, render_results


def test_normalize_url_adds_https():
    assert _normalize_url("example.com") == "https://example.com"


def test_normalize_url_preserves_scheme():
    assert _normalize_url("http://example.com") == "http://example.com"


def test_read_urls_combines_sources(tmp_path, monkeypatch):
    file_path = tmp_path / "urls.txt"
    file_path.write_text("https://example.com\nhttps://openai.com\n")
    monkeypatch.setattr(sys, "stdin", StringIO("https://example.org\n"))

    args = SimpleNamespace(
        urls=["https://example.net"],
        file=str(file_path),
    )

    urls = _read_urls(args)

    assert urls == [
        "https://example.net",
        "https://example.com",
        "https://openai.com",
        "https://example.org",
    ]


def test_check_url_success(monkeypatch):
    response = SimpleNamespace(
        status_code=200,
        headers={"content-type": "text/html; charset=utf-8"},
        history=[object()],
        url="https://example.com/final",
    )
    monkeypatch.setattr("rogkit_package.bin.httpcheck.requests.get", lambda *args, **kwargs: response)

    result = check_url("example.com")

    assert result.status_code == 200
    assert result.content_type == "text/html"
    assert result.redirect_count == 1
    assert result.final_url == "https://example.com/final"
    assert result.ok is True


def test_check_url_request_error(monkeypatch):
    def _boom(*args, **kwargs):
        raise pytest.importorskip("requests").RequestException("boom")

    monkeypatch.setattr("rogkit_package.bin.httpcheck.requests.get", _boom)

    result = check_url("example.com")

    assert result.status_code is None
    assert result.ok is False
    assert "boom" in (result.error or "")


def test_render_results_plain_outputs_rows(capsys):
    render_results(
        [
            CheckResult(
                url="https://example.com",
                final_url="https://example.com",
                status_code=200,
                elapsed_ms=123,
                content_type="text/html",
                redirect_count=0,
                ok=True,
            )
        ],
        plain=True,
    )
    out = capsys.readouterr().out
    assert "200" in out
    assert "https://example.com" in out


def _run_main(argv: list[str]) -> int:
    old = sys.argv
    sys.argv = ["httpcheck"] + argv
    try:
        from rogkit_package.bin.httpcheck import main as _main

        return _main()
    finally:
        sys.argv = old


def test_main_plain_output(monkeypatch, capsys):
    monkeypatch.setattr(
        "rogkit_package.bin.httpcheck.check_urls",
        lambda urls, timeout=10: [
            CheckResult(
                url=urls[0],
                final_url=urls[0],
                status_code=200,
                elapsed_ms=50,
                content_type="text/html",
                redirect_count=0,
                ok=True,
            )
        ],
    )

    rc = _run_main(["https://example.com", "--plain"])

    assert rc == 0
    assert "https://example.com" in capsys.readouterr().out
