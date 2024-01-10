#!/usr/bin/env python3
import argparse
import os
import time
from dataclasses import dataclass, field

DEFAULT_FOLDER_LIST = ["/home/rdubar/projects/pythonProject/openerp-addons"]
EXCLUDE_PATTERNS = ["/.idea/"]

@dataclass
class SearchResults:
    matched_files: list = field(default_factory=list)
    skipped_files: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    total_files: int = 0

def is_valid_file(file):
    return os.path.splitext(file)[1] in ['.py', '.xml', '.js', '.css', '.txt', '.md', '.log', '.po', '.pot']

def is_excluded_path(filepath):
    return any(excluded in filepath for excluded in EXCLUDE_PATTERNS)

def file_contains_text(filepath, search_terms, whole_phrase):
    try:
        with open(filepath, 'r') as f:
            content = f.read().lower()
            if whole_phrase:
                return search_terms in content
            else:
                return all(term in content for term in search_terms)
    except Exception as e:
        raise IOError(f"Error reading file {filepath}: {e}")

def search_folder(folder, search_terms, whole_phrase):
    results = SearchResults()
    for root, dirs, files in os.walk(folder):
        for file in files:
            results.total_files += 1
            filepath = os.path.join(root, file)
            if is_excluded_path(filepath) or not is_valid_file(file):
                results.skipped_files.append(filepath)
                continue
            try:
                if file_contains_text(filepath, search_terms, whole_phrase):
                    results.matched_files.append(filepath)
            except IOError as e:
                results.errors.append(f"{filepath}: {e}")

    return results

def main():
    parser = argparse.ArgumentParser(description='Search a folder for text.')
    parser.add_argument('text', nargs='+', help='Text to search for.')
    parser.add_argument('-f', '--folder', type=str, default='', help='Folder to search.')
    parser.add_argument('-s', '--show-skipped', action='store_true', help='Show skipped files.')
    parser.add_argument('-e', '--show-errors', action='store_true', help='Show errors.')
    parser.add_argument('-m', '--show-matches', action='store_true', help='Show matches.')
    args = parser.parse_args()

    folder = args.folder or next((f for f in DEFAULT_FOLDER_LIST if os.path.exists(f)), '')
    if not folder:
        print("No valid folder found.")
        return

    whole_phrase = len(args.text) == 1 and args.text[0].startswith('"') and args.text[0].endswith('"')
    search_terms = ' '.join(args.text).strip('"').lower().split() if not whole_phrase else args.text[0].strip('"').lower()

    print(f"Searching for '{args.text}' in {folder}...")

    results = search_folder(folder, search_terms, whole_phrase)

    print(f"Found {len(results.matched_files):,} matches in {results.total_files:,} files. "
          f"(Skipped {len(results.skipped_files):,} files, Encountered {len(results.errors):,} errors.)")

    if args.show_matches or len(results.matched_files) < 10:
        print(f"Showing {len(results.matched_files):,} matches:")
        for file in results.matched_files:
            print(file)

    if args.show_skipped:
        print(f"Showing {len(results.skipped_files):,} skipped files:")
        for file in results.skipped_files:
            print(file)

    if args.show_errors:
        print(f"Showing {len(results.errors):,} errors:")
        for error in results.errors:
            print(error)


if __name__ == "__main__":
    main()
