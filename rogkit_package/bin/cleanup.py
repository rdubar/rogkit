import os
import argparse
import shutil
import platform
from pathlib import Path

""" 
Clean up script for macOS and Raspberry Pi
This script scans for temporary and cache files in common directories
and allows the user to delete them based on a specified cleanup level.
It supports three levels of cleanup:
1. Level 1: Safe cleanup (e.g., cache directories)
2. Level 2: Moderate cleanup (e.g., Downloads, Trash)
3. Level 3: Aggressive cleanup (e.g., npm cache, thumbnails, logs
"""

def sizeof_fmt(num, suffix="B"):
    for unit in ["", "K", "M", "G", "T"]:
        if abs(num) < 1024:
            return f"{num:.1f}{unit}{suffix}"
        num /= 1024
    return f"{num:.1f}P{suffix}"

def collect_paths(level):
    system = platform.system()
    home = Path.home()

    level_1 = []
    level_2 = []
    level_3 = []

    # Level 1
    if system == "Darwin":
        level_1 += [home / ".Trash", home / "Library/Caches"]
    else:
        level_1 += [home / ".cache", Path("/var/tmp"), Path("/tmp")]

    # Level 2 (adds to level 1)
    # level_2 += level_1 + [home / "Downloads", home / ".local/share/Trash/files"]
    level_2 += level_1 + [home / ".local/share/Trash/files"]
    
    # Level 3 (adds to level 2)
    level_3 += level_2 + [home / ".npm", home / ".thumbnails"]
    if system != "Darwin":
        level_3.append(Path("/var/log"))

    if level == 1:
        return [p for p in level_1 if p.exists()]
    elif level == 2:
        return [p for p in level_2 if p.exists()]
    elif level == 3:
        return [p for p in level_3 if p.exists()]
    else:
        return []

def scan_and_report(paths, verbose=False):
    total_size = 0
    to_delete = []
    per_path_summary = {}

    for path in paths:
        path_total = 0
        path_files = []

        if path.is_file():
            size = path.stat().st_size
            total_size += size
            to_delete.append((path, size))
            path_total += size
            path_files.append((path, size))
        else:
            for root, _, files in os.walk(path):
                for f in files:
                    try:
                        file_path = Path(root) / f
                        size = file_path.stat().st_size
                        total_size += size
                        to_delete.append((file_path, size))
                        path_total += size
                        path_files.append((file_path, size))
                    except Exception:
                        continue

        if verbose:
            per_path_summary[path] = (path_total, len(path_files))

    return to_delete, total_size, per_path_summary

def delete_files(file_list):
    for file_path, _ in file_list:
        try:
            file_path.unlink()
        except IsADirectoryError:
            shutil.rmtree(file_path, ignore_errors=True)
        except Exception as e:
            print(f"Error deleting {file_path}: {e}")
            continue

def main():
    parser = argparse.ArgumentParser(description="Cleanup Script for macOS and Pi")
    parser.add_argument('--level', type=int, choices=[1, 2, 3], default=1,
                        help="Level of cleanup: 1 (safe), 2 (moderate), 3 (aggressive)")
    parser.add_argument('--confirm', action='store_true',
                        help="Actually delete files. Without this, it does a dry-run.")
    parser.add_argument('-v', '--verbose', action='store_true',
                    help="Enable verbose output for debugging purposes")

    args = parser.parse_args()

    print(f"Scanning with cleanup level {args.level}...")
    paths = collect_paths(args.level)
    files, total_size, summary = scan_and_report(paths, verbose=args.verbose)

    if not files:
        print("No files found to delete.")
        return

    if args.verbose:
        print("\nSummary per path:")
        for path, (size, count) in summary.items():
            print(f"{path}: {sizeof_fmt(size)} in {count:,} files")

        print("\nFiles to be deleted:")
        for path, size in files:
            print(f"{path} - {sizeof_fmt(size)}")

    print(f"\nTotal space that would be freed: {sizeof_fmt(total_size)} [{len(files):,} files]")

    if args.confirm:
        confirm = input("\nAre you sure you want to delete these files? (y/N): ").lower()
        if confirm == 'y':
            delete_files(files)
            print("Files deleted.")
        else:
            print("Aborted.")
    else:
        print("\nDry run complete. Use --confirm to actually delete files.")

if __name__ == "__main__":
    main()