#!/usr/bin/env python3
"""
File search utility with optional media information display.

Recursively searches directories for files matching all specified text patterns,
with support for displaying media file resolution and codec information.
"""
import argparse
import os
import time
from dataclasses import dataclass, field
from typing import List
import ffmpeg  # type: ignore
from .bytes import byte_size


def media_info(filepath: str, verbose: bool = False) -> str:
    """
    Retrieves the resolution of a video file.

    Args:
    filepath (str): The path to the video file.

    Returns:
    str: The resolution of the video as a string in the format 'widthxheight',
         or an error message if the resolution cannot be determined.
    """
    try:
        probe = ffmpeg.probe(filepath)
        video_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
        if video_stream:
            width = video_stream['width']
            height = video_stream['height']
            codec = video_stream['codec_name']
            return f"{width}x{height} {codec}"
    except ffmpeg.Error as e:
        error = f'ffmpeg error: {e.stderr.decode()}'
    except Exception as e:
        error = f'Error: {e}'
    if verbose:
        return error
    else:
        return ''


DEFAULT_FOLDER_LIST = [
    "/home/rdubar/projects/pythonProject/openerp-addons",
    "/mnt/expansion/Media/Movies/",
    "/mnt/archive/Media/TV Shows/",
]

@dataclass
class SearchReport:
    """Encapsulates file search results and metadata."""
    search_terms: List[str]
    folders : List[str] = field(default_factory=list)
    results: List[str] = field(default_factory=list)
    total_files_searched: int = 0
    search_time: float = 0.0

    def display_files(self, number=10, all=False, media=False):
        """Display search results with file size and optional media info."""
        matches = "match" if len(self.results) == 1 else "matches"
        print(f"Found {len(self.results):,} {matches} in {self.total_files_searched:,} files in {self.search_time:.2f} seconds.")
        if all:
            number = len(self.results)
        for result in self.results[:number]:
            size = byte_size(os.path.getsize(result))
            print(f'{size:>9}  {result}')
            if media:
                info = media_info(result)
                if info:
                    print(f"{'':>10}  {info}")
        if len(self.results) > number:
            print("...and more")

def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for file search."""
    parser = argparse.ArgumentParser(description='Search for files and folders containing all specified texts.')
    parser.add_argument('-a', '--all', action='store_true', help='Show all matching results.')
    parser.add_argument('-f', '--folder', type=str, default='', help='Folder to search.')
    parser.add_argument('-m', '--media', action='store_true', help='Show media info for matching files')
    parser.add_argument('-n', '--number', type=int, default=10, help='Number of results shown')
    parser.add_argument('-u', '--user', action='store_true', help='Search the user\'s home folder.')

    parser.add_argument('texts', nargs='+', help='Texts to search for (all must match).')
    return parser.parse_args()

def find_files(folders: List[str], texts: List[str]) -> SearchReport:
    """Recursively search for files containing all specified text patterns."""
    start_time = time.perf_counter()
    report = SearchReport(search_terms=texts)
    texts = [text.lower() for text in texts]
    for folder in folders:
        report.folders.append(folder)
        for root, dirs, files in os.walk(folder):
            for file in files:
                report.total_files_searched += 1
                filepath = os.path.join(root, file)
                if all(text in filepath.lower() for text in texts):
                    report.results.append(filepath)
    report.search_time = time.perf_counter() - start_time
    return report

def main():
    """CLI entry point for file search utility."""
    args = parse_args()

    folders = [args.folder] if args.folder else [f for f in DEFAULT_FOLDER_LIST if os.path.exists(f)]
    if not folders or args.user:
        home_folder = os.path.expanduser('~')
        folders.append(home_folder)

    print(f"Searching in folders: {', '.join(folders)}")
    print(f"Looking for files containing all of: {', '.join(args.texts)}")

    if args.media:
        print('Showing media info for matching files.')

    clock = time.perf_counter()
    report = find_files(folders, args.texts)
    report.display_files(number=args.number, all=args.all, media=args.media)
    print(f"Completed in {time.perf_counter() - clock:.2f} seconds.")

if __name__ == "__main__":
    main()
