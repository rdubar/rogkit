"""
Internet Archive padding file remover.

Recursively finds and optionally deletes .____padding_file directories
created by Internet Archive downloads.
"""
import os
import argparse
import shutil


def find_padding_files(path='.'):
    """
    Recursively scans the given path for padding files created by Internet Archive.
    These files typically reside in directories with names like .____padding_file.
    """
    padding_files = []
    
    for root, dirs, files in os.walk(path, followlinks=False):  # Disable following symbolic links
        for dir_name in dirs:
            if '.____padding_file' in dir_name:
                padding_dir = os.path.join(root, dir_name)
                padding_files.append(padding_dir)
    
    return padding_files

def delete_padding_files(padding_dirs):
    """
    Deletes the padding files found in the provided directories.
    """
    for dir_path in padding_dirs:
        try:
            shutil.rmtree(dir_path)
            print(f"Deleted: {dir_path}")
        except Exception as e:
            print(f"Error deleting {dir_path}: {e}")

def main():
    """CLI entry point for padding file remover."""
    parser = argparse.ArgumentParser(description="Recursively find and optionally delete Internet Archive padding files.")
    
    # Adding optional argument for path, default is current directory
    parser.add_argument('-p', '--path', type=str, default='.',
                        help="The path to recursively scan for padding files. Defaults to current directory.")
    
    # Option to remove the padding files
    parser.add_argument('-d', '--delete', action='store_true',
                        help="Delete the found padding files.")
    
    args = parser.parse_args()
    
    # Ensure the path or working directory exists
    if not os.path.exists(args.path):
        print(f"Error: The specified path '{args.path}' does not exist.")
        return
    
    # Ensure the current working directory exists
    try:
        os.getcwd()  # Attempt to get the current working directory
    except FileNotFoundError:
        print("Error: The current working directory no longer exists.")
        return
    
    path_to_scan = os.path.abspath(args.path)
    padding_files = find_padding_files(path_to_scan)
    
    if padding_files:
        print(f"Padding directories found in {path_to_scan}:")
        for file in padding_files:
            print(file)
        
        if args.delete:
            confirmation = input("Are you sure you want to delete these padding files? (y/n): ").lower()
            if confirmation == 'y':
                delete_padding_files(padding_files)
    else:
        print(f"No padding directories found in {path_to_scan}.")

if __name__ == '__main__':
    main()
