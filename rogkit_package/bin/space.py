import os
import argparse
from .bytes import byte_size

# TODO: use TOML for setup
default_path_list = ['/', '/mnt/expansion', '/mnt/archive']

def display_space(path):
    # get the free space on the disk
    total_space = os.statvfs(path).f_blocks * os.statvfs(path).f_frsize
    free_space = os.statvfs(path).f_bfree * os.statvfs(path).f_frsize
    percent_full = (total_space - free_space) / total_space * 100

    print(f'{path} has {byte_size(free_space)} free of {byte_size(total_space)} total, and is {percent_full:.2f}% full.')

def display_paths(path_list=None):
    if path_list is None or not path_list:
        path_list = default_path_list

    paths_found = [x for x in path_list if os.path.exists(x)]
    if not paths_found:
        print(f'No paths found: {path_list}')
        return

    for path in paths_found:
        display_space(path)

def get_args():
    parser = argparse.ArgumentParser(description='Display disk space usage')
    parser.add_argument('paths', nargs='*', default=None, help='List of paths to check (optional)')
    args = parser.parse_args()
    return args.paths

if __name__ == "__main__":
    args_paths = get_args()
    display_paths(args_paths)
