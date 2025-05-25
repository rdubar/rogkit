import argparse
from plexapi.server import PlexServer
from plexapi.exceptions import NotFound
import sys
from dataclasses import dataclass
from typing import List
import time
from pathlib import Path
import json
import os

from ..settings import root_dir
from ..bin.tomlr import load_rogkit_toml
from ..bin.seconds import convert_seconds
from ..bin.bytes import byte_size

# Load the configuration from TOML file
TOML = load_rogkit_toml()
PLEX_SERVER_URL = TOML.get('plex', {}).get('plex_server_url', None)
PLEX_SERVER_TOKEN = TOML.get('plex', {}).get('plex_server_token', None)
PLEX_SERVER_PORT = TOML.get('plex', {}).get('plex_server_port', 32400)

# put the cache file in the rogkit package directory
CACHE_PATH = os.path.join(root_dir, 'plex_cache.json')


@dataclass
class PlexConnection:
    """Dataclass to manage Plex connection and operations."""
    server_url: str
    token: str
    port: int
    plex: PlexServer = None
    user = None

    def __post_init__(self):
        """Construct the full Plex server URL and connect."""
        self.server_url = self.construct_plex_url()
        self.connect_to_plex()

    def construct_plex_url(self):
        """Ensure we are using a full URL (with http/https) and port."""
        if self.server_url:
            if 'http' not in self.server_url:
                self.server_url = f"http://{self.server_url}:{self.port}"  # Default to http if no scheme present
            elif ':' not in self.server_url:
                self.server_url = f"{self.server_url}:{self.port}"  # Append port if no port is present
        return self.server_url

    def connect_to_plex(self):
        """Connect to Plex Server using URL and token."""
        try:
            self.plex = PlexServer(self.server_url, self.token)
            self.user = self.plex.myPlexAccount()  # Get the current user from Plex account
            print(f"Connected to {self.server_url} as {self.user.username}")  # Optional: Print the current user's username
        except Exception as e:
            print(f"Error connecting to Plex {self.server_url}: {e}")
            sys.exit(1)

    def search_plex(self, search_query):
        """Search Plex for media titles matching the search query."""
        try:
            results = self.plex.library.search(search_query)
            return results
        except NotFound:
            print(f"No results found for '{search_query}'.")
            return []

    def mark_as_watched(self, results):
        """Mark all episodes of the same series and season as watched in Plex."""
        print('Results to mark as watched:', len(results))  # Show the number of results being processed
        for result in results:
            try:
                # Debug: Show the result type
                print(f"Processing: {result.title} ({result.type})")
                
                # Check if it's an episode
                if result.type == 'episode':
                    show = result.show()  # Get the show
                    season = result.season()  # Get the season
                    
                    # Fetch all episodes in the same season
                    episodes = show.episodes(season=season.index)
                    
                    # Debug: Show how many episodes we are marking
                    print(f"Found {len(episodes)} episodes in season {season.index} of '{show.title}'.")

                    # Mark each episode as watched
                    for episode in episodes:
                        if not episode.isWatched:
                            episode.markWatched(user=self.user)
                            print(f"Marked '{episode.title}' as watched.")
                        else:
                            print(f"'{episode.title}' is already marked as watched.")

                # If it's not an episode, check if it's a movie
                elif result.type == 'movie':
                    if not result.isWatched:
                        result.markWatched(user=self.user)
                        print(f"Marked movie '{result.title}' as watched.")
                    else:
                        print(f"Movie '{result.title}' is already marked as watched.")
                        
                # Check if it's a show (this happens when it's a full series)
                elif result.type == 'show':
                    # Get all episodes of the show
                    episodes = result.episodes()
                    print(f"Found {len(episodes)} episodes in '{result.title}' (show).")
                    
                    # Mark all episodes of the show as watched
                    for episode in episodes:
                        if not episode.isWatched:
                            episode.markWatched(user=self.user)
                            print(f"Marked '{episode.title}' as watched.")
                        else:
                            print(f"'{episode.title}' is already marked as watched.")

                else:
                    print(f"Skipping unsupported type: {result.type}")

                # Force refresh of the library after marking as watched
                result.reload()  # Reload the result to ensure Plex updates its state

            except Exception as e:
                print(f"Could not mark '{result.title}' as watched: {e}")
                
    def save_cache(self, cache_path="~/.rogkit/plex_cache.json", include_file_size=True, debug=False):
        """Fetch full Plex library metadata and save to local cache file."""
        start_time = time.perf_counter()

        cache_file = Path(cache_path).expanduser()
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        data = []
        total_seconds = 0 

        for section in self.plex.library.sections():
            if section.type not in ["movie", "show", "artist", "album", "track"]:
                continue  # Skip unsupported types

            print(f"Caching section: {section.title} ({section.type})")
            items = section.all()

            for item in items:
                duration = item.duration // 1000 if hasattr(item, "duration") and item.duration else None
                entry = {
                    "title": item.title,
                    "year": getattr(item, "year", None),
                    "type": item.TYPE,
                    "watched": getattr(item, "isWatched", False),
                    "duration_seconds": duration,
                    "summary": getattr(item, "summary", ""),
                    "file_path": None,
                    "file_size_bytes": None,
                    "added_at": getattr(item, "addedAt", None).timestamp() if getattr(item, "addedAt", None) else None,
                    "cast": [r.tag for r in getattr(item, "roles", [])],
                    "resolution": None
                }

                if hasattr(item, "media") and item.media:
                    try:
                        media = item.media[0]
                        media_part = media.parts[0]
                        entry["file_path"] = getattr(media_part, "file", None)

                        if include_file_size:
                            entry["file_size_bytes"] = getattr(media_part, "size", None)

                        # Add resolution
                        raw_res = getattr(media, "videoResolution", None)
                        if raw_res:
                            normalized = str(raw_res).lower()
                            if normalized == "sd":
                                entry["resolution"] = "SD"
                            elif normalized in {"480", "576", "720", "1080", "4k"}:
                                entry["resolution"] = normalized.lower()
                            else:
                                if debug: 
                                    print(f"  [!] Unrecognized resolution '{raw_res}' for '{item.title}'")
                                entry["resolution"] = normalized  # catch-all fallback

                    except Exception as e:
                        print(f"  [!] Media access error for '{item.title}': {e}")
                        continue

                # Add to final data list
                data.append(entry)
                if duration:
                    total_seconds += duration

        # Write to JSON file
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        size_kb = cache_file.stat().st_size / 1024
        elapsed_time = time.perf_counter() - start_time
        print(f"\nSaved {len(data):,} items to cache at {cache_file}")
        if total_seconds > 0:
            print(f"Total duration of cached items: {convert_seconds(total_seconds, long_format=True, show_seconds=True)}")
        if size_kb > 0:
            print(f"Cache file size: {byte_size(size_kb * 1024, base=1000)}")
        print(f"Cache operation completed in {elapsed_time:.2f} seconds.")


