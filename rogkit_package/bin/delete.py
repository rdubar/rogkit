"""
Safe file/folder deletion utility.

Provides safe deletion using system trash (send2trash) by default,
with option for permanent deletion when force flag is enabled.
"""
import os
import sys
import shutil
import argparse
from send2trash import send2trash
from colorama import Fore, Style, init

init(autoreset=True)


def safe_delete(path, force=False):
    """
    Deletes a file or folder.
    If force=True, permanently deletes using os.remove/rmtree.
    Otherwise, sends to trash (safe delete).
    """
    if not os.path.exists(path):
        print(Fore.RED + f"[ERROR] Path not found: {path}")
        return False

    try:
        if force:
            if os.path.isfile(path):
                os.remove(path)
            elif os.path.isdir(path):
                shutil.rmtree(path)
            print(Fore.MAGENTA + f"[DELETED] {path} (permanently)")
        else:
            send2trash(path)
            print(Fore.CYAN + f"[TRASHED] {path}")
        return True

    except Exception as e:
        print(Fore.RED + f"[ERROR] Failed to delete {path}: {e}")
        return False


def main():
    """CLI entry point for safe deletion utility."""
    parser = argparse.ArgumentParser(description="Delete a file or folder safely or forcefully.")
    parser.add_argument("path", nargs="+", help="File(s)/folder(s) to delete")
    parser.add_argument("-f", "--force", action="store_true", help="Force permanent deletion (use with caution)")

    args = parser.parse_args()
    safe_delete(args.path, args.force)


if __name__ == "__main__":
    main()