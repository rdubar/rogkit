"""
Spotify liked songs manager.

CLI tool for viewing, searching, and managing Spotify liked songs with local caching.
Supports duplicate detection and playlist browsing. Configuration via rogkit config.toml.
"""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from dataclasses import dataclass, field
from time import perf_counter
from typing import Optional

from dotenv import load_dotenv
import spotipy  # type: ignore
from spotipy.oauth2 import SpotifyOAuth  # type: ignore
from spotipy.exceptions import SpotifyException  # type: ignore

from ..bin.tomlr import load_rogkit_toml
from .seconds import time_ago_in_words

# Load environment variables from .env file if present
load_dotenv()


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
    scope: str = 'user-library-read playlist-read-private playlist-read-collaborative'
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
        )

        token_info = auth_manager.get_cached_token()
        if token_info:
            print("Using cached Spotify token.")
        else:
            print('No cached token, launching Spotify authorization flow...')
            token = auth_manager.get_access_token()
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

    def get_user_playlists(self, limit=50, offset=0):
        """Retrieve user's playlists from Spotify."""
        if not self.sp:
            raise RuntimeError("Spotify client is not authenticated.")
        playlists = []
        if limit < 1 or limit > 50:
            limit = 50

        try:
            results = self.sp.current_user_playlists(limit=limit, offset=offset)
            while results:
                for item in results['items']:
                    playlists.append(item['name'])
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

    if redirect_uri.lower().startswith("http://"):
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
            for playlist in playlists:
                print(playlist)
            print(f"Total playlists: {len(playlists):,}")
        except (SpotifyException, RuntimeError) as exc:
            print(f"Error fetching playlists: {exc}")
        raise SystemExit(0)

    return liked_songs


def main():
    """CLI entry point for Spotify liked songs manager."""
    start_time = perf_counter()
    print("Rog's Spotify Playlist Utility")
    args, search_text = process_arguments()

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
