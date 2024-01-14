#!/usr/bin/env python3
from .plex_record import PlexRecord
from .plex_server import PlexServer
from .models import PlexRecordORM
from .plex_library import PlexLibrary, update_database_schema, engine
from ..bin.seconds import convert_seconds
from ..bin.bytes import byte_size
from .utils import process_arguments, sort_by_resolution, should_show_latest_results

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
        update_database_schema(engine)
        plex_library.reset_database()
    elif args.update:
        plex_library.update_database()

    if args.duplicates: 
        removed = plex_library.remove_duplicates()
        print(f"Removed {removed:,} duplicates.") 

    total_records = plex_library.session.query(PlexRecordORM).count()

    results = plex_library.libraries
    if not results:
        print("No results.")
        return

    if search_text:
        results = plex_library.search(search_text)
        print(f"Found {len(results):,} results in {total_records:,} total records for '{search_text}':" )

    if args.latest or should_show_latest_results(args, search_text):
        results = plex_library.latest(number=args.number)
        print(f"Showing {len(results):,} latest updates from {total_records:,} total records:")
        
    if args.dvd:
        print("Filtering for uncompressed DVDs...")
        results = [result for result in results if result.codec == 'mpeg2video']

    if args.year:
        print("Sort by year...")
        results = sorted(results, key=lambda x: x.year, reverse=True)
    
    if args.video:
        print("Sorting by video resolution...")
        results = sort_by_resolution(results)

    if args.reverse:
        print("Reversing order...")
        results = list(reversed(results))

    for result in results:
        print(result)  
        if args.summary:
            print(result.summary)
        if args.verbose:
            print(vars(result))     

    # get the total duration of all results
    total_duration = convert_seconds((sum([getattr(result, 'duration', 0) or 0 for result in results]) or 0) / 1000)
    total_size = byte_size(sum([getattr(result, 'size', 0) or 0 for result in results]) or 0)
    print(f"{len(results):,} items, {total_duration} ({total_size})")

    if args.debug and results:
        plex_library.test_connection()


if __name__ == "__main__":
    main()