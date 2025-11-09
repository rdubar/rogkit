#!/usr/bin/env python3
"""
File purge utility for removing junk files.

Recursively searches for and deletes files matching patterns from a purge list
(e.g., torrent metadata, sample files, zone identifiers). Includes safety checks
to avoid deleting actual media files.
"""
import argparse
import os
import fnmatch
from dataclasses import dataclass, field

from ..bin.bytes import byte_size
from ..bin.delete import safe_delete


DEFAULT_FOLDER_LIST = [
    "/Users/rdubar/apv/openerp-addons",
    "/mnt/media1/Media/",
    "/mnt/media2/Media/",
    "/mnt/media3/Media/",
]


def sanitize_pattern(pattern: str) -> str:
    """
    Normalise purge patterns for case-insensitive fnmatch usage and make square
    brackets literal so entries like "[TGx]Downloaded..." behave as expected.
    """
    pattern = pattern.strip()
    if not pattern:
        return pattern
    pattern = pattern.replace("[", "[[]").replace("]", "[]]")
    return pattern.lower()


def prepare_patterns(pattern_source):
    """Return a list of normalised patterns regardless of the input shape."""
    if isinstance(pattern_source, (list, tuple, set)):
        iterator = pattern_source
    else:
        iterator = [pattern_source]
    return [sanitize_pattern(p) for p in iterator if p]


def process_purge_list(raw_list):
    """
    Process a multi-line string into a list of non-empty lines.
    :param raw_list: A multi-line string.
    :return: A list of non-empty, stripped strings.
    """
    return [line.strip() for line in raw_list.strip().split("\n") if line.strip()]

# Updated PURGE_LIST with patterns to include broader matches
PURGE_LIST = process_purge_list(
    """
Zone.Identifier
RARBG_DO_NOT_MIRROR.exe
RARBG.txt
RARBG.com.txt
WWW.YIFY-TORRENTS.COM.jpg
[TGx]Downloaded from torrentgalaxy.to .txt
*torrentgalaxy.to*.txt
*downloaded from torrentgalaxy*.txt
NEW upcoming releases by Xclusive.txt
Downloaded From PublicHD.SE.txt
00.nfo
TSYifyUP... (TOR).txt
Torrent*ownloaded*rom *.txt
YIFYStatus.com.txt
WWW.YTS.*.jpg
sample.m*
YTSProxies.*
VISIT ME ON FACEBOOK.txt
AhaShare.com.txt
YTSYifyUP... (TOR).txt
._*
"""
)

@dataclass
class PurgeResults:
    """Encapsulates purge results including files to delete and total files scanned."""
    files_to_delete: list = field(default_factory=list)
    total_files: int = 0

def matches_pattern(path, patterns, relative=None):
    """
    Check if a file matches any pattern from the list.
    Supports wildcards using fnmatch and is case-insensitive.
    """
    filename_lower = os.path.basename(path).lower()
    path_lower = path.lower().replace(os.sep, "/")
    rel_lower = (
        relative.lower().replace(os.sep, "/")
        if relative is not None
        else filename_lower
    )
    for pattern in patterns:
        if fnmatch.fnmatch(filename_lower, pattern):
            return True
        if fnmatch.fnmatch(path_lower, pattern):
            return True
        if rel_lower and fnmatch.fnmatch(rel_lower, pattern):
            return True
    return False

def search_and_collect_files(folders, patterns):
    """Recursively search folders for files matching purge patterns."""
    results = PurgeResults()
    if not isinstance(folders, list):
        folders = [folders]
    for folder in folders:
        for root, dirs, files in os.walk(folder):
            for file in files:
                filepath = os.path.join(root, file)
                relpath = os.path.relpath(filepath, folder).replace(os.sep, "/")
                if matches_pattern(filepath, patterns, relpath):
                    results.files_to_delete.append(filepath)
                results.total_files += 1
    return results
        
def _is_sample_media_file(path):
    """Check if file is a sample media file (not an actual media file)."""
    file = os.path.basename(path)
    return file.lower().startswith('sample.') or file.lower().endswith('.sample')

def delete_files(file_list):
    """Delete files from list, skipping actual media files for safety."""
    for file in file_list:
        # check for media files
        if file.endswith(('.mkv', '.mp4', '.avi', '.srt')) and not _is_sample_media_file(file):
            print(f"Skipping media file: {file}")
            continue
        safe_delete(file)

def main():
    """CLI entry point for file purge utility."""
    parser = argparse.ArgumentParser(
        description="Search and delete files based on a pattern."
    )
    parser.add_argument(
        "pattern",
        nargs="?",
        default=PURGE_LIST,
        help="Pattern to search for [or use defaults].",
    )
    parser.add_argument(
        "-d", "--dsstore", action="store_true", help="Include .DS_Store files."
    )
    parser.add_argument(
        "-c", "--confirm", action="store_true", help="Confirm deletion of files."
    )
    parser.add_argument("-f", "--folder", type=str, help="Folder to search.")
    parser.add_argument(
        "-p", "--purge_list", action="store_true", help="Show the purge list."
    )
    args = parser.parse_args()

    if args.purge_list:
        print("Showing the purge list of files to purge:")
        for item in PURGE_LIST:
            print(item)
        return

    folder_list = [args.folder] if args.folder else DEFAULT_FOLDER_LIST
    folders = [x for x in folder_list if os.path.exists(x)]

    if not folders:
        print("No valid folder found. Exiting.")
        return

    patterns = prepare_patterns(args.pattern)
    if args.dsstore:
        patterns.append(sanitize_pattern(".DS_Store"))

    if args.dsstore:
        print("Including .DS_Store files.")

    print(f"Searching {folders} for files to purge...")

    results = search_and_collect_files(folders, patterns)
    print(f"Found {len(results.files_to_delete):,} files to delete from {results.total_files:,} files scanned.")

    if args.confirm:
        delete_files(results.files_to_delete)
    elif results.files_to_delete:
        print("Files to be deleted (use --confirm to actually delete):")
        for file in results.files_to_delete:
            size = os.path.getsize(file)
            print(f"{byte_size(size):>10}   {file}")

if __name__ == "__main__":
    main()
