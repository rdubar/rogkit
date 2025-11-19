"""
Disk space usage utility.

Displays disk space information for mounted filesystems,
including total, used, and free space with usage percentages.
"""
import argparse
import os

from rich.console import Console
from rich.table import Table

from .bytes import byte_size

console = Console()


def get_space_info(path):
    """Return disk usage stats for a given path."""
    stats = os.statvfs(path)
    total_space = stats.f_blocks * stats.f_frsize
    free_space = stats.f_bfree * stats.f_frsize
    used_space = total_space - free_space
    percent_full = (used_space / total_space * 100) if total_space else 0
    return total_space, used_space, free_space, percent_full


def display_space(path):
    """Display disk space statistics for a given path."""
    total_space, used_space, free_space, percent_full = get_space_info(path)

    print(
        f"{path:20} | {byte_size(total_space):10} | {byte_size(used_space):10} | "
        f"{byte_size(free_space):10} | {percent_full:5.2f}%"
    )

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

    rows = []
    for path in found_paths:
        try:
            rows.append((path, *get_space_info(path)))
        except OSError:
            continue

    if quiet:
        for path, total_space, used_space, free_space, percent_full in rows:
            print(
                f"{path:20} | {byte_size(total_space):10} | {byte_size(used_space):10} | "
                f"{byte_size(free_space):10} | {percent_full:5.2f}%"
            )
        return

    table = Table(header_style="bold cyan", show_lines=False)
    table.add_column("Path", style="magenta")
    table.add_column("Total", justify="right")
    table.add_column("Used", justify="right")
    table.add_column("Free", justify="right")
    table.add_column("Usage", justify="right")

    for path, total_space, used_space, free_space, percent_full in rows:
        if percent_full >= 95:
            style = "bold red"
        elif percent_full >= 80:
            style = "yellow"
        else:
            style = "green"
        table.add_row(
            path,
            byte_size(total_space),
            byte_size(used_space),
            byte_size(free_space),
            f"{percent_full:5.2f}%",
            style=style,
        )

    console.print(table)

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
