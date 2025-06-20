import os
import sys
import time
import argparse
import pickle
from dataclasses import dataclass
from typing import List
from pathlib import Path

from plexapi.server import PlexServer
from plexapi.exceptions import NotFound

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
CACHE_PICKLE_PATH = os.path.join(root_dir, 'plex_cache.pkl')


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
                    # "cast": [r.tag for r in getattr(item, "roles", [])],
                    "resolution": None,
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

        save_cache_data(data)

        size_kb = cache_file.stat().st_size / 1024
        elapsed_time = time.perf_counter() - start_time
        print(f"\nSaved {len(data):,} items to cache at {cache_file}")
        if total_seconds > 0:
            print(f"Total duration of cached items: {convert_seconds(total_seconds, long_format=True, show_seconds=True)}")
        if size_kb > 0:
            print(f"Cache file size: {byte_size(size_kb * 1024, base=1000)}")
        print(f"Cache operation completed in {elapsed_time:.2f} seconds.")


def save_cache_data(data):
    # Save as Pickle (for speed)
    with open(CACHE_PICKLE_PATH, "wb") as f:
        pickle.dump(data, f)

    print(f"Saved cache: {len(data)} items to .pkl")
    
def load_cache_data():
    if os.path.exists(CACHE_PICKLE_PATH):
        with open(CACHE_PICKLE_PATH, "rb") as f:
            return pickle.load(f)
    else:
        raise FileNotFoundError("No cache file found. Please run with --update.")


def search_cache(search_query):
    """Search the local Plex metadata cache for matching titles, resolution, or other metadata."""
    if not os.path.exists(CACHE_PICKLE_PATH):
        print("Cache file not found. Please generate it with --cache.")
        return []

    items = load_cache_data()

    query = search_query.lower()

    def matches_item(item):
        # Primary search fields (you can expand this list)
        fields = [
            item.get("title", ""),
            item.get("resolution", ""),
            item.get("summary", ""),
            item.get("file_path", ""),
            item.get("year", ""),
            # ' '.join(item.get("cast", [])),  # searchable cast names
        ]
        return any(query in str(val).lower() for val in fields if isinstance(val, str))

    matches = [item for item in items if matches_item(item)]

    return matches


def search_plex_live(plex_connection, search_query):
    """Search the live Plex server."""
    return plex_connection.search_plex(search_query)


def media_info(item, args=None):
    """Return formatted string with title, size, resolution, duration (hh:mm), and optional file path/info."""
    args = args or argparse.Namespace()
    show_path = getattr(args, "path", False)
    show_info = getattr(args, "info", False)
    title_length = getattr(args, "length", 50)

    size = item.get('file_size_bytes')
    resolution = item.get('resolution') or ""
    duration = item.get('duration_seconds')
    title = item.get('title', 'Unknown Title')
    year = item.get('year', None)
    disk = item.get('disk', '')
    path = item.get('file_path', None)
    disk = f'[{path[10]}]' if path and len(path) > 10 else ''
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
    size_str = byte_size(size) if size is not None else ""

    # Crop and pad title
    if len(title) > title_length:
        title_display = title[:title_length - 1] + "…"
    else:
        title_display = title.ljust(title_length)

    result = f"{title_display}  {size_str:>9}  {resolution:<5}  {h_m_string} {disk}"
    
    if show_info:
        result = result + f"\n  {item.get('summary', '')}"
        
    if show_path:
        result = result + f"\n  {item.get('file_path', '')}"
    
    return result


