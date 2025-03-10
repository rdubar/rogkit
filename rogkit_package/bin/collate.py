import os
import sys
import argparse

def clean_name(name):
    """ create a file friendly name from a given string """
    return name.replace(" ", "_").lower()

def collate_files(directory, output_file=None, match=None, ignore_case=False, report=False):
    """Recursively collates all text and code files from a given directory into one file."""
    matched = 0
    total = 0

    if match and ignore_case:
        match = match.lower()  # Ensure match text is lowercase before processing
        
    if not output_file:
        if match:
            output_file = f"collated_{clean_name(match)}.txt"
        elif directory:
            output_file = f"collated_{clean_name(directory)}.txt"
        else:
            output_file = "collated_files.txt"

    # Exclude directories
    exclude_dirs = ["__pycache__", "eggs", "venv", ".git", ".vscode", ".idea", ".ropeproject", ".mypy_cache", ".pytest_cache"]

    output = []
    for root, _, files in os.walk(directory):
        
        # Skip excluded directories
        if any(excluded in root.split(os.sep) for excluded in exclude_dirs):
            continue
        
        for file in files:
            file_path = os.path.join(root, file)

            # Only include text and coding files based on extension
            if file.endswith((".txt", ".py", ".java", ".cpp", ".html", ".css", ".js", ".json", ".md")):
                try:
                    total += 1
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()

                        # If match is specified, check if it exists in content
                        if match:
                            content_to_check = content.lower() if ignore_case else content
                            if match not in content_to_check:
                                continue

                        output.append(f"\n--- {file_path} ---\n")
                        output.append(content + "\n")
                        matched += 1
                except Exception as e:
                    if report:
                        print(f"Skipping {file_path}: {e}")
                    # out_file.write(f"\n--- {file_path} ---\n[Error reading file: {e}]\n")

    if report:
        print(f"Matched {matched:,} out of {total:,} files.")
        
    if not matched:
        print("No files matched the specified text.")
        return

    # write & report
    try:
        with open(output_file, "w", encoding="utf-8") as out_file:
            out_file.write("".join(output))
            if report:
                print(f"Collated files written to: {output_file}")
    except Exception as e:
        print(f"Failed to write to {output_file}: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Collate text and code files from a directory into one file.")
    parser.add_argument("-m", "--match", type=str, default=None, help="Match text to include in the collated file.")
    parser.add_argument("-i", "--ignore", action="store_true", help="Ignore case in text matches.")
    parser.add_argument("-p", "--path", type=str, default=os.getcwd(), help="Path of the directory to collate files from.")
    parser.add_argument("-o", "--output", type=str, default=None, help="Output file name.")
    parser.add_argument("-q", "--quiet", action="store_true", help="Quiet mode: do not print a report summary after processing.")

    args = parser.parse_args()
    
    if not args.match and args.path:
        print("Please specify a match text and path.")
        sys.exit(1)

    # Validate path
    if not os.path.exists(args.path):
        print("The specified path does not exist.")
        sys.exit(1)

    print(f"Collating files from: {args.path} to {args.output}")
    if args.match:
        print(f'Matching text: "{args.match}" (Ignore case: {"Yes" if args.ignore else "No"})')

    collate_files(
        args.path,
        output_file=args.output,
        match=args.match,
        ignore_case=args.ignore,
        report=not args.quiet
    )