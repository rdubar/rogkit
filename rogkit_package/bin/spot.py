"""
Spotify liked songs manager.

CLI tool for viewing, searching, and managing Spotify liked songs with local caching.
Supports duplicate detection, playlist browsing, downloading a playlist's tracks via
spotdl, and creating a new playlist from a text list of songs. Configuration via
rogkit config.toml.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from time import perf_counter
from typing import Optional

from dotenv import load_dotenv
import spotipy  # type: ignore
from spotipy.oauth2 import SpotifyOAuth  # type: ignore
from spotipy.exceptions import SpotifyException  # type: ignore

from ..settings import get_invoking_cwd
from ..bin.tomlr import load_rogkit_toml
from .seconds import time_ago_in_words

# Load environment variables from .env file if present
load_dotenv()

SPOTDL_INSTALL_HELP = "spotdl not found on PATH. Install it with: uv tool install spotdl"


SPOTIFY_CONFIG_HELP = """
Spotify credentials are required. Add the following to ~/.config/rogkit/config.toml:

[spotify]
spotify_client_id = "your_client_id"
spotify_client_secret = "your_client_secret"
spotify_redirect_uri = "https://your-app.example.com/callback"

Spotify is deprecating HTTP redirects, so ensure the redirect URI is HTTPS.
"""


@dataclass
class SpotifyClient:
    """Spotify API client wrapper with authentication."""

    client_id: str
    client_secret: str
    redirect_uri: str
    scope: str = (
        'user-library-read playlist-read-private playlist-read-collaborative '
        'playlist-modify-private playlist-modify-public'
    )
    cache_path: str = ".spotify_cache"
    sp: Optional[spotipy.Spotify] = field(default=None, init=False)

    def authenticate(self):
        """Authenticate with Spotify using OAuth2."""
        auth_manager = SpotifyOAuth(
            client_id=self.client_id,
            client_secret=self.client_secret,
            redirect_uri=self.redirect_uri,
            scope=self.scope,
            cache_path=self.cache_path,
            open_browser=True,
        )

        token_info = auth_manager.get_cached_token()
        if token_info:
            print("Using cached Spotify token.")
        else:
            print('No cached token, launching Spotify authorization flow...')
            token = auth_manager.get_access_token(as_dict=False)
            if not token:
                raise RuntimeError("Failed to obtain Spotify access token.")
            print("Authentication successful.")

        self.sp = spotipy.Spotify(auth_manager=auth_manager)
        print("Spotify client authenticated successfully.")

    def get_liked_songs(self):
        """Retrieve all liked songs from Spotify."""
        if not self.sp:
            raise RuntimeError("Spotify client is not authenticated.")
        tracks = []
        results = self.sp.current_user_saved_tracks()
        while results:
            for item in results['items']:
                track = item['track']
                tracks.append(track['name'] + ' - ' + track['artists'][0]['name'])
            results = self.sp.next(results)
        return tracks

    def get_playlist_tracks(self, playlist_id):
        """Retrieve all track names for a single playlist, in playlist order."""
        if not self.sp:
            raise RuntimeError("Spotify client is not authenticated.")
        tracks = []
        results = self.sp.playlist_items(playlist_id)
        while results:
            for item in results['items']:
                track = item.get('track')
                if not track:
                    continue
                artists = ', '.join(artist['name'] for artist in track['artists'])
                tracks.append(track['name'] + ' - ' + artists)
            results = self.sp.next(results) if results['next'] else None
        return tracks

    def get_current_user_id(self):
        """Return the authenticated user's Spotify user ID."""
        if not self.sp:
            raise RuntimeError("Spotify client is not authenticated.")
        return self.sp.current_user()['id']

    def create_playlist(self, user_id, name, public=False, description=''):
        """Create a new, empty playlist for the given user and return the playlist object."""
        if not self.sp:
            raise RuntimeError("Spotify client is not authenticated.")
        return self.sp.user_playlist_create(user_id, name, public=public, description=description)

    def search_track(self, query):
        """Search Spotify for a track matching query; return its URI, or None if no match."""
        if not self.sp:
            raise RuntimeError("Spotify client is not authenticated.")
        results = self.sp.search(q=query, type='track', limit=1)
        items = results.get('tracks', {}).get('items', [])
        return items[0]['uri'] if items else None

    def add_tracks_to_playlist(self, playlist_id, track_uris):
        """Add track URIs to a playlist, batching in groups of 100 (the Spotify API limit)."""
        if not self.sp:
            raise RuntimeError("Spotify client is not authenticated.")
        for i in range(0, len(track_uris), 100):
            self.sp.playlist_add_items(playlist_id, track_uris[i:i + 100])

    def get_user_playlists(self, limit=50, offset=0):
        """Retrieve user's playlists from Spotify, with id/url/track count for each."""
        if not self.sp:
            raise RuntimeError("Spotify client is not authenticated.")
        playlists = []
        if limit < 1 or limit > 50:
            limit = 50

        try:
            results = self.sp.current_user_playlists(limit=limit, offset=offset)
            while results:
                for item in results['items']:
                    playlists.append({
                        'id': item['id'],
                        'name': item['name'],
                        'url': item['external_urls'].get(
                            'spotify', f"https://open.spotify.com/playlist/{item['id']}"
                        ),
                        'track_count': item['tracks']['total'],
                    })
                if results['next']:
                    results = self.sp.next(results)
                else:
                    break
            return playlists
        except SpotifyException as exc:
            print(f"Error fetching playlists: {exc}")
            return playlists


