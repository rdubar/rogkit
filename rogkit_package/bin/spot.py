import os
from dataclasses import dataclass
from collections import Counter
from time import perf_counter
import argparse
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv
from ..bin.tomlr import load_rogkit_toml  # Assuming your tomlr loader function is here

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
    
def process_arguments():
    """
    Process command line arguments
    :return: args, search_text
    """
    parser = argparse.ArgumentParser(description='Process arguments')
    parse = parser.add_argument

    # Display options
    parse('-a', '--all', action='store_true', help='Show all records')
    args, search_terms = parser.parse_known_args()
    return args, ' '.join(search_terms)


def main():
    # Load the toml configuration file
    start_time = perf_counter()
    try:
        toml = load_rogkit_toml()  # Assuming this function returns the parsed TOML as a dictionary
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

    # Authenticate the user
    client.authenticate()
    
    args, search_text = process_arguments()
    
    print(f"Search text: {search_text}")

    # Fetch liked songs
    try:
        liked_songs = client.get_liked_songs()
    except Exception as e:
        print(f"Error fetching liked songs: {e}")
        exit(1)
    
    if args.all:
        [print(song) for song in liked_songs]
    elif search_text:
        matched = [song for song in liked_songs if search_text.lower() in song.lower()]
        if not matched:
            print(f"No matching songs found for '{search_text}'.")
        else:
            print(f"Found: {len(matched):,} songs from {len(liked_songs):,} liked songs matching:'{search_text}'")
            [print(song) for song in matched]

    print(f"Total liked songs: {len(liked_songs):,}")
        
    # Create a Counter object to count the occurrences of each song
    song_counts = Counter(liked_songs)

    # Get the duplicates by filtering songs that appear more than once
    duplicates = {song for song, count in song_counts.items() if count > 1}

    if len(duplicates) == 0:
        print("No duplicate songs found.")
    else:
        print(f"Duplicate songs: {len(duplicates):,}")
        [print(song) for song in duplicates]
        
    print(f"Execution time: {perf_counter() - start_time:.2f} seconds.")


if __name__ == '__main__':
    main()
