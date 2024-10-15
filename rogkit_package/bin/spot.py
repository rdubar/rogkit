import os
from dataclasses import dataclass
from collections import Counter
from time import perf_counter
import argparse

from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyOAuth

from ..bin.tomlr import load_rogkit_toml

# Load environment variables from .env file if needed
load_dotenv()

@dataclass
class SpotifyClient:
    client_id: str
    client_secret: str
    redirect_uri: str
    scope: str = 'user-library-read'
    cache_path: str = ".spotify_cache"

    def __post_init__(self):
        self.auth_manager = SpotifyOAuth(
            client_id=self.client_id,
            client_secret=self.client_secret,
            redirect_uri=self.redirect_uri,
            scope=self.scope,
            cache_path=self.cache_path
        )

    def authenticate(self):
        if not self.auth_manager.get_cached_token():
            print('No cached token, proceeding with user authentication...')
            # SpotifyOAuth will automatically handle the callback via a local server
            # Ensure token_info is returned as a dictionary
            token_info = self.auth_manager.get_access_token(as_dict=True)
            print(f"Authentication successful, access token: {token_info['access_token']}")
        
        self.sp = spotipy.Spotify(auth_manager=self.auth_manager)
        print("Spotify client authenticated successfully.")

    def get_liked_songs(self):
        tracks = []
        results = self.sp.current_user_saved_tracks()
        while results:
            for item in results['items']:
                track = item['track']
                tracks.append(track['name'] + ' - ' + track['artists'][0]['name'])
            results = self.sp.next(results)
        return tracks
    
    # Get user playlists
    def get_user_playlists(self, limit=50, offset=0):
        print("Fetching user playlists... This is not working.")
        playlists = []
        
        # Validate limit (must be between 1 and 50 according to the API)
        if limit < 1 or limit > 50:
            limit = 50  # Default to 50 if an invalid limit is passed

        try:
            # Fetch playlists with a valid limit and offset
            results = self.sp.current_user_playlists(limit=limit, offset=offset)
            print(f"New User playlist results: {results}")
            
            # If the total is 0, it means the user has no playlists
            if results['total'] == 0:
                print("No playlists found or limit is set to 0.")
                return playlists

            # Fetch playlists and handle pagination
            while results:
                for item in results['items']:
                    playlists.append(item['name'])  # Append the playlist name
                if results['next']:
                    results = self.sp.next(results)  # Fetch next batch of playlists (if available)
                else:
                    break
            return playlists
        except Exception as e:
            print(f"Error fetching playlists: {e}")
            return playlists

    # Create a new playlist
    def create_playlist(self, name, description="My new playlist", public=False):
        user_id = self.sp.me()['id']  # Get the current user's ID
        playlist = self.sp.user_playlist_create(user=user_id, name=name, public=public, description=description)
        print(f"Playlist '{name}' created successfully!")
        return playlist
    
def process_arguments():
    """
    Process command line arguments
    :return: args, search_text
    """
    parser = argparse.ArgumentParser(description='Process arguments')
    parse = parser.add_argument

    # Display options
    parse('-a', '--all', action='store_true', help='Show all records')
    parse('-p', '--playlists', action='store_true', help='Show user playlists')
    args, search_terms = parser.parse_known_args()
    return args, ' '.join(search_terms)


def main():
    # Load the toml configuration file
    start_time = perf_counter()
    try:
        toml = load_rogkit_toml()  # returns the parsed TOML as a dictionary
        spotify_config = toml.get('spotify', {})
    except Exception as e:
        print(f"Error loading configuration from toml: {e}")
        exit(1)

    # Extract credentials from the toml config or environment variables
    client_id = spotify_config.get('spotify_client_id', '') or os.getenv('SPOTIFY_CLIENT_ID')
    client_secret = spotify_config.get('spotify_client_secret', '') or os.getenv('SPOTIFY_CLIENT_SECRET')
    redirect_uri = spotify_config.get('spotify_redirect_uri', '') or os.getenv('SPOTIFY_REDIRECT_URI', "http://localhost:8888/callback/")

    if not client_id or not client_secret or not redirect_uri:
        print("Missing Spotify credentials in the configuration. Please check your config.toml file.")
        exit(1)

    # Create the SpotifyClient object
    client = SpotifyClient(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri
    )

    # Connect to Spotify
    try:
        client.authenticate()
    except Exception as e:
        print(f"Spotify Authetication Error: {e}")
        exit(1)

    args, search_text = process_arguments()
    
    if args.playlists:
        playlists = client.get_user_playlists()
        [print(playlist) for playlist in playlists]
        print(f"Total playlists: {len(playlists):,}")
        exit(0)
    
    liked_songs = client.get_liked_songs()

    if args.all:
        [print(song) for song in liked_songs]
    elif search_text:
        matched = [song for song in liked_songs if search_text.lower() in song.lower()]
        if not matched:
            print(f"No matching songs found for '{search_text}'.")
            print(f"Total liked songs: {len(liked_songs):,}")
        
        else:
            print(f"Found: {len(matched):,} songs from {len(liked_songs):,} liked songs matching:'{search_text}'")
            [print(song) for song in matched]

    # Look for duplicates in the liked songs
    song_counts = Counter(liked_songs)
    duplicates = {song for song, count in song_counts.items() if count > 1}
    if len(duplicates) == 0:
        print("No duplicate songs found.")
    else:
        print(f"Duplicate songs: {len(duplicates):,}")
        [print(song) for song in duplicates]
        
    print(f"Execution time: {perf_counter() - start_time:.2f} seconds.")


if __name__ == '__main__':
    main()