def process_arguments():
    """Parse command-line arguments for Spotify utility."""
    parser = argparse.ArgumentParser(description='Process arguments')
    parse = parser.add_argument

    parse('-a', '--all', action='store_true', help='Show all records')
    parse('-d', '--duplicates', action='store_true', help='Show duplicate records')
    parse('-p', '--playlists', action='store_true', help='Show user playlists')
    parse('-r', '--refresh', action='store_true', help='Refresh the cache')
    parse('--tracks', metavar='PLAYLIST',
          help='List all tracks on a playlist. '
               'PLAYLIST may be the number shown by -p, a playlist ID, or a name (substring match).')
    parse('--download', metavar='PLAYLIST',
          help='Download all tracks from a playlist via spotdl. '
               'PLAYLIST may be the number shown by -p, a playlist ID, or a name (substring match).')
    parse('--dest', metavar='DIR',
          help='Destination directory for --download (default: spotify.download_folder in '
               'config.toml, falling back to the current directory)')
    parse('--create-playlist', metavar='NAME',
          help="Create a new Spotify playlist named NAME from a text list of songs "
               "(one 'Title - Artist' or free-text search per line). Reads from --from-file, "
               "or stdin if that's omitted.")
    parse('--from-file', metavar='FILE',
          help='Song list file for --create-playlist; omit to read the list from stdin')
    parse('--public', action='store_true',
          help='Make the playlist created by --create-playlist public (default: private)')
    args, search_terms = parser.parse_known_args()
    return args, ' '.join(search_terms)


def load_cache(file_path):
    """Load liked songs from local JSON cache."""
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)
            time_ago = time_ago_in_words(os.path.getmtime(file_path))
            print(f"Loaded {len(data):,} Liked songs.\nCache last updated {time_ago} ago.")
            return data
    return None


def save_cache(file_path, data):
    """Save liked songs to local JSON cache."""
    with open(file_path, 'w', encoding='utf-8') as file:
        json.dump(data, file)


def _require_spotify_credentials():
    """Load Spotify credentials from config/env and validate them."""
    toml = load_rogkit_toml()
    spotify_config = toml.get('spotify', {})
    client_id = spotify_config.get('spotify_client_id') or os.getenv('SPOTIFY_CLIENT_ID')
    client_secret = spotify_config.get('spotify_client_secret') or os.getenv('SPOTIFY_CLIENT_SECRET')
    redirect_uri = spotify_config.get('spotify_redirect_uri') or os.getenv('SPOTIFY_REDIRECT_URI')

    missing = []
    if not client_id:
        missing.append("spotify_client_id")
    if not client_secret:
        missing.append("spotify_client_secret")
    if not redirect_uri:
        missing.append("spotify_redirect_uri")

    if missing:
        print("Missing Spotify configuration values:", ", ".join(missing))
        print(SPOTIFY_CONFIG_HELP)
        raise SystemExit(1)

    if redirect_uri.lower().startswith("http://") and not redirect_uri.lower().startswith("http://127.0.0.1") and not redirect_uri.lower().startswith("http://localhost"):
        print("Spotify requires HTTPS redirect URIs. Please update spotify_redirect_uri to use https.")
        print(SPOTIFY_CONFIG_HELP)
        raise SystemExit(1)

    return client_id, client_secret, redirect_uri


