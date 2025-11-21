"""
Hidden file and folder finder.

Recursively scans directories for hidden files/folders (starting with dot)
and prints results one per line for piping. Use -v for rich summaries.
"""
import os
import argparse
import shutil
import subprocess
import sys
from typing import List

try:  # Optional rich dependency for nicer verbose output
    from rich.console import Console
    from rich.table import Table

    console = Console()
    RICH_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover
    console = None
    RICH_AVAILABLE = False


def _is_ignored(path: str, ignore_patterns: List[str]) -> bool:
    import fnmatch

    return any(fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(os.path.basename(path), pattern) for pattern in ignore_patterns)


def _run_fd_for_hidden(root: str, ignore_patterns: List[str]) -> List[str] | None:
    """Use fd to find hidden files/dirs quickly; returns None on failure."""
    if shutil.which("fd") is None:
        return None

    cmd = ["fd", "-H", "--type", "f", "--type", "d", "--absolute-path", r"^\..*", root]
    for pattern in ignore_patterns:
        cmd.extend(["--exclude", pattern])

    result = subprocess.run(
        cmd,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        sys.stderr.write(f"fd scan failed (exit {result.returncode}): {result.stderr.strip()}\n")
        return None
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def find_hidden_items(path='.', ignore_patterns: List[str] | None = None):
    """
    Recursively scans the given path for hidden files and folders (start with dot).
    """
    hidden_items = []
    ignore_patterns = ignore_patterns or []
    
    for root, dirs, files in os.walk(path, topdown=True):
        # Find hidden directories
        for dir_name in list(dirs):
            candidate = os.path.join(root, dir_name)
            if dir_name.startswith('.') and not _is_ignored(candidate, ignore_patterns):
                hidden_items.append(candidate)
            # Prevent descending into hidden/ignored directories
            if dir_name.startswith('.') or _is_ignored(candidate, ignore_patterns):
                dirs.remove(dir_name)
        
        # Find hidden files
        for file_name in files:
            if file_name.startswith('.'):
                candidate = os.path.join(root, file_name)
                if not _is_ignored(candidate, ignore_patterns):
                    hidden_items.append(candidate)
    
    return hidden_items

def main():
    """CLI entry point for hidden file finder."""
    parser = argparse.ArgumentParser(description="Recursively find hidden files and folders.")
    
    # Adding optional argument for path, default is current directory
    parser.add_argument('-p', '--path', type=str, default='.',
                        help="The path to recursively scan for hidden files/folders. Defaults to current directory.")
    parser.add_argument('-v', '--verbose', action='store_true',
                        help="Show summary/table (uses rich when installed).")
    parser.add_argument('-r', '--raw', action='store_true',
                        help="(Deprecated) Print hidden items only (one per line). Default behavior already does this.")
    parser.add_argument('--ignore', action='append', default=[],
                        help="Glob pattern to ignore (can be repeated).")
    parser.add_argument('--engine', choices=["auto", "fd", "python"], default="auto",
                        help="Engine: auto prefers fd when available, else python.")
    
    args = parser.parse_args()
    
    path_to_scan = os.path.abspath(args.path)  # Ensure we are working with absolute paths
    
    # Ensure the path exists
    if not os.path.exists(path_to_scan):
        print(f"Error: The specified path '{path_to_scan}' does not exist.")
        return
    
    ignore_patterns = [pattern.strip() for pattern in args.ignore if pattern and pattern.strip()]

    use_fd = args.engine in {"auto", "fd"}
    fd_results = _run_fd_for_hidden(path_to_scan, ignore_patterns) if use_fd else None
    engine_used = "fd" if fd_results is not None else "python"

    if fd_results is not None:
        hidden_items = fd_results
    else:
        if args.engine == "fd" and shutil.which("fd") is None:
            print("fd not found; falling back to python engine.", file=sys.stderr)
        hidden_items = find_hidden_items(path_to_scan, ignore_patterns)

    count = len(hidden_items)
    
    if args.verbose:
        print(f"[hidden] engine: {engine_used}")
        if RICH_AVAILABLE:
            title = f"{count:,} hidden item(s) in {path_to_scan} [engine: {engine_used}]"
            table = Table(title=title, box=None, pad_edge=False)
            table.add_column("#", justify="right", style="dim", no_wrap=True)
            table.add_column("Path", style="white")
            for idx, item in enumerate(hidden_items, start=1):
                table.add_row(str(idx), item)
            console.print(table)
        else:
            if hidden_items:
                print(f"{count:,} Hidden items found in {path_to_scan} [engine: {engine_used}]:")
                for item in hidden_items:
                    print(item)
            else:
                print(f"No hidden items found in {path_to_scan}. [engine: {engine_used}]")

    for item in hidden_items:
        print(item)

if __name__ == '__main__':
    main()