def main():
    print("Rog's Plex Media Tool")
    
    default_number = 10
    default_max_length = 45

    parser = argparse.ArgumentParser(description="Search or manage your Plex library.")
    general_group = parser.add_argument_group('General Settings')
    action_group = parser.add_argument_group('Action Settings')
    server_group = parser.add_argument_group('Server Settings') 

    general_group.add_argument('search', nargs='*', help="Search string for media titles")
    general_group.add_argument('-a', '--all', action='store_true', help="Show all media items")
    general_group.add_argument('-i', '--info', action='store_true', help="Show media information")
    general_group.add_argument('-p', '--path', action='store_true', help="Show media path")
    general_group.add_argument('-u', '--update', action='store_true', help="Update the local metadata cache")
    general_group.add_argument('-y', '--year', action='store_true', help="Sort by year")
    general_group.add_argument('-l', '--length', type=int, default=default_max_length, help="Set title length for display (default: {default_max_length})")
    general_group.add_argument('-n', '--number', type=int, default=default_number, help=f"Show N items (default: {default_number})")
    general_group.add_argument('-r', '--reverse', action='store_true', help="Reverse the order of results")
    general_group.add_argument('-z', '--zed', action='store_true', help="Sort by year and show all")
    server_group.add_argument('--live', action='store_true', help="Search directly on Plex server instead of using cache")
    server_group.add_argument('--server', default=PLEX_SERVER_URL, help="Plex server URL")
    server_group.add_argument('--token', default=PLEX_SERVER_TOKEN, help="Plex server token")
    server_group.add_argument('--port', default=PLEX_SERVER_PORT, help="Plex server port (default: 32400)")

    action_group.add_argument('-w', '--watched', action='store_true', help="Mark search results as watched (live only)")

    args = parser.parse_args()
    search_query = ' '.join(args.search) if args.search else None

    # Handle cache update
    cache_missing = not os.path.exists(CACHE_PICKLE_PATH)
    if args.update or cache_missing:
        print("Updating Plex metadata cache..." if args.update else "Cache file not found. Generating cache...")
        plex_connection = PlexConnection(args.server, args.token, args.port)
        plex_connection.save_cache(cache_path=CACHE_PICKLE_PATH, include_file_size=True)
        return

    # Load cache
    all_items = load_cache_data()

    total_items = len(all_items)

    # Show cache age
    cache_age_seconds = time.time() - os.path.getmtime(CACHE_PICKLE_PATH)
    print(f"Cache last updated {convert_seconds(cache_age_seconds, long_format=True, show_seconds=True)} ago.")

    # No search = show last N added
    if not search_query:
        print(f"\nShowing last {args.number} items added of {total_items:,} on the Plex server:")
        items_with_dates = [item for item in all_items if item.get("added_at")]
        recent_items = sorted(items_with_dates, key=lambda x: x["added_at"], reverse=True)[:args.number]

        for item in recent_items:
            print("  " + media_info(item, args=args))
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
    
    if args.zed:
        args.year = True
        args.all = True

    if args.all:
        args.number = len(results)

    if args.year:
        results = sorted(results, key=lambda x: x.get('year') or 0, reverse=not args.reverse)
    elif args.reverse:
        results = list(reversed(results))

    match_str = "match" if len(results) == 1 else "matches"
    showing_count = len(results) if args.all else min(args.number, len(results))
    number_str = "all" if args.all or showing_count == len(results) else f"{showing_count:,} of"
    print(f"Showing {number_str} {len(results):,} {match_str} for '{search_query}' in {total_items:,} items:")
    for item in results[:args.number]:
        if isinstance(item, dict):
            print("  " + media_info(item, args=args))
        else:
            # Live PlexAPI fallback
            title = getattr(item, 'title', 'Unknown Title')
            year = getattr(item, 'year', 'N/A')
            print(f"  - {title} ({year})")
    if number := len(results) > args.number:
        print(f"  ...and {len(results) - args.number:,} more results.")

    if args.watched:
        if args.live:
            plex_connection.mark_as_watched(results)
        else:
            print("Marking as watched requires --live mode.")


if __name__ == "__main__":
    start_time = time.perf_counter()
    main()
    elapsed_time = time.perf_counter() - start_time
    print(f"\nOperation completed in {elapsed_time:.5f} seconds.")