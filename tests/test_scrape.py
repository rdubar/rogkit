import requests

import pytest

from rogkit_package.bin.scrape import ScrapeError, fix_url, parse_html, scrape
from rogkit_package.bin.scrape import _with_page_param


SAMPLE_HTML = """
<html>
  <head>
    <title>Example Page</title>
    <meta name="description" content="Example description.">
    <style>body { color: red; }</style>
  </head>
  <body>
    <h1>Hello world</h1>
    <p>This is text.</p>
    <script>console.log('ignore me');</script>
    <a href="/relative">Relative Link</a>
    <a href="https://example.com/absolute">Absolute Link</a>
  </body>
</html>
"""


def test_parse_html_strips_noise_and_extracts_meta():
    result = parse_html(SAMPLE_HTML, "https://example.com")

    assert result.title == "Example Page"
    assert result.description == "Example description."
    assert "Hello world" in result.text
    assert "This is text." in result.text
    assert "console.log" not in result.text
    assert "color: red" not in result.text
    assert any(link.href == "https://example.com/relative" for link in result.links)
    assert any(link.href == "https://example.com/absolute" for link in result.links)


def test_fix_url_defaults_to_https():
    assert fix_url("example.com") == "https://example.com"
    assert fix_url("http://example.com") == "http://example.com"
    assert fix_url("https://example.com") == "https://example.com"


def test_scrape_wraps_request_errors():
    class FakeSession:
        def get(self, url, timeout):
            raise requests.RequestException("boom")

    with pytest.raises(ScrapeError):
        scrape("example.com", session=FakeSession(), timeout=1)


def test_with_page_param_sets_or_replaces():
    assert _with_page_param("https://example.com", 2) == "https://example.com?page=2"
    assert _with_page_param("https://example.com?foo=bar", 3) in (
        "https://example.com?foo=bar&page=3",
        "https://example.com?page=3&foo=bar",
    )