def get_playlist(args):
    """Get liked songs, refreshing cache if needed."""
    client_id, client_secret, redirect_uri = _require_spotify_credentials()

    user_home = os.path.expanduser('~')
    cache_path = os.path.join(user_home, '.spotify_cache')

    # Check if cache refresh is required
    if args.refresh or not os.path.exists(cache_path):
        print("Refreshing the cache...")
        client = SpotifyClient(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri
        )
        try:
            client.authenticate()
            liked_songs = client.get_liked_songs()
            save_cache(cache_path, liked_songs)
            print("Cache refreshed successfully.")
        except (SpotifyException, RuntimeError) as exc:
            print(f"Spotify Authentication Error: {exc}")
            raise SystemExit(1) from exc
    else:
        # Load from cache if it exists and refresh is not requested
        liked_songs = load_cache(cache_path)
        if liked_songs is None:
            print("Cache file is empty or corrupt. Please refresh the cache.")
            raise SystemExit(1)

    # Handle playlists only when explicitly requested
    if args.playlists:
        client = SpotifyClient(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri
        )
        try:
            client.authenticate()
            playlists = client.get_user_playlists()
            if not playlists:
                print("No playlists found.")
            else:
                for i, playlist in enumerate(playlists, start=1):
                    print(f"{i:>3}. {playlist['name']} ({playlist['track_count']:,} tracks)")
                print(f"Total playlists: {len(playlists):,}")
                print("Use --tracks <number|name|id> to list a playlist's tracks, "
                      "or --download <number|name|id> to download them via spotdl.")
        except (SpotifyException, RuntimeError) as exc:
            print(f"Error fetching playlists: {exc}")
        raise SystemExit(0)

    return liked_songs


def resolve_playlist(playlists, selector):
    """Resolve a --download selector (1-based index, playlist ID, or name substring).

    Returns the matching playlist dict, or None if nothing matched.
    Raises ValueError if a name substring matches more than one playlist.
    """
    selector = selector.strip()

    if selector.isdigit():
        idx = int(selector)
        if 1 <= idx <= len(playlists):
            return playlists[idx - 1]
        return None

    for playlist in playlists:
        if playlist['id'] == selector:
            return playlist

    matches = [p for p in playlists if selector.lower() in p['name'].lower()]
    if len(matches) > 1:
        names = ", ".join(p['name'] for p in matches)
        raise ValueError(f"Ambiguous playlist '{selector}' matches: {names}")
    return matches[0] if matches else None


def download_playlist(playlist, dest_dir):
    """Download every track in a playlist to dest_dir using spotdl."""
    spotdl_path = shutil.which('spotdl')
    if not spotdl_path:
        print(SPOTDL_INSTALL_HELP)
        raise SystemExit(1)

    dest_dir = Path(dest_dir).expanduser()
    dest_dir.mkdir(parents=True, exist_ok=True)

    print(f"Downloading '{playlist['name']}' ({playlist['track_count']:,} tracks) to {dest_dir}...")
    result = subprocess.run([spotdl_path, 'download', playlist['url']], cwd=dest_dir, check=False)
    if result.returncode != 0:
        print(f"spotdl exited with status {result.returncode}.")
        raise SystemExit(result.returncode)
    print("Download complete.")


def _authenticate_and_resolve_playlist(selector):
    """Authenticate, fetch the user's playlists, and resolve selector against them.

    Returns (client, playlist). Exits the process on auth/lookup failure or no match,
    shared by --tracks and --download so both fail the same way.
    """
    client_id, client_secret, redirect_uri = _require_spotify_credentials()
    client = SpotifyClient(client_id=client_id, client_secret=client_secret, redirect_uri=redirect_uri)

    try:
        client.authenticate()
        playlists = client.get_user_playlists()
    except (SpotifyException, RuntimeError) as exc:
        print(f"Error fetching playlists: {exc}")
        raise SystemExit(1) from exc

    try:
        playlist = resolve_playlist(playlists, selector)
    except ValueError as exc:
        print(exc)
        raise SystemExit(1) from exc

    if playlist is None:
        print(f"No playlist found matching '{selector}'. Use -p to list playlists.")
        raise SystemExit(1)

    return client, playlist


def _line_to_search_query(line):
    """Turn one input line into a Spotify search query, or None if the line is blank/a comment.

    Lines in the "Title - Artist" shape (what -a and --tracks print) get field-scoped
    so search precision matches that format; anything else is passed through as free text.
    """
    line = line.strip()
    if not line or line.startswith('#'):
        return None
    if ' - ' in line:
        title, artist = line.split(' - ', 1)
        return f"track:{title.strip()} artist:{artist.strip()}"
    return line