def search_cache(search_query):
    """Search the local Plex metadata cache for matching titles, resolution, or other metadata."""
    if not os.path.exists(CACHE_PATH):
        print("Cache file not found. Please generate it with --cache.")
        return []

    with open(CACHE_PATH, encoding='utf-8') as f:
        items = json.load(f)

    query = search_query.lower()

    def matches_item(item):
        # Primary search fields (you can expand this list)
        fields = [
            item.get("title", ""),
            item.get("resolution", ""),
            item.get("summary", ""),
            item.get("file_path", ""),
            item.get("year", ""),
            ' '.join(item.get("cast", [])),  # New: searchable cast names
        ]
        return any(query in str(val).lower() for val in fields if isinstance(val, str))

    matches = [item for item in items if matches_item(item)]

    return matches


def search_plex_live(plex_connection, search_query):
    """Search the live Plex server."""
    return plex_connection.search_plex(search_query)


def media_info(item, length=40):
    """Return formatted string with title, size, resolution, and duration (hh:mm)."""
    size = item.get('file_size_bytes')
    resolution = item.get('resolution') or "??"
    duration = item.get('duration_seconds')
    title = item.get('title', 'Unknown Title')
    year = item.get('year', None)
    if year:
        title += f" ({year})"

    # Format duration
    if duration:
        hours = duration // 3600
        minutes = (duration % 3600) // 60
        h_m_string = f"{hours:02}:{minutes:02}"
    else:
        h_m_string = ""

    # Format size
    size_str = byte_size(size) if size is not None else "??"

    # Crop and pad title
    if len(title) > length:
        title_display = title[:length - 1] + "…"
    else:
        title_display = title.ljust(length)

    return f"{title_display}  {size_str:>9}  {resolution:<5}  {h_m_string}"


