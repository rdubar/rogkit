#!/usr/bin/env python3
import argparse
import os
import time

DEFAULT_FOLDER_LIST = [
    "/home/rdubar/projects/pythonProject/openerp-addons",
    "/mnt/expansion/Media/Movies/",
]

def parse_args():
    parser = argparse.ArgumentParser(description='Search for files and folders containing all specified texts.')
    parser.add_argument('-a', '--all', action='store_true', help='Show all results')
    parser.add_argument('-f', '--folder', type=str, default='', help='Folder to search.')
    parser.add_argument('-n', '--number', type=int, default=10, help='Maximum number of results to show.')
    parser.add_argument('texts', nargs='+', help='Texts to search for (all must match).')
    return parser.parse_args()

def find_files(folder, texts):
    texts = [text.lower() for text in texts]
    for root, dirs, files in os.walk(folder):
        for file in files:
            filepath = os.path.join(root, file).lower()
            if all(text in filepath for text in texts):
                yield filepath

def main():
    args = parse_args()

    folder = args.folder or next((f for f in DEFAULT_FOLDER_LIST if os.path.exists(f)), '')
    print(f"Searching in {folder} for filenames containing all of: {', '.join(args.texts)}")
    clock = time.perf_counter()
    results = list(find_files(folder, args.texts))
    report = f"Found {len(results):,} matches in {time.perf_counter() - clock:.2f} seconds."
    print(report)
    if args.all:
        args.number = len(results)
    for result in results[:args.number]:  # Limit the results printed
        print(result)
    if len(results) > args.number:
        print(f"...and {len(results)-args.number} of {len(results)} more.")

if __name__ == "__main__":
    main()
