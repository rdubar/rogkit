import os
import argparse
from .bytes import byte_size

def print_header():
    print(f"{'Path':20} | {'Total Size':10} | {'Used':10} | {'Free':10} | {'Usage':5}")
    print("-" * 70)  # Adjust the length according to the total width of the above header

def display_space(path):
    total_space = os.statvfs(path).f_blocks * os.statvfs(path).f_frsize
    free_space = os.statvfs(path).f_bfree * os.statvfs(path).f_frsize
    used_space = total_space - free_space
    percent_full = used_space / total_space * 100
    
    print(f"{path:20} | {byte_size(total_space):10} | {byte_size(used_space):10} | {byte_size(free_space):10} | {percent_full:5.2f}%")

def display_paths(path_list=None, size=False, quiet=False):
    if path_list is None:
        path_list = []
        
    if os.path.exists('/mnt'):  #  refactor this for MacOS setup
        mnt_paths = os.listdir('/mnt')
        mnt_paths_full = [os.path.join('/mnt', x) for x in mnt_paths]
    else:
        mnt_paths_full = []

    # Check if paths exist in the filesystem
    found_paths = [x for x in path_list if os.path.exists(x)]

    # If no paths are found and path_list is not empty, check in '/mnt'
    if not found_paths and path_list:        
        # Check if any of the paths in path_list are subdirectories of '/mnt'
        found_paths = [x for x in mnt_paths_full if any(y in x for y in path_list)]

    # If still no paths are found, display the contents of '/mnt' and root '/'
    if not found_paths:
        found_paths = mnt_paths_full + ['/']
    
    if size:
        found_paths.sort(key=lambda x: os.statvfs(x).f_blocks * os.statvfs(x).f_frsize, reverse=True)
    else:
        # sort alphabetically
        found_paths.sort()

    if not quiet:
        print_header()
    for path in found_paths:
        display_space(path)

def get_args():
    parser = argparse.ArgumentParser(description='Display disk space usage')
    parser.add_argument('paths', nargs='*', default=[], help='List of paths to check (optional)')
    parser.add_argument('-s', '--size', action='store_true', help='Sort by size')
    parser.add_argument('-q', '--quiet', action='store_true', help='Short (quiet) output')
    args = parser.parse_args()
    return args

if __name__ == "__main__":
    args = get_args()
    display_paths(args.paths, size=args.size, quiet=args.quiet)

