"""
Directory size calculator and analyzer.

Recursively scans directories to calculate and display the largest directories
by total file size. Supports filtering by search terms.
"""
import os
import sys
from time import perf_counter
from .bytes import byte_size

# TODO: search functionality, show hidden folders

DEFAULT_FOLDER_LIST = ['/home', '/mnt/expansion']


def default_folder():
    """Select first available default folder from DEFAULT_FOLDER_LIST."""
    for folder in DEFAULT_FOLDER_LIST:
        if os.path.isdir(folder):
            return folder
    # else
    return '/'

def main():
    """Calculate and display top 10 largest directories."""
    start_time = perf_counter()
    dir_sizes = {}
    total_files = 0
    errors = []
    root = default_folder()
    print('Searching in', root)
    for root, dirs, files in os.walk(root):
        for file in files:
            total_files += 1
            file_path = os.path.join(root, file)
            try:
                file_size = os.path.getsize(file_path)
            except OSError as e:
                errors.append(f"Error: {e}")
                continue
            # Add file size to its parent directory
            if root in dir_sizes:
                dir_sizes[root] += file_size
            else:
                dir_sizes[root] = file_size

    # get search terms from the command line
    search_terms = ' '.join(sys.argv[1:]).lower()  
    total_size = sum(dir_sizes.values())
    filtered_dirs = {x: dir_sizes[x] for x in dir_sizes if search_terms in x.lower()} if search_terms else dir_sizes
    filtered_size = sum(filtered_dirs.values()) if search_terms != '' else None
    

    # Now, add sizes of directories to their parent directories iteratively
    for dir_path in sorted(filtered_dirs.keys(), key=len, reverse=True):
        parent_dir = os.path.dirname(dir_path)
        if parent_dir in dir_sizes:
            dir_sizes[parent_dir] += dir_sizes[dir_path]
    
    # Sort the directories by size
    sorted_dirs = sorted(filtered_dirs.items(), key=lambda x: x[1], reverse=True)

    # Print the first 10 items
    for i in range(min(10, len(sorted_dirs))):
        print(f"{byte_size(sorted_dirs[i][1]):>10}   {sorted_dirs[i][0]}")

    # print files, errors, and time elapsed
    print(f"Processed {len(filtered_dirs):,} of {total_files:,} files (with {len(errors)} errors) in {perf_counter() - start_time:.2f} seconds")
    if filtered_size:
        print(f"Total size: {byte_size(filtered_size)} of {byte_size(total_size)}")
    else:
        print(f"Total size: {byte_size(total_size)}")


if __name__ == "__main__":
    print("Directory size calculator. Improved efficiency.")
    main()
