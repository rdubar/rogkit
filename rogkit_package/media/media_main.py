#!/usr/bin/env python3
"""
Main CLI interface for Plex library management.

Provides comprehensive tools for searching, filtering, and managing
Plex media library records stored in the local database.
"""
import datetime
from pprint import pp
from time import perf_counter
from rogkit_package.media.media_records import PlexRecordORM
from rogkit_package.media.plex_library import PlexLibrary, update_database_schema, engine
from rogkit_package.media.plex_server import PlexServer
from rogkit_package.media.shrink import shrink_list
from rogkit_package.bin.seconds import convert_seconds
from rogkit_package.bin.bytes import byte_size
from rogkit_package.media.media_args import process_arguments
from rogkit_package.media.media_settings import afi_path
from rogkit_package.media.media_utils import freeze_database, restore_database, last_updated, sort_results_by_attribute

def main():
    start_time = perf_counter()
    print("Rog's Plex Library Utility")
    print(last_updated())
    args, search_text = process_arguments()
    
    if args.zoom:  # turn on popular options
        args.year = True
        args.all = True
    
    plex_library = PlexLibrary()

    if args.afi:
        print("Checking against AFI's 100 Years...100 Movies list")
        found = missing = 0
        with open(afi_path, 'r', encoding='utf-8') as file:
            file_list = file.read().splitlines()
        for item in file_list:
            if item[0] == '#' or '(' not in item or ')' not in item:
                continue
            title = item[item.find(' '):item.rfind('(')].strip().lower().replace(", the", "").replace(", a", "")
            if plex_library.search(title, fuzzy=args.fuzzy, verbose=args.verbose):
                found += 1
            else:
                print(f"Missing: {item} - {title}")
                missing += 1
        print(f"Found: {found}, Missing: {missing}")
        return
    
    if args.delete:
        plex_library.remove_record(args.delete, verbose= True, check=True)
        return
    
    if args.watch:
        plex_library.reset_watch_count(args.watch)
        return
    
    if args.list:
        # read a list of items from a file and search for them
        try:
            with open(args.list, 'r', encoding='utf-8') as file:
                file_list = file.read().splitlines()
        except FileNotFoundError:
            print(f"File not found: {args.list}")
            return
        if not file_list:
            print(f"File is empty: {args.list}")
            return
        print(f"Searching for {len(file_list):,} items in {args.list}")
        print(f"\n{'Matches':5}    Title\n{'-------':5}    -----")
        for item in file_list:
            results = plex_library.search(item, fuzzy=args.fuzzy, verbose=args.verbose)
            titles = {f"{result.title} ({result.year})" if result.year else result.title for result in results}
            print(f"{len(titles):5}      {item}", sep='')
            if args.verbose and len(titles) > 1:  
                print( *titles, sep=', ')
        return

    if args.freeze:
        freeze_database()
        return
    
    if args.unfreeze:
        restore_database()
        return

    if args.conn:
        server = PlexServer()
        print(server.get_connection())
        
    if args.vacuum:
        plex_library.vacuum_db()
        return

    if args.debug:
        # Do debug stuff here
        results = plex_library.test_connection()
        return

    if args.reset:  # or args.update:
        plex_library.connect_to_plex()

    if args.reset:
        confirm = input("Resetting the database will delete all records. Are you sure? (y/n)")
        if confirm.lower() not in ['y', 'yes']:
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
        print(f"Removed {len(removed):,} duplicates.") 
        for result in removed:
            print(result)

    total_records = plex_library.session.query(PlexRecordORM).count()

    results = plex_library.libraries

    if True or args.latest: # or should_show_latest_results(args, search_text):
        # go thru results, setting added at to 01/01/2000 if it's None
        for result in results:
            if hasattr(result, 'added_at') and not result.added_at:
                result.added_at = datetime.datetime(2000, 1, 1)
        # remove results that don't have an added at value
        #results = [result for result in results if getattr(result, 'added_at', None)]
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

    if args.shrink:
        results = [result for result in results if result.codec == 'mpeg2video']
        shrink_list(results, search=search_text)
        return

    if search_text:
        results = plex_library.search(search_text, fuzzy=args.fuzzy, verbose=args.verbose)
        print(f"Found {len(results):,} results in {total_records:,} total records for '{search_text}':" )
        matches_text = f' of {len(results):,} matches' 
    else:
        matches_text = ''
        
    if args.dvd:
        print("Filtering for uncompressed DVDs...")
        results = [result for result in results if result.codec == 'mpeg2video']
        matches_text = f' of {len(results):,} uncompressed DVDs'
        
    # Initialize the sort_by variable to default
    sort_by = 'added_at'

    # Iterate over the sorting arguments and check if the corresponding argument is set
    for arg, sort_by_candidate in [('title', 'title'),('year', 'year'), ('video', 'resolution'), ('size', 'size'), ('rating', 'rating')]:
        if getattr(args, arg):
            sort_by = sort_by_candidate
            break

    # Now, sort based on the selected attribute (if one was chosen)
    if sort_by:
        results = sort_results_by_attribute(results, sort_by, reverse=args.reverse)

    reverse_text = 'reversed' if args.reverse else ''
    if args.all:
        args.number = len(results)
        number_text = 'all'
    else:
        if args.number > len(results):
            args.number = len(results)
        number_text = f'{args.number:,}'
        
    if len(results) == 0:
        print("No results.")
        return
    
    results_text = 'results' if len(results) > 1 else 'result'
    print(f"Showing {number_text} {results_text}{matches_text} from {total_records:,} total records. Sort order: {sort_by} {reverse_text}")
    for result in results[:args.number]:
        if args.info:
            print(result.info())
            continue
        if args.rating:
            print(f"{result.rating:2}  {result}")
            continue
        print(result)  
        if args.summary:
            print(result.summary)
        if args.verbose:
            print(pp(vars(result)))   
        if args.path:
            print(result.video_path)
        if args.vars:
            print(vars(result))
    remaining = len(results) - args.number
    if remaining > 0:
        print(f"...and {remaining:,} more.")

    # get the total duration of all results
    total_duration = convert_seconds((sum([getattr(result, 'duration', 0) or 0 for result in results]) or 0) / 1000)
    total_size = byte_size(sum([getattr(result, 'size', 0) or 0 for result in results]) or 0)
    item_text = 'items' if len(results) > 1 else 'item'
    elapsed = perf_counter() - start_time
    print(f"{len(results):,} {item_text}, {total_duration} ({total_size}) [{elapsed:.2f}s]")


if __name__ == "__main__":
    main()


# TODO: Rename PlexRecord/PlexRecordORM to MediaRecord/MediaRecordORM
# TODO: Rename PlexLibrary to MediaLibrary, plex_library.py to media_library.py
# TODO: Refactor plex_library.py
