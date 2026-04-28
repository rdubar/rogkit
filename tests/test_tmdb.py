"""Tests for TMDb metadata fetching."""

from typing import Any

import requests

from rogkit_package.media import tmdb


class FakeResponse:
    """Small response stub for TMDb request tests."""

    def __init__(self, payload: dict[str, Any], status_code: int = 200) -> None:
        self.payload = payload
        self.status_code = status_code

    def json(self) -> dict[str, Any]:
        """Return the configured JSON payload."""
        return self.payload


def test_get_movie_details_handles_search_timeout(monkeypatch, capsys) -> None:
    """TMDb search timeouts should be treated as no match."""

    data_list = tmdb.DataList()

    def raise_timeout(_url: str, timeout: int) -> FakeResponse:
        raise requests.ReadTimeout("read timed out")

    monkeypatch.setattr(tmdb.requests, "get", raise_timeout)

    assert data_list.get_movie_details("Aliens", 1986) is None
    output = capsys.readouterr().out

    assert "TMDB search for Aliens (1986) failed" in output
    assert "read timed out" in output


def test_get_movie_details_handles_detail_timeout(monkeypatch, capsys) -> None:
    """TMDb detail timeouts should be treated as no match."""

    data_list = tmdb.DataList()
    responses = [
        FakeResponse({"results": [{"id": 679, "release_date": "1986-07-18"}]}),
        requests.ReadTimeout("read timed out"),
    ]

    def fake_get(_url: str, timeout: int) -> FakeResponse:
        response = responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr(tmdb.requests, "get", fake_get)

    assert data_list.get_movie_details("Aliens", 1986) is None
    output = capsys.readouterr().out

    assert "TMDB detail fetch for movie ID 679 failed" in output
    assert "read timed out" in output
