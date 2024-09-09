#!/usr/bin/env python3
import os
import shutil
import time
from .media_settings import db_path, db_backup_path
from ..bin.seconds import convert_seconds
from ..bin.bytes import byte_size


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

def last_updated():
    """
    Return the last time the database was updated
    """
    try:
        return f'Library last updated {convert_seconds(time.time() - os.path.getmtime(db_path))} ago.'
    except FileNotFoundError:
        return "Library not found."
    
def sort_results_by_attribute(results, attribute_name):
    """
    Sort a list of media results by an attribute, filtering out results without the attribute.
    """
    if attribute_name == 'year':
        # Numeric sort with default value for non-numeric or absent values
        return sorted(results, key=lambda x: int(getattr(x, attribute_name, 0)) if str(getattr(x, attribute_name, '0')).isdigit() else 0, reverse=True)
    else:
        # Generic sort for other attributes, filtering out results without the attribute
        return sorted((result for result in results if getattr(result, attribute_name, None)), key=lambda x: getattr(x, attribute_name), reverse=True)
