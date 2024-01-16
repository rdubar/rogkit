import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()


# Set your Spotify API credentials from the .env file
CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')
REDIRECT_URI = os.getenv('SPOTIFY_REDIRECT_URI')
SCOPE = os.getenv('SPOTIFY_SCOPE')

# Authenticate with Spotify
try:
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id=CLIENT_ID,
                                                   client_secret=CLIENT_SECRET,
                                                   redirect_uri=REDIRECT_URI,
                                                   scope=SCOPE))
except Exception as e:
    print(f"Error authenticating with Spotify: {e}")
    exit(1)

# Function to get track names from a playlist
def get_tracks_from_playlist(playlist_id):
    tracks = []
    results = sp.playlist_items(playlist_id)
    while results:
        for item in results['items']:
            track = item['track']
            tracks.append(track['name'] + ' - ' + track['artists'][0]['name'])
        results = sp.next(results)
    return tracks

def get_liked_songs():
    tracks = []
    results = sp.current_user_saved_tracks()
    while results:
        for item in results['items']:
            track = item['track']
            tracks.append(track['name'] + ' - ' + track['artists'][0]['name'])
        results = sp.next(results)
    return tracks

print("Rog's Experimental Spotify Playlist Duplicator")

# Get liked songs
try:
    liked_songs = get_liked_songs()
except Exception as e:
    print(f"Error fetching liked songs: {e}")
    exit(1)

# Find duplicates
duplicates = set([song for song in liked_songs if liked_songs.count(song) > 1])

print("Duplicated songs in Liked Songs:", duplicates)