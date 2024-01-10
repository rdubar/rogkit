#!/usr/bin/env python3
import argparse
import os
import time
from dataclasses import dataclass, field
from typing import List

DEFAULT_FOLDER_LIST = [
    "/home/rdubar/projects/pythonProject/openerp-addons",
    "/mnt/expansion/Media/Movies/",
    "/mnt/archive/Media/TV Shows/",
]

@dataclass
class SearchReport:
    search_terms: List[str]
    folders : List[str]
    results: List[str] = field(default_factory=list)
    total_files_searched: int = 0

def parse_args():
    parser = argparse.ArgumentParser(description='Search for files and folders containing all specified texts.')
    parser.add_argument('-a', '--all', action='store_true', help='Show all matching results.')
    parser.add_argument('-f', '--folder', type=str, default='', help='Folder to search.')
    parser.add_argument('-n', '--number', type=int, default=10, help='Number of results shown')
    parser.add_argument('-u', '--user', action='store_true', help='Search the user\'s home folder.')

    parser.add_argument('texts', nargs='+', help='Texts to search for (all must match).')
    return parser.parse_args()

def find_files(folders, texts):
    report = SearchReport(search_terms=texts)
    texts = [text.lower() for text in texts]
    for folder in folders:
        report.folders.append(folder)
        for root, dirs, files in os.walk(folder):
            for file in files:
                report.total_files_searched += 1
                filepath = os.path.join(root, file).lower()
                if all(text in filepath for text in texts):
                    report.results.append(filepath)
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
    search_time = time.perf_counter() - clock

    matches = "match" if len(report.results) == 1 else "matches"
    print(f"Found {len(report.results):,} {matches} in {report.total_files_searched:,} files in {search_time:.2f} seconds.")
    if args.all:
        args.number = len(report.results)
    for result in report.results[:args.number]:  # Limit the results printed
        print(result)
    if len(report.results) > args.number:
        print("...and more")

if __name__ == "__main__":
    main()
