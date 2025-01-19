import argparse
from plexapi.server import PlexServer
from plexapi.exceptions import NotFound
import sys
from ..bin.tomlr import load_rogkit_toml

# Load the configuration from TOML file
TOML = load_rogkit_toml()
PLEX_SERVER_URL = TOML.get('plex', {}).get('plex_server_url', None)
PLEX_SERVER_TOKEN = TOML.get('plex', {}).get('plex_server_token', None)
PLEX_SERVER_PORT = TOML.get('plex', {}).get('plex_server_port', 32400)

# Ensure we are using a full URL (with http/https) and port
def construct_plex_url(server_url, port):
    if server_url:
        if 'http' not in server_url:
            server_url = f"http://{server_url}:{port}"  # Default to http if no scheme present
        elif ':' not in server_url:
            server_url = f"{server_url}:{port}"  # Append port if no port is present
    return server_url

# Check the constructed URL
PLEX_SERVER_URL = construct_plex_url(PLEX_SERVER_URL, PLEX_SERVER_PORT)

def connect_to_plex(server_url, token):
    """Connect to Plex Server using URL and token"""
    try:
        plex = PlexServer(server_url, token)
        return plex
    except Exception as e:
        print(f"Error connecting to Plex: {e}")
        sys.exit(1)

def search_plex(plex, search_query):
    """Search Plex for media titles matching the search query"""
    try:
        results = plex.library.search(search_query)
        return results
    except NotFound:
        print(f"No results found for '{search_query}'.")
        return []

def mark_as_watched(results):
    """Mark all episodes of the same series and season as watched in Plex, or movies if applicable."""
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
                        episode.markWatched()
                        print(f"Marked '{episode.title}' as watched.")
                    else:
                        print(f"'{episode.title}' is already marked as watched.")

            # If it's not an episode, check if it's a movie
            elif result.type == 'movie':
                if not result.isWatched:
                    result.markWatched()
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
                        episode.markWatched()
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
    print("Experimental Plex Media Search and Mark as Watched Tool")
    
    # Set up argument parser
    parser = argparse.ArgumentParser(description="Plex Media Search and Mark as Watched Tool")
    parser.add_argument('search', nargs='*', help="Search string for media titles")
    parser.add_argument('-s', "--server", default=PLEX_SERVER_URL, help="Plex server URL (default from config file)")
    parser.add_argument('-t', "--token", default=PLEX_SERVER_TOKEN, help="Plex server token (default from config file)")
    parser.add_argument('-p', "--port", default=PLEX_SERVER_PORT, help="Plex server port (default 32400)")
    
    # Parse arguments
    args = parser.parse_args()

    # Join the search arguments if provided
    search_query = ' '.join(args.search) if args.search else None

    if not search_query:
        print("Usage: plex_search.py <search_string> --token <plex_token>")
        sys.exit(1)

    # Construct the Plex URL using server, port, and token
    server_url = args.server or PLEX_SERVER_URL
    port = args.port or PLEX_SERVER_PORT
    plex_url = construct_plex_url(server_url, port)

    # Connect to Plex server
    try:
        plex = connect_to_plex(plex_url, args.token)
    except Exception as e:
        print(f"Error connecting to Plex: {e}")
        sys.exit(1)

    # Search Plex for titles matching the search query
    results = search_plex(plex, search_query)

    if results:
        print(f"\nFound {len(results)} match(es) for '{search_query}':")
        for result in results:
            print(f"  - {result.title} ({result.year})")

        # Ask if user wants to mark all matches as watched
        mark_watched = input("\nDo you want to mark all these titles as watched? (y/n): ").strip().lower()
        if mark_watched in ['y', 'yes']:
            mark_as_watched(results)
        else:
            print("No titles were marked as watched.")
    else:
        print("No matches found.")

if __name__ == "__main__":
    main()