def read_song_list(from_file):
    """Read raw song-list lines from a file, or from stdin if from_file is None."""
    if from_file:
        path = Path(from_file).expanduser()
        if not path.exists():
            print(f"File not found: {path}")
            raise SystemExit(1)
        return path.read_text(encoding='utf-8').splitlines()

    if sys.stdin.isatty():
        print("No --from-file given and nothing piped on stdin. "
              "Provide a song list via --from-file or pipe one in.")
        raise SystemExit(1)
    return sys.stdin.read().splitlines()


def handle_create_playlist(args):
    """Search Spotify for each line of a song list and add matches to a new playlist."""
    lines = read_song_list(args.from_file)

    queries = [(line.strip(), query) for line in lines if (query := _line_to_search_query(line))]
    if not queries:
        print("No songs found in the input.")
        raise SystemExit(1)

    client_id, client_secret, redirect_uri = _require_spotify_credentials()
    client = SpotifyClient(client_id=client_id, client_secret=client_secret, redirect_uri=redirect_uri)
    try:
        client.authenticate()
        user_id = client.get_current_user_id()
    except (SpotifyException, RuntimeError) as exc:
        print(f"Error authenticating: {exc}")
        raise SystemExit(1) from exc

    track_uris = []
    unmatched = []
    for original, query in queries:
        try:
            uri = client.search_track(query)
        except SpotifyException as exc:
            print(f"Search failed for '{original}': {exc}")
            uri = None
        if uri:
            track_uris.append(uri)
        else:
            unmatched.append(original)

    if not track_uris:
        print("None of the songs could be matched on Spotify. No playlist created.")
        raise SystemExit(1)

    try:
        playlist = client.create_playlist(user_id, args.create_playlist, public=args.public)
        client.add_tracks_to_playlist(playlist['id'], track_uris)
    except SpotifyException as exc:
        print(f"Error creating playlist: {exc}")
        raise SystemExit(1) from exc

    playlist_url = playlist['external_urls'].get('spotify', playlist['id'])
    print(f"Created '{args.create_playlist}' with {len(track_uris):,} tracks: {playlist_url}")
    if unmatched:
        print(f"Could not match {len(unmatched):,} entries:")
        for line in unmatched:
            print(" ", line)


def handle_tracks(args):
    """Resolve --tracks's playlist selector and print every track on it."""
    client, playlist = _authenticate_and_resolve_playlist(args.tracks)

    try:
        tracks = client.get_playlist_tracks(playlist['id'])
    except (SpotifyException, RuntimeError) as exc:
        print(f"Error fetching tracks: {exc}")
        raise SystemExit(1) from exc

    print(f"'{playlist['name']}' ({len(tracks):,} tracks):")
    for i, track in enumerate(tracks, start=1):
        print(f"{i:>4}. {track}")


def handle_download(args):
    """Resolve --download's playlist selector and hand it off to spotdl."""
    _, playlist = _authenticate_and_resolve_playlist(args.download)

    toml = load_rogkit_toml()
    dest = args.dest or toml.get('spotify', {}).get('download_folder') or None
    dest_dir = Path(dest).expanduser() if dest else get_invoking_cwd()

    download_playlist(playlist, dest_dir)


def main():
    """CLI entry point for Spotify liked songs manager."""
    start_time = perf_counter()
    print("Rog's Spotify Playlist Utility")
    args, search_text = process_arguments()

    if args.create_playlist:
        handle_create_playlist(args)
        return

    if args.tracks:
        handle_tracks(args)
        return

    if args.download:
        handle_download(args)
        return

    liked_songs = get_playlist(args)

    if args.all:
        for song in liked_songs:
            print(song)
    elif search_text:
        matched = [song for song in liked_songs if search_text.lower() in song.lower()]
        if not matched:
            print(f"No matching songs found for '{search_text}' in the Liked playlist.")
        else:
            print(f"Found {len(matched):,} songs matching '{search_text}' in the Liked playlist:")
            for song in matched:
                print(" ", song)
    
    if args.duplicates:
        song_counts = Counter(liked_songs)
        duplicates = {song for song, count in song_counts.items() if count > 1}
        if len(duplicates) == 0:
            print("No duplicate songs found in the liked playist.")
        else:
            print(f"Duplicate songs: {len(duplicates):,}")
            for song in duplicates:
                print(song)
            
    # check if no arguments are given
    if not any(vars(args).values()):
        print("Use -r to refresh the cache, -d to check for duplicates,\nor text to search for something.")

    execution_time = perf_counter() - start_time
    if execution_time > 0.5:
        print(f"Execution time: {perf_counter() - start_time:.2f} seconds.")


if __name__ == '__main__':
    main()