def main():
    print("Plex Media Search and Mark as Watched Tool")

    parser = argparse.ArgumentParser(description="Search or manage your Plex library.")
    general_group = parser.add_argument_group('General Settings')
    action_group = parser.add_argument_group('Action Settings')

    general_group.add_argument('search', nargs='*', help="Search string for media titles")
    general_group.add_argument('-c', '--cache', action='store_true', help="Regenerate the local metadata cache")
    general_group.add_argument('--live', action='store_true', help="Search directly on Plex server instead of using cache")
    general_group.add_argument('-s', '--server', default=PLEX_SERVER_URL, help="Plex server URL")
    general_group.add_argument('-t', '--token', default=PLEX_SERVER_TOKEN, help="Plex server token")
    general_group.add_argument('-p', '--port', default=PLEX_SERVER_PORT, help="Plex server port (default: 32400)")
    general_group.add_argument('--number', '-n', type=int, default=10, help="Show N most recently added items if no search is given")

    action_group.add_argument('-w', '--watched', action='store_true', help="Mark search results as watched (live only)")

    args = parser.parse_args()
    search_query = ' '.join(args.search) if args.search else None

    # Handle cache generation
    if args.cache or not os.path.exists(CACHE_PATH):
        if not args.cache:
            print("Cache file not found. Generating cache...")
        else:
            print("Regenerating Plex metadata cache...")

        plex_connection = PlexConnection(args.server, args.token, args.port)
        plex_connection.save_cache(cache_path=CACHE_PATH, include_file_size=True)
        return

    # Show cache age
    if os.path.exists(CACHE_PATH):
        cache_age_seconds = time.time() - os.path.getmtime(CACHE_PATH)
        print(f"Cache file age: {convert_seconds(cache_age_seconds, long_format=True, show_seconds=True)}")

    # If no search query is provided, show the last N items added to Plex
    if not search_query:
        print(f"\nShowing last {args.number} items added to Plex:")

        if not os.path.exists(CACHE_PATH):
            print("Cache is missing. Please run with --cache first.")
            sys.exit(1)

        with open(CACHE_PATH, encoding='utf-8') as f:
            items = json.load(f)

        items_with_dates = [item for item in items if item.get("added_at")]
        recent_items = sorted(items_with_dates, key=lambda x: x["added_at"], reverse=True)[:args.number]

        for item in recent_items:
            added_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(item["added_at"]))
            print(f"    {media_info(item)}")
        return

    # Perform search
    if args.live:
        plex_connection = PlexConnection(args.server, args.token, args.port)
        results = search_plex_live(plex_connection, search_query)
    else:
        results = search_cache(search_query)

    if not results:
        print("No matches found.")
        return

    print(f"\nFound {len(results)} match(es) for '{search_query}':")
    for item in results:
        if isinstance(item, dict):
            print("  " + media_info(item, length=40))
        else:
            # Live PlexAPI item — fallback to basic info
            title = getattr(item, 'title', 'Unknown Title')
            year = getattr(item, 'year', 'N/A')
            print(f"  - {title} ({year})")

    # Mark watched (only in live mode)
    if args.watched:
        if args.live:
            plex_connection.mark_as_watched(results)
        else:
            print("Marking as watched requires --live mode.")


if __name__ == "__main__":
    main()