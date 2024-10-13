import os
from dataclasses import dataclass
from collections import Counter
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


def main():
    # Load the toml configuration file
    try:
        toml = load_rogkit_toml()  # Assuming this function returns the parsed TOML as a dictionary
        spotify_config = toml.get('spotify', {})
    except Exception as e:
        print(f"Error loading configuration from toml: {e}")
        exit(1)

    # Extract credentials from the toml config
    client_id = spotify_config.get('spotify_client_id', '')
    client_secret = spotify_config.get('spotify_client_secret', '')
    redirect_uri = spotify_config.get('spotify_redirect_uri', '') or "http://localhost:8888/callback/"

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

    # Fetch liked songs
    liked_songs = client.get_liked_songs()
    print("Total liked songs:", len(liked_songs))
        
    # Create a Counter object to count the occurrences of each song
    song_counts = Counter(liked_songs)

    # Get the duplicates by filtering songs that appear more than once
    duplicates = {song for song, count in song_counts.items() if count > 1}

    print("Duplicate songs:", len(duplicates))
    for song in duplicates:
        print(song)


if __name__ == '__main__':
    main()
