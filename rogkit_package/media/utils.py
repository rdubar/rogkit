#!/usr/bin/env python3
import argparse

def process_arguments():
    parser = argparse.ArgumentParser(description='Process arguments')

    # Database management options
    parser.add_argument('--update', action='store_true', help='Update database')
    parser.add_argument('-R', '--reset', action='store_true', help='Reset database')
    parser.add_argument('-D', '--duplicates', action='store_true', help='Remove duplicates')

    # Display options
    parser.add_argument('-a', '--all', action='store_true', help='Show all records')
    parser.add_argument('-d', '--dvd', action='store_true', help='Show uncompressed DVDs')
    parser.add_argument('-i', '--info', action='store_true', help='Show info for a title')  
    parser.add_argument('-l', '--latest', action='store_true', help='Show latest additions')
    parser.add_argument('-r', '--reverse', action='store_true', help='Show reverse order')
    parser.add_argument('-t', '--title', action='store_true', help='sort by title')
    parser.add_argument('-n', '--number', type=int, default=10, help='Number of results to return')
    parser.add_argument('-v', '--video', action='store_true', help='Sort by video resolution')
    parser.add_argument('-y', '--year', action='store_true', help='Sort by year of release') 
    parser.add_argument('-s', '--size', action='store_true', help='Sort by file size')
    parser.add_argument('-S', '--summary', action='store_true', help='Show a summary for each title')
    
    # Mode options
    parser.add_argument('-V', '--verbose', action='store_true', help='Verbose mode')
    parser.add_argument('--conn', action='store_true', help='Test Plex server connection')
    parser.add_argument('--debug', action='store_true', help='Debug mode')
    
    args, search_terms = parser.parse_known_args()
    return args, ' '.join(search_terms)


def sort_by_resolution(results):
    """
    Sort the results by resolution  4k > 2k > 1080p > 720p > 480p > 0
    """
    resolutions = {'4k': 2160, '2k': 2000, '1080p': 1080, '720p': 720, 'hd': 1080, '480p': 480, 'sd': 480}

    def resolution_to_int(result):
        res_string = result.resolution.lower() if result.resolution else ''
        res_string = res_string.replace('*', '')  # Remove star marker
        # Extract resolution from the string (e.g., "1080p" -> "1080")
        numeric_res = ''.join(filter(str.isdigit, res_string))
        # Check if resolution is directly in the dictionary
        if res_string in resolutions:
            return resolutions[res_string]
        # Check if numeric resolution is in the dictionary
        elif numeric_res in resolutions:
            return resolutions[numeric_res]
        # Handle cases like "576" which are not in the dictionary but are numeric
        elif numeric_res.isdigit():
            return int(numeric_res)
        # Default case
        else:
            return 0

    return sorted(results, key=resolution_to_int, reverse=True)