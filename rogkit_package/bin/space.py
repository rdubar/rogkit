"""
Disk space usage utility.

Displays disk space information for mounted filesystems,
including total, used, and free space with usage percentages.
"""
import os
import argparse
from .bytes import byte_size


def print_header():
    """Print table header for disk space display."""
    print(f"{'Path':20} | {'Total Size':10} | {'Used':10} | {'Free':10} | {'Usage':5}")
    print("-" * 70)

def display_space(path):
    """Display disk space statistics for a given path."""
    stats = os.statvfs(path)
    total_space = stats.f_blocks * stats.f_frsize
    free_space = stats.f_bfree * stats.f_frsize
    used_space = total_space - free_space
    percent_full = used_space / total_space * 100
    
    print(f"{path:20} | {byte_size(total_space):10} | {byte_size(used_space):10} | {byte_size(free_space):10} | {percent_full:5.2f}%")

def display_paths(path_list=None, size=False, quiet=False, show_all=False):
    """
    Display disk space for multiple paths.
    
    Args:
        path_list: List of paths to check (defaults to /mnt/* and /)
        size: Sort by size if True
        quiet: Skip header if True  
        show_all: Show all mount points including duplicates
    """
    if path_list is None:
        path_list = []
        
    if os.path.exists('/mnt'):
        mnt_paths = os.listdir('/mnt')
        mnt_paths_full = [os.path.join('/mnt', x) for x in mnt_paths]
    else:
        mnt_paths_full = []

    found_paths = [x for x in path_list if os.path.exists(x)]

    if not found_paths and path_list:
        found_paths = [x for x in mnt_paths_full if any(y in x for y in path_list)]

    if not found_paths:
        found_paths = mnt_paths_full + ['/']

    if size:
        found_paths.sort(key=lambda x: os.statvfs(x).f_blocks * os.statvfs(x).f_frsize, reverse=True)
    else:
        found_paths.sort()

    # Deduplicate by device ID unless --all is used
    if not show_all:
        seen_devs = set()
        unique_paths = []
        for path in found_paths:
            try:
                dev = os.stat(path).st_dev
                if dev not in seen_devs:
                    seen_devs.add(dev)
                    unique_paths.append(path)
            except FileNotFoundError:
                continue
        found_paths = unique_paths

    if not quiet:
        print_header()
    for path in found_paths:
        display_space(path)

def get_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description='Display disk space usage')
    parser.add_argument('paths', nargs='*', default=[], help='List of paths to check (optional)')
    parser.add_argument('-s', '--size', action='store_true', help='Sort by size')
    parser.add_argument('-q', '--quiet', action='store_true', help='Short (quiet) output')
    parser.add_argument('-a', '--all', action='store_true', help='Show all mount points, including duplicates')
    return parser.parse_args()

if __name__ == "__main__":
    args = get_args()
    display_paths(args.paths, size=args.size, quiet=args.quiet, show_all=args.all)