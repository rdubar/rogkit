import argparse
from plexapi.server import PlexServer
from plexapi.exceptions import NotFound
import sys
from dataclasses import dataclass
from typing import List

from ..bin.tomlr import load_rogkit_toml


# Load the configuration from TOML file
TOML = load_rogkit_toml()
PLEX_SERVER_URL = TOML.get('plex', {}).get('plex_server_url', None)
PLEX_SERVER_TOKEN = TOML.get('plex', {}).get('plex_server_token', None)
PLEX_SERVER_PORT = TOML.get('plex', {}).get('plex_server_port', 32400)


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


def main():
    print("Plex Media Search and Mark as Watched Tool")
    
    # Set up argument parser
    parser = argparse.ArgumentParser(description="Plex Media Search and Mark as Watched Tool")

    # Create argument groups for better organization
    general_group = parser.add_argument_group('General Settings')
    action_group = parser.add_argument_group('Action Settings')

    # Add arguments to each group
    general_group.add_argument('search', nargs='*', help="Search string for media titles")
    general_group.add_argument('-s', "--server", default=PLEX_SERVER_URL, help="Plex server URL (default from config file)")
    general_group.add_argument('-t', "--token", default=PLEX_SERVER_TOKEN, help="Plex server token (default from config file)")
    general_group.add_argument('-p', "--port", default=PLEX_SERVER_PORT, help="Plex server port (default 32400)")

    action_group.add_argument('-w', "--watched", action="store_true", help="Mark search results as watched")

    # Parse arguments
    args = parser.parse_args()

    # Join the search arguments if provided
    search_query = ' '.join(args.search) if args.search else None

    if not search_query:
        print("Usage: plex_search.py <search_string> --token <plex_token>")
        sys.exit(1)

    # Connect to Plex server
    plex_connection = PlexConnection(args.server, args.token, args.port)

    # Search Plex for titles matching the search query
    results = plex_connection.search_plex(search_query)

    if not results:
        print("No matches found.")
        return
    
    print(f"\nFound {len(results)} match(es) for '{search_query}':")
    for result in results:
        print(f"  - {result.title} ({result.year})")

    # If the --watched flag is provided, mark as watched
    if args.watched:
        plex_connection.mark_as_watched(results)


if __name__ == "__main__":
    main()