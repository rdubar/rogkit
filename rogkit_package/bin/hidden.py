import os
import argparse

def find_hidden_items(path='.'):
    """
    Scans the given path for hidden files and folders.
    Hidden files and folders typically start with a dot (.)
    """
    hidden_items = []
    try:
        with os.scandir(path) as entries:
            for entry in entries:
                if entry.name.startswith('.'):
                    hidden_items.append(entry.path)
    except PermissionError:
        print(f"Permission denied: {path}")
    return hidden_items

def main():
    parser = argparse.ArgumentParser(description="Find hidden files and folders.")
    
    # Adding optional argument for path, default is current directory
    parser.add_argument('-p', '--path', type=str, default='.',
                        help="The path to scan for hidden files/folders. Defaults to current directory.")
    
    args = parser.parse_args()
    
    path_to_scan = args.path
    hidden_items = find_hidden_items(path_to_scan)
    
    if hidden_items:
        print(f"Hidden items found in {path_to_scan}:")
        for item in hidden_items:
            print(item)
    else:
        print(f"No hidden items found in {path_to_scan}.")
    

if __name__ == '__main__':
    main()
