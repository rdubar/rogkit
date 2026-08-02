"""Tests for spot.py - Spotify liked songs and playlist manager."""

from __future__ import annotations

import pytest

from rogkit_package.bin.spot import (
    SpotifyClient,
    _line_to_search_query,
    download_playlist,
    read_song_list,
    resolve_playlist,
    SPOTDL_INSTALL_HELP,
)


PLAYLISTS = [
    {"id": "id1", "name": "Road Trip", "url": "https://open.spotify.com/playlist/id1", "track_count": 42},
    {"id": "id2", "name": "Focus Mix", "url": "https://open.spotify.com/playlist/id2", "track_count": 10},
    {"id": "id3", "name": "Focus Deep", "url": "https://open.spotify.com/playlist/id3", "track_count": 5},
]


def test_resolve_playlist_by_index():
    assert resolve_playlist(PLAYLISTS, "2") is PLAYLISTS[1]


def test_resolve_playlist_by_index_out_of_range():
    assert resolve_playlist(PLAYLISTS, "99") is None


def test_resolve_playlist_by_id():
    assert resolve_playlist(PLAYLISTS, "id3") is PLAYLISTS[2]


def test_resolve_playlist_by_unique_name_substring():
    assert resolve_playlist(PLAYLISTS, "road") is PLAYLISTS[0]


def test_resolve_playlist_by_ambiguous_name_raises():
    with pytest.raises(ValueError, match="Ambiguous"):
        resolve_playlist(PLAYLISTS, "focus")


def test_resolve_playlist_no_match_returns_none():
    assert resolve_playlist(PLAYLISTS, "nonexistent") is None


def test_download_playlist_missing_spotdl_exits(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr("rogkit_package.bin.spot.shutil.which", lambda _cmd: None)

    with pytest.raises(SystemExit) as exc_info:
        download_playlist(PLAYLISTS[0], tmp_path)

    assert exc_info.value.code == 1
    assert SPOTDL_INSTALL_HELP in capsys.readouterr().out


class _FakePlaylistSpotify:
    """Fake spotipy client paginating playlist_items across two pages."""

    def __init__(self):
        self._pages = [
            {
                'items': [
                    {'track': {'name': 'Song A', 'artists': [{'name': 'Artist One'}, {'name': 'Artist Two'}]}},
                    {'track': None},  # e.g. a removed/local track Spotify returns as null
                ],
                'next': True,
            },
            {
                'items': [
                    {'track': {'name': 'Song B', 'artists': [{'name': 'Solo Artist'}]}},
                ],
                'next': False,
            },
        ]
        self._index = 0

    def playlist_items(self, _playlist_id):
        page = self._pages[self._index]
        self._index += 1
        return page

    def next(self, _results):
        page = self._pages[self._index]
        self._index += 1
        return page


def test_get_playlist_tracks_formats_multi_artist_and_skips_null_track():
    client = SpotifyClient(client_id="id", client_secret="secret", redirect_uri="uri")
    client.sp = _FakePlaylistSpotify()

    tracks = client.get_playlist_tracks("playlist123")

    assert tracks == ["Song A - Artist One, Artist Two", "Song B - Solo Artist"]


def test_line_to_search_query_title_artist_shape_is_field_scoped():
    assert _line_to_search_query("Song A - Artist One") == "track:Song A artist:Artist One"


def test_line_to_search_query_free_text_passthrough():
    assert _line_to_search_query("some vague search terms") == "some vague search terms"


def test_line_to_search_query_blank_and_comment_lines_are_none():
    assert _line_to_search_query("   ") is None
    assert _line_to_search_query("# a comment") is None


def test_read_song_list_from_file(tmp_path):
    song_file = tmp_path / "songs.txt"
    song_file.write_text("Song A - Artist One\nSong B - Artist Two\n", encoding="utf-8")

    assert read_song_list(str(song_file)) == ["Song A - Artist One", "Song B - Artist Two"]


def test_read_song_list_missing_file_exits(tmp_path):
    with pytest.raises(SystemExit) as exc_info:
        read_song_list(str(tmp_path / "nonexistent.txt"))
    assert exc_info.value.code == 1


class _FakeCreatePlaylistSpotify:
    """Fake spotipy client for search + playlist creation + add-items."""

    def __init__(self, matches):
        self.matches = matches  # query -> uri or None
        self.created = None
        self.added_batches = []

    def search(self, q, type, limit):  # noqa: A002 - matches spotipy's signature
        uri = self.matches.get(q)
        items = [{'uri': uri}] if uri else []
        return {'tracks': {'items': items}}

    def user_playlist_create(self, user_id, name, public, description):
        self.created = {
            'id': 'new_playlist_id',
            'name': name,
            'public': public,
            'external_urls': {'spotify': 'https://open.spotify.com/playlist/new_playlist_id'},
        }
        return self.created

    def playlist_add_items(self, playlist_id, uris):
        self.added_batches.append(list(uris))


def test_create_playlist_and_add_tracks_flow():
    fake_sp = _FakeCreatePlaylistSpotify(matches={"track:Song A artist:Artist One": "spotify:track:1"})
    client = SpotifyClient(client_id="id", client_secret="secret", redirect_uri="uri")
    client.sp = fake_sp

    uri = client.search_track("track:Song A artist:Artist One")
    assert uri == "spotify:track:1"
    assert client.search_track("track:No Match artist:Nobody") is None

    playlist = client.create_playlist("user1", "My Playlist", public=False)
    client.add_tracks_to_playlist(playlist['id'], [uri])

    assert fake_sp.created['name'] == "My Playlist"
    assert fake_sp.added_batches == [["spotify:track:1"]]


def test_add_tracks_to_playlist_batches_in_groups_of_100():
    fake_sp = _FakeCreatePlaylistSpotify(matches={})
    client = SpotifyClient(client_id="id", client_secret="secret", redirect_uri="uri")
    client.sp = fake_sp

    uris = [f"spotify:track:{i}" for i in range(150)]
    client.add_tracks_to_playlist("playlist_id", uris)

    assert len(fake_sp.added_batches) == 2
    assert len(fake_sp.added_batches[0]) == 100
    assert len(fake_sp.added_batches[1]) == 50
