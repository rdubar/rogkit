"""
Hidden file and folder finder/remover.

Recursively scans directories for hidden files and folders (starting with dot)
and optionally deletes them with confirmation.
"""
import os
import argparse
import shutil


def find_hidden_items(path='.'):
    """
    Recursively scans the given path for hidden files and folders.
    Hidden files and folders typically start with a dot (.)
    """
    hidden_items = []
    
    for root, dirs, files in os.walk(path, topdown=True):
        # Modify 'dirs' in place to avoid traversing hidden directories
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        
        # Find hidden directories
        for dir_name in dirs:
            if dir_name.startswith('.'):
                hidden_items.append(os.path.join(root, dir_name))
        
        # Find hidden files
        for file_name in files:
            if file_name.startswith('.'):
                hidden_items.append(os.path.join(root, file_name))
    
    return hidden_items

def delete_hidden_items(hidden_items):
    """
    Deletes hidden files and directories.
    """
    for item in hidden_items:
        try:
            if os.path.isdir(item):
                shutil.rmtree(item)  # Use rmtree for directories, as they may not be empty
            else:
                os.remove(item)
            print(f"Deleted: {item}")
        except PermissionError:
            print(f"Permission denied: {item}")
        except Exception as e:
            print(f"Error deleting {item}: {e}")

def main():
    """CLI entry point for hidden file finder."""
    parser = argparse.ArgumentParser(description="Recursively find and optionally delete hidden files and folders.")
    
    # Adding optional argument for path, default is current directory
    parser.add_argument('-p', '--path', type=str, default='.',
                        help="The path to recursively scan for hidden files/folders. Defaults to current directory.")
    parser.add_argument('--delete', action='store_true',
                        help="Delete all hidden files and folders found in the specified path.")
    parser.add_argument('-v', '--verbose', action='store_true',
                        help="Print detailed output during scanning and deletion.")
    
    args = parser.parse_args()
    
    path_to_scan = os.path.abspath(args.path)  # Ensure we are working with absolute paths
    
    # Ensure the path exists
    if not os.path.exists(path_to_scan):
        print(f"Error: The specified path '{path_to_scan}' does not exist.")
        return
    
    hidden_items = find_hidden_items(path_to_scan)
    count = len(hidden_items)
    
    if hidden_items:
        print(f"{count:,} Hidden items found in {path_to_scan}:")
        if args.verbose:
            for item in hidden_items:
                print(item)
    else:
        print(f"No hidden items found in {path_to_scan}.")
        
    if hidden_items and args.delete:
        confirm = input(f"Are you sure you want to delete these {count} items? (y/n): ")
        if confirm.lower() != 'y':
            print("Aborted.")
            return
        print("Deleting hidden items...")
        delete_hidden_items(hidden_items)

if __name__ == '__main__':
    main()
