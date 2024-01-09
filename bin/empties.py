#!/usr/bin/env python3
import os
import time
import argparse

DEFAULT_DIRECTORIES = ["/home/rdubar/projects/pythonProject/openerp-addons/src", "/mnt/expansion/Media/Movies/"]

def check_directory(directory, file_limit):
    """
    Recursively checks the given directory and its subdirectories for folders with
    less than or equal to 'file_limit' files and subdirectories.
    """
    limited_file_folders = []
    directory_count = 0
    file_count = 0

    for root, directories, filenames in os.walk(directory):
        directory_count += 1
        file_count += len(filenames)

        total_count = len(filenames) + len(directories)  # Counting both files and subdirectories

        if total_count <= file_limit:
            limited_file_folders.append(root)

    return limited_file_folders, directory_count, file_count


def print_results(folders, directory_count, file_count, file_limit, time_taken):
    if folders:
        print(f"Found {len(folders):,} folders with <= {file_limit} files:")
        for folder in folders:
            print(folder)
    else:
        print(f"No folders with {file_limit} or fewer files found.")

    print(f'Checked {file_count:,} files in {directory_count:,} directories in {time_taken:.2f} seconds.')

def main():
    parser = argparse.ArgumentParser(description="Check for folders with limited number of files.")
    parser.add_argument('-d', '--directory', type=str, help='Directory to search.')
    parser.add_argument('-n', '--number', type=int, default=0, help='Maximum number of files in a folder')
    args = parser.parse_args()

    directories_to_check = [args.directory] if args.directory else DEFAULT_DIRECTORIES

    for directory in directories_to_check:
        if os.path.exists(directory):
            clock = time.time()
            print(f'Checking for folders in {directory} with <= {args.number} files and directories...')
            folders, directory_count, file_count = check_directory(directory, args.number)
            print_results(folders, directory_count, file_count, args.number, time.time() - clock)
        else:
            print(f'Directory not found: {directory}')

if __name__ == "__main__":
    main()
