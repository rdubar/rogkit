#!/usr/bin/env python3
import argparse
import os
import time
from dataclasses import dataclass, field
from typing import List, Tuple
from bytes import byte_size

DEFAULT_FOLDER_LIST = [
    "/home/rdubar/projects/pythonProject/openerp-addons",
    "/mnt/expansion/Media/Movies/",
    "/mnt/archive/Media/TV Shows/",
]

@dataclass
class SearchReport:
    search_terms: List[str]
    folders : List[str] = field(default_factory=list)
    results: List[str] = field(default_factory=list)
    total_files_searched: int = 0
    search_time: float = 0.0

    def display_files(self, number=10, all=False):
        matches = "match" if len(self.results) == 1 else "matches"
        print(f"Found {len(self.results):,} {matches} in {self.total_files_searched:,} files in {self.search_time:.2f} seconds.")
        if all:
            number = len(self.results)
        for result in self.results[:number]:
            size = byte_size(os.path.getsize(result))
            print(f'{size:>9}  {result}')
        if len(self.results) > number:
            print("...and more")

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Search for files and folders containing all specified texts.')
    parser.add_argument('-a', '--all', action='store_true', help='Show all matching results.')
    parser.add_argument('-f', '--folder', type=str, default='', help='Folder to search.')
    parser.add_argument('-n', '--number', type=int, default=10, help='Number of results shown')
    parser.add_argument('-u', '--user', action='store_true', help='Search the user\'s home folder.')

    parser.add_argument('texts', nargs='+', help='Texts to search for (all must match).')
    return parser.parse_args()

def find_files(folders: List[str], texts: List[str]) -> SearchReport:
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
    args = parse_args()

    folders = [args.folder] if args.folder else [f for f in DEFAULT_FOLDER_LIST if os.path.exists(f)]
    if not folders or args.user:
        home_folder = os.path.expanduser('~')
        folders.append(home_folder)

    print(f"Searching in folders: {', '.join(folders)}")
    print(f"Looking for files containing all of: {', '.join(args.texts)}")

    clock = time.perf_counter()
    report = find_files(folders, args.texts)
    report.display_files(number=args.number, all=args.all)

if __name__ == "__main__":
    main()
