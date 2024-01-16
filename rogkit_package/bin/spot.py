import os
import base64
import argparse
import requests
from dataclasses import dataclass
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

@dataclass
class SpotifyClient:
    client_id: str
    client_secret: str
    redirect_uri: str
    scope: str = 'user-library-read'
    cache_path: str = ".spotify_cache"  # Path for caching the token

    def __post_init__(self):
        self.auth_manager = SpotifyOAuth(client_id=self.client_id,
                                         client_secret=self.client_secret,
                                         redirect_uri=self.redirect_uri,
                                         scope=self.scope,
                                         cache_path=self.cache_path)

    def authenticate(self):
        if not self.auth_manager.get_cached_token():
            print('Please open the following URL in your browser to authorize access:')
            print(self.auth_manager.get_authorize_url())

            try:
                response = input('Enter the URL you were redirected to: ')
                code = self.auth_manager.parse_response_code(response)
                self.auth_manager.get_access_token(code)
            except Exception as e:
                print(f"Error during authentication: {e}")
                exit(1)
        
        self.sp = spotipy.Spotify(auth_manager=self.auth_manager)

    def get_tracks_from_playlist(self, playlist_id):
        tracks = []
        results = self.sp.playlist_items(playlist_id)
        while results:
            for item in results['items']:
                track = item['track']
                tracks.append(track['name'] + ' - ' + track['artists'][0]['name'])
            results = self.sp.next(results)
        return tracks

    def get_liked_songs(self):
        tracks = []
        results = self.sp.current_user_saved_tracks()
        while results:
            for item in results['items']:
                track = item['track']
                tracks.append(track['name'] + ' - ' + track['artists'][0]['name'])
            results = self.sp.next(results)
        return tracks

    def refresh_token(self):
        url = "https://accounts.spotify.com/api/token"
        headers = {'Authorization': f'Basic {self.encoded_credentials}'}
        payload = {'grant_type': 'refresh_token', 'refresh_token': self.refresh_token}
        response = requests.post(url, headers=headers, data=payload)

        if response.status_code == 200:
            self.access_token = response.json()['access_token']
            print("New access token obtained:", self.access_token)
        else:
            raise Exception(f"Token refresh failed: {response.text}")
        
    def get_access_token(self, authorization_code):
        """Exchange the authorization code for an access token."""
        url = "https://accounts.spotify.com/api/token"
        headers = {'Authorization': f'Basic {self.encoded_credentials}'}
        data = {
            'grant_type': 'authorization_code',
            'code': authorization_code,
            'redirect_uri': self.redirect_uri
        }
        response = requests.post(url, headers=headers, data=data)
        if response.status_code == 200:
            self.access_token = response.json()['access_token']
            self.refresh_token = response.json().get('refresh_token')
            print("Access token obtained:", self.access_token)
            return self.access_token
        else:
            raise Exception(f"Failed to get access token: {response.text}")
        
def get_args():
    parser = argparse.ArgumentParser(description='Rog Kit Spotify Playlist Tool')
    parser.add_argument('-p', '--playlist', help='Playlist ID')
    parser.add_argument('-l', '--liked', action='store_true', help='Get liked songs')
    parser.add_argument('-d', '--duplicates', action='store_true', help='List duplicates')
    parser.add_argument('--list', action='store_true', help='List liked songs')
    return parser.parse_args()


# Function to get liked songs
def get_liked_songs(sp):
    tracks = []
    results = sp.current_user_saved_tracks()
    while results:
        for item in results['items']:
            track = item['track']
            tracks.append(track['name'] + ' - ' + track['artists'][0]['name'])
        results = sp.next(results)
    return tracks

def main():
    args = get_args()
    # Usage example

    print("Rog's Experimental Spotify Playlist Tool")
    try:
        client = SpotifyClient(
            client_id=os.getenv('SPOTIFY_CLIENT_ID'),
            client_secret=os.getenv('SPOTIFY_CLIENT_SECRET'),
            redirect_uri=os.getenv('SPOTIFY_REDIRECT_URI')
        )
    except Exception as e:
        print(f"Error creating Spotify client: {e}")
        exit(1)

    client.authenticate()
    liked_songs = client.get_liked_songs()

    print("Total songs in Liked Songs:", len(liked_songs))

    if args.duplicates:
        duplicates = set([song for song in liked_songs if liked_songs.count(song) > 1])
        if len(duplicates) > 0:
            print(f'Found {len(duplicates)} duplicates:')
            for song in duplicates:
                print(song)
        else:
            print('No duplicates found.')

    if args.list:
        for song in liked_songs:
            print(song)

if __name__ == '__main__':
    main()