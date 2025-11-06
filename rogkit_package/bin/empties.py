#!/usr/bin/env python3
"""
Empty folder and sparse directory finder.

Recursively scans directories to find folders with few or no files,
including folders containing only .pyc bytecode files.
"""
import os
import time
import argparse

DEFAULT_DIRECTORIES = ["/Users/rdubar/apv/openerp-addons/src","/Users/rdubar/apv/pythonProject/openerp-addons/src", "/mnt/expansion/Media/Movies/"]


def check_directory(directory, file_limit):
    """
    Recursively checks the given directory and its subdirectories for folders with
    less than or equal to 'file_limit' files and subdirectories.
    """
    limited_file_folders = []
    directory_count = file_count = 0

    for root, directories, filenames in os.walk(directory):
        directory_count += 1
        file_count += len(filenames)

        if len(filenames) + len(directories) <= file_limit:
            limited_file_folders.append(root)
            
        # id folders only contain one or more '.pyc' files, also add them
        elif all([f.endswith('.pyc') for f in filenames]) and len(filenames) > 0:
            limited_file_folders.append(root)
        

    return limited_file_folders, directory_count, file_count

def print_results(folders, directory_count, file_count, file_limit, time_taken):
    """Print summary of found folders and scan statistics."""
    if folders:
        print(f"Found {len(folders)} matching folders.")
        for folder in folders:
            print(folder)
    else:
        print("No matching directories found.")

    print(f'Checked {file_count:,} files in {directory_count:,} directories in {time_taken:.2f} seconds.')

def main():
    """CLI entry point for empty/sparse folder finder."""
    parser = argparse.ArgumentParser(description="Check for folders with a limited number of files.")
    parser.add_argument('-d', '--directory', type=str, help='Directory to search.')
    parser.add_argument('-n', '--number', type=int, default=0, help='Maximum number of files in a folder')
    args = parser.parse_args()

    directories_to_check = [args.directory] if args.directory else DEFAULT_DIRECTORIES

    for directory in directories_to_check:
        if os.path.exists(directory):
            clock = time.time()
            action = 'empty' if args.number == 0 else f'with {args.number} or fewer files and directories'
            print(f'Checking for folders in {directory} {action}...')
            folders, directory_count, file_count = check_directory(directory, args.number)
            print_results(folders, directory_count, file_count, args.number, time.time() - clock)

if __name__ == "__main__":
    main()
