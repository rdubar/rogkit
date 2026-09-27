"""Tests for media library search filtering."""

from pathlib import Path
from typing import Any, Dict, List

import pytest

from rogkit_package.media import media, search


def _cached_records() -> List[Dict[str, Any]]:
    """Return cache records with newer episodes ahead of a series and movie."""
    return [
        {
            "title": "Second Episode",
            "title_low": "second episode",
            "metadata_type": 4,
            "added_at": 40,
        },
        {
            "title": "Pilot",
            "title_low": "pilot",
            "metadata_type": 4,
            "added_at": 30,
        },
        {
            "title": "Example Series",
            "title_low": "example series",
            "metadata_type": 2,
            "added_at": 20,
        },
        {
            "title": "Example Film",
            "title_low": "example film",
            "metadata_type": 1,
            "added_at": 10,
        },
    ]


def test_bare_cli_excludes_episodes_before_limit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Episode rows must not consume slots in the bare recent-media listing."""
    rendered_rows: List[Dict[str, Any]] = []

    def capture_rows(rows: List[Dict[str, Any]], _args: Any) -> None:
        rendered_rows.extend(rows)

    monkeypatch.setattr(media, "load_remote_config", lambda: None)
    monkeypatch.setattr(media, "detect_db_path", lambda: tmp_path / "plex.db")
    monkeypatch.setattr(media, "ensure_cache_table", lambda _path: None)
    monkeypatch.setattr(media, "get_cache_metadata", lambda _path: (4, 0.0))
    monkeypatch.setattr(media, "_render_media_rows", capture_rows)
    monkeypatch.setattr(search, "load_cached_records", lambda _path: _cached_records())

    result = media.main(["--no-daemon", "--number", "2"])

    assert result == 0
    assert [row["title"] for row in rendered_rows] == [
        "Example Series",
        "Example Film",
    ]


def test_title_search_still_includes_matching_episode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ordinary title searches should retain individual episode matches."""
    monkeypatch.setattr(search, "load_cached_records", lambda _path: _cached_records())

    rows, total = search.run_pretty_search(
        Path("unused.db"),
        ["pilot"],
        limit=10,
        sort="added",
        reverse=False,
        deep=False,
    )

    assert [row["title"] for row in rows] == ["Pilot"]
    assert total == 1
