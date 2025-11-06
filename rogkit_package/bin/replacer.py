#!/usr/bin/env python3
"""
Text find and replace utility.

Recursively searches text files for specified text patterns and optionally
replaces them with new text, with confirmation option for each replacement.
"""
import os
import argparse
import dataclasses


@dataclasses.dataclass
class SearchResults:
    """Encapsulates search results including matches, skipped files, and errors."""
    matches: list = dataclasses.field(default_factory=list)
    skipped: list = dataclasses.field(default_factory=list)
    errors: list = dataclasses.field(default_factory=list)
    total: int = 0

def skip_path(path):
    """Check if path should be skipped based on common directories to exclude."""
    return any(skip_path in path for skip_path in ['node_modules', '.git', '.venv', '.tox', '__pycache__', '/eggs/' , '/parts/', '/env/', '/etc/'])


def is_text_file(filename):
    """Check if filename has a text file extension."""
    # check if file is a text file
    text_file_extensions = ['.py', '.txt', '.html', '.xml', '.js', '.css', '.csv', '.rst', '.po', '.pot', '.mako']
    return any(filename.endswith(extension) for extension in text_file_extensions)

def find_text_files(path, find_text, debug=False):
    """Recursively search text files for specified text and return matching files."""
    results = SearchResults()
    if not find_text:
        return results
    for root, _, filenames in os.walk(path):
        for filename in filenames:
            results.total += 1
            if is_text_file(filename):
                file_path = os.path.join(root, filename)
                if skip_path(file_path):
                    results.skipped.append(file_path)
                    continue
                with open(file_path, 'r') as file:
                    try:
                        if find_text in file.read():
                            results.matches.append(file_path)
                    except Exception as e:
                        if debug:
                            print(f'Error reading {file_path}: {e}')
                        results.errors.append(f'{file_path}: {e}')
    return results

def replace_text_in_file(file_path, find_text, replace_text):
    """Replace text in a single file and return True if replacement was made."""
    with open(file_path, 'r') as file:
        content = file.read()
    if replace_text in content:
        return False
    content = content.replace(find_text, replace_text)
    with open(file_path, 'w') as file:
        file.write(content)
    return True

def get_args():
    """Parse command-line arguments for search and replace utility."""
    parser = argparse.ArgumentParser(description='Search and optionally replace text in files.')
    parser.add_argument("-p", '--path',  required=False, help='Path to search files in')
    parser.add_argument('-f', '--find_text', required=False, help='Text to find')
    parser.add_argument('--replace_text', help='Text to replace found text with')
    parser.add_argument('--confirm', action='store_true', help='Confirm before making each replacement')
    parser.add_argument('--debug', action='store_true', help='Run in debug mode')
    args = parser.parse_args()
    return args

def do_search_and_replace(args):
    """Execute search and optional replace operation based on arguments."""
    if args.find_text:
        print(f"Searching for {args.find_text} in {args.path}")
    else:
        print(f"Searching for text in {args.path}")
    results = find_text_files(args.path, args.find_text, debug=args.debug)
    print(f"Found {len(results.matches):,} matching files in {results.total:,} files (skipped {len(results.skipped):,}, errors {len(results.errors):,}).")
    if args.confirm and args.replace_text:
        print(f"Replacing {args.find_text} with {args.replace_text} in {len(results.matches):,} files.")
        for file_path in results.matches:
            if replace_text_in_file(file_path, args.find_text, args.replace_text):
                print(f"Replaced text in {file_path}")
            else:
                print(f"Text already replaced in {file_path}")

def main():
    """CLI entry point for text replacement utility."""
    args = get_args()

    over_ride = False

    print('Rogkit Replacer: Search and optionally replace text in files.')

    if over_ride: 
        # defaults for testing
        args.path = '/home/rdubar/projects/pythonProject/openerp-addons'
        
        # args.find_text = 'Die Lieferung ist inkl. <b>Liefertermin spätestens 48h</b>'
        # args.replace_text = 'Die Lieferung ist inkl. <b>Liefertermin und Preisen spätestens 48h</b>'

        # args.find_text = 'Delivery including the <b>delivery date</b>'
        # args.replace_text = 'Delivery including the <b>delivery date and prices</b>'
        args.confirm = False

    do_search_and_replace(args)

if __name__ == "__main__":
    main()
