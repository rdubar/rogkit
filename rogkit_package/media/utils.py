#!/usr/bin/env python3
import argparse
import os
import shutil
import time
from .media_settings import db_path, db_backup_path
from ..bin.seconds import convert_seconds
from ..bin.bytes import byte_size

def process_arguments():
    parser = argparse.ArgumentParser(description='Process arguments')

    # Database management options
    parser.add_argument('-u', '--update', action='store_true', help='Update database')  # TODO: confirm working
    parser.add_argument('-R', '--reset', action='store_true', help='Reset database')
    parser.add_argument('-D', '--duplicates', action='store_true', help='Remove duplicates')
    parser.add_argument('--freeze', action='store_true', help='Freeze database')
    parser.add_argument('--restore', action='store_true', help='Restore database')

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


def freeze_database():
    """
    Create a backup of the database
    """
    print(f"Freezing database...")
    if os.path.exists(db_backup_path):
        time_now = time.time()
        backtime = os.path.getmtime(db_backup_path)
        # Convert timestamp to string
        backtime_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(backtime))
        back_datetime = convert_seconds(time_now - backtime)
        backsize = byte_size(os.path.getsize(db_backup_path))
        print(f"Backup file already exists: {db_backup_path}  ({backsize}).")
        print(f'Backup date: {backtime_str}, {back_datetime} ago.')

        # Calculate elapsed time since in seconds since last backup
        backtime = os.path.getmtime(db_path)
        backtime_str = convert_seconds(time_now - backtime)
        backsize = byte_size(os.path.getsize(db_path))
        print(f"Existing database ({backsize}) last updated: {backtime_str} ago.")

        response = input("Overwrite? This cannot be undone![y/N] ")
        if response.lower() != 'y':
            print("Aborting...")
            return
    try:
        shutil.copyfile(db_path, db_backup_path)
    except Exception as e:
        print(f"Error creating backup file: {e}")
        return
    backsize = byte_size(os.path.getsize(db_backup_path))
    print(f"Backup file created: {db_backup_path} ({backsize} bytes).")


def restore_database():
    """
    Restore the database from a backup
    """
    if not os.path.exists(db_backup_path):
        print(f"Backup file not found: {db_backup_path}")
        return
    time_now = time.time()
    size = byte_size(os.path.getsize(db_backup_path))
    last_updated = convert_seconds(time_now - os.path.getmtime(db_backup_path))
    print(f"Backup file found: {db_backup_path}\nLast updated {last_updated} ago ({size}).")
    if os.path.exists(db_path):
        size = byte_size(os.path.getsize(db_path))
        last_updated = convert_seconds(time_now - os.path.getmtime(db_path))
        print(f"Database already exists: {db_path}\nLast updated {last_updated} ago ({size}).")
        response = input("Overwrite with backup? This cannot be undone![y/N] ")
        if response not in ['y', 'Y']:
            print("Aborting...")
            return
    print(f"Restoring database...")
    try:
        shutil.copyfile(db_backup_path, db_path)
    except Exception as e:
        print(f"Error restoring backup file: {e}")
        return
    print(f"Backup file restored: {db_backup_path}.")