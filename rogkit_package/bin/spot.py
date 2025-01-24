import os
import json
from dataclasses import dataclass
from collections import Counter
from time import perf_counter
import argparse

from dotenv import load_dotenv
import spotipy

from ..bin.tomlr import load_rogkit_toml
from .seconds import time_ago_in_words

# Load environment variables from .env file if needed
load_dotenv()

@dataclass
class SpotifyClient:
    client_id: str
    client_secret: str
    redirect_uri: str
    scope: str = 'user-library-read'
    cache_path: str = ".spotify_cache"
    sp: spotipy.Spotify = None

    def authenticate(self):
        from spotipy.oauth2 import SpotifyOAuth  # Import only when needed
        auth_manager = SpotifyOAuth(
            client_id=self.client_id,
            client_secret=self.client_secret,
            redirect_uri=self.redirect_uri,
            scope=self.scope,
            cache_path=self.cache_path
        )
        if not auth_manager.get_cached_token():
            print('No cached token, proceeding with user authentication...')
            token_info = auth_manager.get_access_token(as_dict=True)
            print(f"Authentication successful, access token: {token_info['access_token']}")
        self.sp = spotipy.Spotify(auth_manager=auth_manager)
        print("Spotify client authenticated successfully.")

    def get_liked_songs(self):
        if not self.sp:
            raise Exception("Spotify client is not authenticated.")
        tracks = []
        results = self.sp.current_user_saved_tracks()
        while results:
            for item in results['items']:
                track = item['track']
                tracks.append(track['name'] + ' - ' + track['artists'][0]['name'])
            results = self.sp.next(results)
        return tracks

    def get_user_playlists(self, limit=50, offset=0):
        if not self.sp:
            raise Exception("Spotify client is not authenticated.")
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
        except Exception as e:
            print(f"Error fetching playlists: {e}")
            return playlists


def process_arguments():
    parser = argparse.ArgumentParser(description='Process arguments')
    parse = parser.add_argument

    parse('-a', '--all', action='store_true', help='Show all records')
    parse('-d', '--duplicates', action='store_true', help='Show duplicate records')
    parse('-p', '--playlists', action='store_true', help='Show user playlists')
    parse('-r', '--refresh', action='store_true', help='Refresh the cache')
    args, search_terms = parser.parse_known_args()
    return args, ' '.join(search_terms)


def load_cache(file_path):
    if os.path.exists(file_path):
        with open(file_path, 'r') as file:
            data = json.load(file)
            time_ago = time_ago_in_words(os.path.getmtime(file_path))
            print(f"Loaded {len(data):,} Liked songs.\nCache last updated {time_ago} ago.")
            return data
    return None


def save_cache(file_path, data):
    with open(file_path, 'w') as file:
        json.dump(data, file)


def get_playlist(args, search_text):
    start_time = perf_counter()
    try:
        toml = load_rogkit_toml()
        spotify_config = toml.get('spotify', {})
    except Exception as e:
        print(f"Error loading configuration from toml: {e}")
        exit(1)

    client_id = spotify_config.get('spotify_client_id', '') or os.getenv('SPOTIFY_CLIENT_ID')
    client_secret = spotify_config.get('spotify_client_secret', '') or os.getenv('SPOTIFY_CLIENT_SECRET')
    redirect_uri = spotify_config.get('spotify_redirect_uri', '') or os.getenv('SPOTIFY_REDIRECT_URI', "http://localhost:8888/callback/")

    if not client_id or not client_secret or not redirect_uri:
        print("Missing Spotify credentials in the configuration. Please check your config.toml file.")
        exit(1)

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
        except Exception as e:
            print(f"Spotify Authentication Error: {e}")
            exit(1)
    else:
        # Load from cache if it exists and refresh is not requested
        liked_songs = load_cache(cache_path)
        if liked_songs is None:
            print("Cache file is empty or corrupt. Please refresh the cache.")
            exit(1)

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
            [print(playlist) for playlist in playlists]
            print(f"Total playlists: {len(playlists):,}")
        except Exception as e:
            print(f"Error fetching playlists: {e}")
        exit(0)

    return liked_songs


def main():
    start_time = perf_counter()
    print("Rog's Spotify Playlist Utility")
    args, search_text = process_arguments()

    liked_songs = get_playlist(args, search_text)

    if args.all:
        [print(song) for song in liked_songs]
    elif search_text:
        matched = [song for song in liked_songs if search_text.lower() in song.lower()]
        if not matched:
            print(f"No matching songs found for '{search_text}' in the Liked playlist.")
        else:
            print(f"Found {len(matched):,} songs matching '{search_text}' in the Liked playlist:")
            [print(" ",song) for song in matched]
    
    if args.duplicates:
        song_counts = Counter(liked_songs)
        duplicates = {song for song, count in song_counts.items() if count > 1}
        if len(duplicates) == 0:
            print("No duplicate songs found in the liked playist.")
        else:
            print(f"Duplicate songs: {len(duplicates):,}")
            [print(song) for song in duplicates]
            
    # check if no arguments are given
    if not any(vars(args).values()):
        print("Use -r to refresh the cache, -d to check for duplicates,\nor text to search for something.")

    execution_time = perf_counter() - start_time
    if execution_time > 0.5:
        print(f"Execution time: {perf_counter() - start_time:.2f} seconds.")


if __name__ == '__main__':
    main()
