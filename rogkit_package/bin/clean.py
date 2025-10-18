#!/usr/bin/env python3
import os
import fnmatch
import time
import subprocess
import argparse
from .tomlr import load_rogkit_toml

try:
    script_path = load_rogkit_toml()['clean']['script_path']
except KeyError:
    print("Error: '[clean][script_path]' section not found in ~/.config/rogkit/config.toml. Exiting.")
    script_path = None

"""
# Add to ~/.config/rogkit/config.toml: 
[clean]
script_path = '/home/rdubar/projects/pythonProject/openerp-addons/src/scripts/local/scripts/translation_clean.sh'
"""

def run_command(command):
    """Execute a shell command and return its output and error."""
    process = subprocess.run(command, capture_output=True, text=True, shell=True)
    return process.stdout, process.stderr

def find_files(directory, patterns):
    """Get all files in a directory tree matching a set of patterns."""
    for root, dirs, files in os.walk(directory):
        for pattern in patterns:
            for filename in fnmatch.filter(files, pattern):
                yield os.path.join(root, filename)
                
def clean_files(file_list):
    """Run the external cleaning script on each file in the list."""
    for path in file_list:
        print(f'Running translation_clean.sh on {path}')
        command = f'{script_path} {path}'
        output, error = run_command(command)
        if error:
            print(f"Error: {error}")

def main():
    print("Translation Clean Script")

    default_minutes = 10
    root_directory = '/Users/rdubar/apv/openerp-addons/src/'
    desired_filenames = ['*.po', '*.pot']

    parser = argparse.ArgumentParser(description="Clean .po and .pot files modified within a certain time frame.")
    parser.add_argument("--confirm", action="store_true", help="Confirm that files should be cleaned")
    parser.add_argument('-m', "--minutes", type=int, default=default_minutes, help="Minutes to look back for modified files")
    parser.add_argument('-a', "--all", action="store_true", help="Clean all matching files, ignoring modification time")
    parser.add_argument('search', nargs='?', default=None, help="Optional: only clean translation paths containing this string")
    args = parser.parse_args()

    if not os.path.exists(root_directory):
        print(f"Root directory {root_directory} does not exist. Exiting.")
        return

    if not script_path:
        print(f"Script path not found at {script_path}. Exiting.")
        return
    
    matched_file = None
    if args.search:
        if os.path.isfile(args.search):
            matched_file = args.search
        else:
            test_path = os.path.join(root_directory, args.search)
            if os.path.isfile(test_path):
                matched_file = test_path
            
    if matched_file:
        print(f"Directly cleaning specified file: {matched_file}")
        clean_files([matched_file])
        return

    if not args.search:
        # just show help
        parser.print_help()
        return
        
    print(f"Searching for files named {', '.join(desired_filenames)} in {root_directory}")
    all_files = list(find_files(root_directory, desired_filenames))
    total_files = len(all_files)

    if args.all:
        files_to_clean = all_files
        print(f"Matching ALL {total_files:,} files.")
    else:
        time_limit = time.time() - (args.minutes * 60)
        files_to_clean = [file for file in all_files if os.path.getmtime(file) > time_limit]
        print(f"Found {len(files_to_clean)} of {total_files:,} files modified within the last {args.minutes} minutes. (Use --all to match all files).")

    # New: warn if no files selected
    if not files_to_clean:
        print(f"⚠️  No files found to clean. Tip: use --all to clean/search across all files.")

    # New: Filter by search string if provided
    if args.search:
        before_filter = len(files_to_clean)
        search_term = args.search.lower()
        files_to_clean = [file for file in files_to_clean if search_term in file.lower()]
        print(f"After fuzzy search filter '{args.search}': {len(files_to_clean)} files (from {before_filter})")
        for file in files_to_clean:
            print(f"  {file}")

    if not args.confirm:
        print("Test run only. No files were modified. Use --confirm to proceed.")
        return

    if not os.path.exists(script_path):
        print(f"Script path {script_path} does not exist. Exiting.")
        return

    clean_files(files_to_clean)

if __name__ == "__main__":
    main()