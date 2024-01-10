#!/usr/bin/env python3
import argparse
import os
import time
from dataclasses import dataclass, field

DEFAULT_FOLDER_LIST = [
    "/home/rdubar/projects/pythonProject/openerp-addons", 
    "/mnt/expansion/Media/Movies/",                   
    ]

# function to crawl a directory and return a list of the paths of all files or folders matching <text>
def find_files(folder, text):
    text = text.lower()
    results = []
    for root, dirs, files in os.walk(folder):
        for file in files:
            filepath = os.path.join(root, file)
            if text in file:
                results.append(filepath)
    return results

def main():
    parser = argparse.ArgumentParser(description='Search for files and folders matching <text>.')
    parser.add_argument('-f', '--folder', type=str, default='', help='Folder to search.')
    parser.add_argument('text', nargs='+', help='Text to search for.')
    args = parser.parse_args()

    folder = args.folder or next((f for f in DEFAULT_FOLDER_LIST if os.path.exists(f)), '')
    for text in args.text:
        print(f"Searching for '{text}' in {folder}...")
        clock = time.perf_counter()
        results = find_files(folder, text)
        report = f"Found {len(results):,} matches in {time.perf_counter() - clock:.2f} seconds."
        print(report)
        for result in results:
            print(result)
        if len(results) > 10:
            print(report)

if __name__ == "__main__":
    main()