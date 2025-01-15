import os
import sys
import json
import subprocess
import paramiko
import urllib.parse

# Configuration
REMOTE_USER = "rog"
REMOTE_HOST = "192.168.0.50"
SSH_PORT = 22
LOCAL_PLAY_CMD = "/Applications/VLC.app/Contents/MacOS/VLC"  # Command to play video locally (e.g., 'vlc', 'mpv')
script_dir = os.path.dirname(os.path.abspath(__file__))
CACHE_FILE = os.path.join(script_dir, "media_files_cache.json")

def load_cache():
    """Load the media files cache."""
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    return {}

def save_cache(cache):
    """Save the media files cache."""
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f)

def play_local(filepath):
    """Play the video locally."""
    print(f"Playing locally: {filepath}")
    subprocess.run([LOCAL_PLAY_CMD, filepath])

def play_from_remote(filepath):
    """Stream a file from the remote system and play it locally using VLC's sftp module."""
    vlc_command = "/Applications/VLC.app/Contents/MacOS/VLC"
    
    # Encode the file path to handle spaces and special characters
    encoded_path = urllib.parse.quote(filepath)
    sftp_url = f"sftp://{REMOTE_USER}@{REMOTE_HOST}{encoded_path}"
    
    print(f"Streaming remote file via SFTP: {sftp_url}")
    
    try:
        # Launch VLC with the SFTP URL
        subprocess.run(
            [vlc_command, sftp_url],
            check=True
        )
    except subprocess.CalledProcessError as e:
        print(f"Failed to stream the file: {e}")

def search_and_play(title):
    """Search for a video by title and play it."""
    # Load the cache
    cache = load_cache()

    # Check if the cache contains valid data
    if not isinstance(cache, list):
        print("Cache is not in the expected format.")
        return

    # Search for matching files
    lower = title.lower()
    matching_files = [entry for entry in cache if lower in entry['title'].lower() and entry['filetype'] in ["mp4", "mkv", "avi"]]
    
    if not matching_files:
        print(f"No matching files found for title: {title}")
        return

    if len(matching_files) == 1:
        selected_file = matching_files[0]
    else:
        # Display matching files to the user
        print("Matching files:")
        for idx, entry in enumerate(matching_files, start=1):
            print(f"{idx}: {entry['title']} - {entry['filename']} ({entry['filetype']})")
            print(f"    Location: {entry['location']}")
            print(f"    Path: {entry['filepath']}")
            print(f"    Disk: {entry['disk']}")
            print(f"    Size: {entry['filesize']} bytes")
    
        # Let the user choose a file
        choice = input("Enter the number of the file to play: ").strip()
        if not choice.isdigit() or int(choice) < 1 or int(choice) > len(matching_files):
            print("Invalid choice.")
            return

        selected_file = matching_files[int(choice) - 1]

    # Check if the file is local or remote based on its filepath
    filepath = selected_file['filepath']
    if os.path.exists(filepath):
        # File is local
        play_local(filepath)
    else:
        # File is remote
        play_from_remote(filepath)



def main():
    print("Roger's Experimental Media Player (not yet working)")
    title = " ".join(sys.argv[1:])
    if not title:
        print("Usage: media_play.py <title>")
        sys.exit(1)
        
    search_and_play(title)

if __name__ == "__main__":
    main()