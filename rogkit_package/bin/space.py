import os
import argparse
from .bytes import byte_size
from .tomlr import load_rogkit_toml # TODO: Use this to get default paths

default_path_list = ['/', '/mnt/expansion', '/mnt/archive']

def print_header():
    print(f"{'Path':20} | {'Total Size':10} | {'Used':10} | {'Free':10} | {'Usage':5}")
    print("-" * 70)  # Adjust the length according to the total width of the above header

def display_space(path):
    total_space = os.statvfs(path).f_blocks * os.statvfs(path).f_frsize
    free_space = os.statvfs(path).f_bfree * os.statvfs(path).f_frsize
    used_space = total_space - free_space
    percent_full = used_space / total_space * 100

    print(f"{path:20} | {byte_size(total_space):10} | {byte_size(used_space):10} | {byte_size(free_space):10} | {percent_full:5.2f}%")

def display_paths(path_list=None):
    if path_list is None or not path_list:
        path_list = default_path_list

    paths_found = [x for x in path_list if os.path.exists(x)]
    if not paths_found:
        # Check if args are search terms for paths in /mnt
        paths_found = [f'/mnt/{x}' for x in os.listdir('/mnt') if any([y in x for y in path_list])]

    if not paths_found:
        print(f'No paths found: {path_list}')
        return

    print_header()
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
