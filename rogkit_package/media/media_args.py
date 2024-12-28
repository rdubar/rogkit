import argparse
from .media_settings import FUZZY_DEFAULT

def process_arguments():
    """
    Process command line arguments
    :return: args, search_text
    """
    parser = argparse.ArgumentParser(description='Process arguments')
    parse = parser.add_argument

    # Database management options
    parse('-u', '--update', action='store_true', help='Update database')
    parse('-R', '--reset', action='store_true', help='Reset database')
    parse('-D', '--duplicates', action='store_true', help='Remove duplicates')
    parse('-F', '--freeze', action='store_true', help='Freeze database')
    parse('-U', '--unfreeze', action='store_true', help='Unfreeze (restore) frozen database')
    parse('--vacuum', action='store_true', help='Vacuum database')

    # Display options
    parse('-a', '--all', action='store_true', help='Show all records')
    parse('-d', '--dvd', action='store_true', help='Show uncompressed DVD format video')
    parse('-i', '--info', action='store_true', help='Show info for a title')  
    parse('-f', '--fuzzy', nargs='?', const=FUZZY_DEFAULT, type=int, help=f'Fuzzy search with optional integer value (default: {FUZZY_DEFAULT})')
    parse('-l', '--latest', action='store_true', help='Show latest additions')
    parse('-r', '--reverse', action='store_true', help='Show reverse order')
    parse('-t', '--title', action='store_true', help='sort by title')
    parse('-n', '--number', type=int, default=10, help='Number of results to return')
    parse('-p', '--path', action='store_true', help='Show main video file path')
    parse('-v', '--video', action='store_true', help='Sort by video resolution')
    parse('-y', '--year', action='store_true', help='Sort by year of release') 
    parse('-s', '--size', action='store_true', help='Sort by file size')
    parse('-S', '--summary', action='store_true', help='Show a summary for each title')
    parse('--delete', type=int, help='Delete a record by ID')
    parse('--rating', action='store_true', help='Sort by rating')
    parse('--shrink', action='store_true', help='Run the experimental database shrink function')
    parse('--afi', action="store_true", help="Check against AFI's 100 Years...100 Movies list")
    parse('--list', type=str, help='Search for a list of titles in a file (one per line)')
    parse('--watch', type=int, help='Reset the watch count of a title to zero')
    
    # Mode options
    parse('-V', '--verbose', action='store_true', help='Verbose mode')
    parse('--conn', action='store_true', help='Test Plex server connection')
    parse('--debug', action='store_true', help='Debug mode')
    
    args, search_terms = parser.parse_known_args()
    if not args.fuzzy:  # fix issue for searches like: void "the void"
        args.fuzzy = 100
    return args, ' '.join(search_terms)