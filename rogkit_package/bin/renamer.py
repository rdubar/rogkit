#!/usr/bin/env python3
import os
import argparse
import sys

def rename_files(directory, old_pattern, new_pattern, confirm=False):
    """Recursively rename files matching old_pattern -> new_pattern."""
    renamed = 0
    for root, _, files in os.walk(directory):
        for file in files:
            if old_pattern not in file:
                continue

            old_path = os.path.join(root, file)
            new_name = file.replace(old_pattern, new_pattern)
            new_path = os.path.join(root, new_name)

            if old_path == new_path:
                continue

            print(f"Original: {old_path}")
            print(f"Renamed : {new_path}")

            if confirm:
                try:
                    os.rename(old_path, new_path)
                    renamed += 1
                except OSError as e:
                    print(f"⚠️  Error renaming {file}: {e}", file=sys.stderr)
            else:
                print("🟡 (dry-run, no changes made)")
            print()
    if confirm:
        print(f"✅ Done! Renamed {renamed} file(s).")
    else:
        print("💡 Add '--yes' to actually apply changes.")


def main():
    parser = argparse.ArgumentParser(
        description="Recursively rename files by replacing substrings in filenames."
    )
    parser.add_argument("directory", help="Target directory to scan")
    parser.add_argument("old", help="Old pattern to replace")
    parser.add_argument("new", help="New pattern to insert")
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Actually perform renames (without this, it's a dry-run)."
    )

    args = parser.parse_args()

    if not os.path.isdir(args.directory):
        sys.exit(f"❌ Error: {args.directory} is not a valid directory.")

    rename_files(args.directory, args.old, args.new, confirm=args.yes)


if __name__ == "__main__":
    main()