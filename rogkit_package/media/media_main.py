#!/usr/bin/env python3
import datetime
from .media_records import PlexRecordORM
from .plex_library import PlexLibrary, update_database_schema, engine
from .plex_server import PlexServer

from ..bin.seconds import convert_seconds
from ..bin.bytes import byte_size
from .utils import process_arguments, sort_by_resolution, freeze_database, restore_database

def main():
    print("Rog's Plex Library Utility")
    args, search_text = process_arguments()

    plex_library = PlexLibrary()

    if args.freeze:
        freeze_database()
        return
    
    if args.restore:
        restore_database()
        return

    if args.conn:
        server = PlexServer()
        print(server.get_connection())

    if args.debug:
        # Do debug stuff here
        results = plex_library.test_connection()
        return

    if args.reset:  # or args.update:
        plex_library.connect_to_plex()

    if args.reset:
        confirm = input("Resetting the database will delete all records. Are you sure? (y/n)")
        if not confirm.lower() in ['y', 'yes']:
            print("Aborting reset.")
            return
        update_database_schema(engine)
        plex_library.reset_database()
        print("Database reset.")
        return
    elif args.update:
        plex_library.update_test()
        return

    if args.duplicates: 
        removed = plex_library.remove_duplicates()
        print(f"Removed {removed:,} duplicates.") 

    total_records = plex_library.session.query(PlexRecordORM).count()

    results = plex_library.libraries

    if True or args.latest: # or should_show_latest_results(args, search_text):
        # go thru results, setting addded at to 01/01/2000 if it's None
        for result in results:
            if hasattr(result, 'added_at') and not result.added_at:
                result.added_at = datetime.datetime(2000, 1, 1)
        # remove results that don't have an added at value
        results = [result for result in results if getattr(result, 'added_at', None)]
        # sort by added at
        results = sorted(results, key=lambda x: x.added_at, reverse=True)
        # results = plex_library.latest()
        sort_by = 'added_at'

    if args.title:
        sort_by = 'title'
        results = sorted(results, key=lambda x: x.title)

    if not results:
        print("No results.")
        return

    if search_text:
        results = plex_library.search(search_text)
        print(f"Found {len(results):,} results in {total_records:,} total records for '{search_text}':" )
        matches_text = f' of {len(results):,} matches' 
    else:
        matches_text = ''
        
    if args.dvd:
        print("Filtering for uncompressed DVDs...")
        results = [result for result in results if result.codec == 'mpeg2video']
        matches_text = f' of {len(results):,} uncompressed DVDs'

    if args.year:
        sort_by = 'year'
        # remove results that don't have a year value
        results = sorted((result for result in results if getattr(result, 'year', None)), key=lambda x: x.year, reverse=True)
    
    if args.video:
        sort_by = 'resolution'
        # remove results that don't have a resolution value
        results = sorted((result for result in results if getattr(result, 'resolution', None)), key=lambda x: x.resolution, reverse=True)
    
    if args.size:
        sort_by = 'size'
        results = sorted((result for result in results if getattr(result, 'size', None)), key=lambda x: x.size, reverse=True)

    reverse_text = 'reversed' if args.reverse else ''
    if args.reverse:
        results = list(reversed(results))

    if args.all:
        args.number = len(results)
        number_text = 'all'
    else:
        if args.number > len(results):
            args.number = len(results)
        number_text = f'{args.number:,}'
    results_text = 'results' if len(results) > 1 else 'result'
    print(f"Showing {number_text} {results_text}{matches_text} from {total_records:,} total records. Sort order: {sort_by} {reverse_text}")
    for result in results[:args.number]:
        if args.info:
            print(result.info())
            continue
        print(result)  
        if args.summary:
            print(result.summary)
        if args.verbose:
            print(vars(result))     

    # get the total duration of all results
    total_duration = convert_seconds((sum([getattr(result, 'duration', 0) or 0 for result in results]) or 0) / 1000)
    total_size = byte_size(sum([getattr(result, 'size', 0) or 0 for result in results]) or 0)
    item_text = 'items' if len(results) > 1 else 'item'
    print(f"{len(results):,} {item_text}, {total_duration} ({total_size})")


if __name__ == "__main__":
    main()

"""
TODO: 

update in plex_library.py
Rename PlexRecord, PlexRecordORM to MediaRecord, MediaRecordORM 
Rename PlexLibrary to MediaLibrary
Rename plex_library.py to media_library.py
Refactor plex_library.py
--update currenrly not implemented
"""