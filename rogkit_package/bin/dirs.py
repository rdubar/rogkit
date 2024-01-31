import os
import argparse


def main():

    
    # create a dictionary of all files on the disk with their sizes
    # key = file name, value = file size
    file_size_dict = {}
    for root, dirs, files in os.walk('/'):
        for file in files:
            try:
                file_size_dict[file] = os.path.getsize(os.path.join(root, file))
            except Exception as e:
                print(file, e)
                continue
    
    # create dictionaries of all hidden folders from the file size dict with their total sizes including subfolders
    # key = folder name, value = folder size
    hidden_folders_dict = {}
    for file, size in file_size_dict.items():
        if file.startswith('.'):
            hidden_folders_dict[file] = size
    


if __name__ == "__main__":
    print("Experimental hidden/large directory logger. Test code.")
    main()
