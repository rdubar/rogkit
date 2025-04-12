#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import sys
import argparse

def clean_name(name):
    """Create a file-friendly name from a given string."""
    return name.replace(" ", "_").lower()

def collate_files(directory, output_file=None, match=None, ignore_case=False, report=False, sort_files=False, verbose=False):
    """Recursively collates all text and code files from a given directory into one file."""
    matched = 0
    total = 0
    output = []

    if match is not None and ignore_case:
        match = match.lower()

    if not output_file:
        if match:
            output_file = f"collated_{clean_name(match)}.txt"
        elif directory:
            output_file = f"collated_{clean_name(os.path.basename(directory))}.txt"
        else:
            output_file = "collated_files.txt"

    exclude_dirs = ["__pycache__", "eggs", "v27", "venv", ".git", ".vscode", ".idea", ".ropeproject", ".mypy_cache", ".pytest_cache"]
    file_list = []

    for root, _, files in os.walk(directory):
        if any(excluded in root.split(os.sep) for excluded in exclude_dirs):
            continue
        for file in files:
            file_path = os.path.join(root, file)
            if file.endswith((".txt", ".py", ".java", ".cpp", ".html", ".css", ".js", ".json", ".md", ".mako", ".csv", ".xml", ".yaml", ".yml")):
                file_list.append(file_path)

    if sort_files:
        file_list.sort()

    for file_path in file_list:
        try:
            total += 1
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                if match is not None:
                    check_text = content.lower() if ignore_case else content
                    if match not in check_text:
                        continue
                output.append("\n--- {} ---\n".format(file_path))
                output.append(content + "\n")
                matched += 1
                if verbose:
                    print("[MATCH] {}: {}".format(file_path, match))
        except Exception as e:
            if report:
                print("[SKIP] {}: {}".format(file_path, e))

    if report:
        print("[SUMMARY] Matched {:,} out of {:,} files.".format(matched, total))

    if not matched:
        print("No files matched.")
        return

    try:
        with open(output_file, "w", encoding="utf-8") as out_file:
            out_file.write("".join(output))
        if report:
            print("[DONE] Collated files written to: {}".format(output_file))
    except Exception as e:
        print("[ERROR] Failed to write to {}: {}".format(output_file, e))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Collate text and code files from a directory into one file.")
    parser.add_argument("-a", "--all", action="store_true", help="Include all files regardless of match text.")
    parser.add_argument("-m", "--match", type=str, default=None, help="Text to match in file content.")
    parser.add_argument("-i", "--ignore", action="store_true", help="Ignore case in match text.")
    parser.add_argument("-p", "--path", type=str, default=os.getcwd(), help="Directory path to scan (default: current directory).")
    parser.add_argument("-o", "--output", type=str, default=None, help="Output file name.")
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress summary output.")
    parser.add_argument("-s", "--sort", action="store_true", help="Sort files alphabetically before collating.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output.")

    args = parser.parse_args()

    if not args.all and not args.match:
        print("You must specify either --all or --match.")
        sys.exit(1)

    if not os.path.exists(args.path):
        print("[ERROR] The path '{}' does not exist.".format(args.path))
        sys.exit(1)

    if args.all:
        args.match = None  # Include all files

    if not args.quiet:
        print("[START] Collating from: {}".format(args.path))
        if args.match is not None:
            print("[FILTER] Matching: '{}' (ignore case: {})".format(args.match, "Yes" if args.ignore else "No"))
        if args.sort:
            print("[INFO] Files will be sorted alphabetically.")

    collate_files(
        args.path,
        output_file=args.output,
        match=args.match,
        ignore_case=args.ignore,
        report=not args.quiet,
        sort_files=args.sort,
        verbose=args.verbose,
    )