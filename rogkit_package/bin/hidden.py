import os
import argparse

def find_hidden_items(path='.'):
    """
    Recursively scans the given path for hidden files and folders.
    Hidden files and folders typically start with a dot (.)
    """
    hidden_items = []
    
    for root, dirs, files in os.walk(path, topdown=True):
        # Find hidden directories
        for dir_name in dirs:
            if dir_name.startswith('.'):
                hidden_items.append(os.path.join(root, dir_name))
        
        # Find hidden files
        for file_name in files:
            if file_name.startswith('.'):
                hidden_items.append(os.path.join(root, file_name))
    
    return hidden_items

def main():
    parser = argparse.ArgumentParser(description="Recursively find hidden files and folders.")
    
    # Adding optional argument for path, default is current directory
    parser.add_argument('-p', '--path', type=str, default='.',
                        help="The path to recursively scan for hidden files/folders. Defaults to current directory.")
    
    args = parser.parse_args()
    
    path_to_scan = args.path
    
    # Ensure the path exists
    if not os.path.exists(path_to_scan):
        print(f"Error: The specified path '{path_to_scan}' does not exist.")
        return
    
    hidden_items = find_hidden_items(path_to_scan)
    
    if hidden_items:
        print(f"Hidden items found in {path_to_scan}:")
        for item in hidden_items:
            print(item)
    else:
        print(f"No hidden items found in {path_to_scan}.")

if __name__ == '__main__':
    main()
