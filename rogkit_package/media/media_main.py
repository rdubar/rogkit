#!/usr/bin/env python3
from .utils import process_arguments
from .plex_record import PlexRecord
from .plex_server import PlexServer
from .models import PlexRecordORM
from .plex_library import PlexLibrary, update_database_schema
from ..bin.seconds import convert_seconds

def main():
    print("Rog's Plex Library Utility")
    args, search_text = process_arguments()

    plex_library = PlexLibrary()

    if args.reset or args.update:
        plex_library.connect_to_plex()

    if args.reset:
        confirm = input("Resetting the database will delete all records. Are you sure? (y/n)")
        if not confirm.lower() in ['y', 'yes']:
            print("Aborting reset.")
            return
        update_database_schema()
        plex_library.reset_database()
    elif args.update:
        plex_library.update_database()

    if args.duplicates: 
        removed = plex_library.remove_duplicates()
        print(f"Removed {removed:,} duplicates.") 

    total_records = plex_library.session.query(PlexRecordORM).count()

    if args.all:
        results = plex_library.libraries
    elif search_text:
        results = plex_library.search(search_text)
        print(f"Found {len(results):,} results in {total_records:,} total records for '{search_text}':" )
    else:
        results = plex_library.latest(number=args.number)
        print(f"Showing {len(results):,} latest updates from {total_records:,} total records:")
    if results:

        if args.dvd:
            print("Filtering for uncompressed DVDs...")
            results = plex_library.libraries
            results = [result for result in results if result.codec == 'mpeg2video']

        if args.year:
            print("Sort by year...")
            results = sorted(results, key=lambda x: x.year, reverse=True)
        

        def sort_by_resolution(results):
            resolutions = {'4k': 2160, '1080p': 1080, '720p': 720, 'hd': 1080, '480p': 480, 'sd': 480}

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

        # In your main function or wherever you process the search results:
        if args.resolution:
            print("Sorting by video resolution...")
            results = sort_by_resolution(results)

        for result in results:
            print(result)  
            if args.summary:
                print(result.summary)
            if args.verbose:
                print(vars(result))      
        # get the total duration of all results
        total_duration = convert_seconds((sum([result.duration for result in results if result.duration]) or 0) / 1000)
        print(f"{len(results):,} items, {total_duration}")

    if args.debug and results:
        print(f"First result: {results[0]}")
        print(vars(results[0]))


if __name__ == "__main__":
    main()