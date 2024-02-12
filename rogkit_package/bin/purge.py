#!/usr/bin/env python3
import argparse
import os
from dataclasses import dataclass, field

DEFAULT_FOLDER_LIST = ["/home/rdubar/projects/pythonProject/openerp-addons", "/mnt/expansion/Media/Movies/"]

def process_purge_list(raw_list):
    """
    Process a multi-line string into a list of non-empty lines.
    :param raw_list: A multi-line string.
    :return: A list of non-empty, stripped strings.
    """
    return [line.strip() for line in raw_list.strip().split('\n') if line.strip()]

# Use the function to process PURGE_LIST and PURGE_INCLUDE
PURGE_LIST = process_purge_list("""
Zone.Identifier
RARBG_DO_NOT_MIRROR.exe
RARBG.txt
WWW.YIFY-TORRENTS.COM.jpg
[TGx]Downloaded from torrentgalaxy.to .txt
NEW upcoming releases by Xclusive.txt
Downloaded From PublicHD.SE.txt
00.nfo
www.YTS.MX.jpg
WWW.YTS.RE.jpg
www.YTS.AM.jpg
TSYifyUP... (TOR).txt
YIFYStatus.com.txt
""")

@dataclass
class PurgeResults:
    files_to_delete: list = field(default_factory=list)
    total_files: int = 0

def matches_pattern(file, pattern):
    # Modify this function based on how you want to match the patterns
    for p in pattern:
        if p in file:
            return True
    return False

def search_and_collect_files(folder, pattern):
    results = PurgeResults()
    for root, dirs, files in os.walk(folder):
        for file in files:
            filepath = os.path.join(root, file)
            if matches_pattern(filepath, pattern):
                results.files_to_delete.append(filepath)
            results.total_files += 1
    return results

def delete_files(file_list):
    for file in file_list:
        try:
            os.remove(file)
            print(f"Deleted: {file}")
        except Exception as e:
            print(f"Failed to delete {file}: {e}")

def main():
    parser = argparse.ArgumentParser(description='Search and delete files based on a pattern.')
    parser.add_argument('pattern', nargs='?', default=PURGE_LIST, help='Pattern to search for [or use defaults].')
    parser.add_argument('-c', '--confirm', action='store_true', help='Confirm deletion of files.')
    parser.add_argument('-f', '--folder', type=str, default='', help='Folder to search.')
    parser.add_argument('-p', '--purge_list', action='store_true', help='Show the purge list.')
    args = parser.parse_args()

    folder = args.folder or next((f for f in DEFAULT_FOLDER_LIST if os.path.exists(f)), '')
    if not folder:
        print("No valid folder found. Exiting.")
        return
    
    print(f"Searching {folder} for files to purge...")

    if args.purge_list:
        print("Showing the purge list of files to purge:")
        for item in PURGE_LIST:
            print(item)
        return

    results = search_and_collect_files(folder, args.pattern)
    print(f"Found {len(results.files_to_delete):,} files to delete out of {results.total_files:,} files scanned.")

    if args.confirm:
        delete_files(results.files_to_delete)
    elif results.files_to_delete:
        print("Files to be deleted (use --confirm to actually delete):")
        for file in results.files_to_delete:
            print(file)

if __name__ == "__main__":
    main()
