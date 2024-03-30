import dataclasses
import argparse
import os
import subprocess
from collections import defaultdict
import paramiko
from .bytes import byte_size
from .remote import execute_command

# SSH connection parameters
HOSTNAME = '192.168.0.240'
USERNAME = 'pi'
PASSWORD = 'your_password_here'  # It's better to use SSH keys if possiblepi
FOLDER = '/mnt/expansion/Media/Movies'
        
@dataclasses.dataclass
class FileObject:
    path: str
    size: int = 0
    folder: str = ""

    def __post_init__(self):
        parts = self.path.split('/')
        self.name = parts[-1]
        self.folder = '/'.join(parts[:-1])

def parse_args():
    parser = argparse.ArgumentParser(description="List large files and folders with multiple large files over SSH.")
    parser.add_argument('search', nargs='*', help='Text to search for.')
    parser.add_argument('-a', '--all', action='store_true', help='Show all relevant paths') 
    parser.add_argument('-s', '--small', action='store_true', help='Show small files') 
    parser.add_argument('-l', '--large', action='store_true', help='Show large files') 
    parser.add_argument('--folder', type=str, required=False, default=FOLDER, help='Folder to check')
    parser.add_argument('--hostname', type=str, required=False, default=HOSTNAME, help='SSH server hostname')
    parser.add_argument('--username', type=str, required=False, default=USERNAME, help='SSH username')
    parser.add_argument('--password', type=str, required=False, default=PASSWORD, help='SSH password')
    parser.add_argument('--min_size', type=int, default=500_000_000, help='Minimum file size in bytes')
    parser.add_argument('--large_file_size', type=int, default=50000000, help='Size defining a very large file')
    return parser.parse_args()

def get_file_objects(folder, hostname, username, password, command):
    file_objects = []
    output = execute_command(command, folder, hostname, username, password)
    
    for line in output.split('\n'):
        if line:  # Check if line is not empty
            size, path = line.split('\t', 1)
            file_objects.append(FileObject(path=path, size=int(size)))
    return file_objects

def analyze_files(file_objects, min_size, large_file_size):
    large_files = [file for file in file_objects if file.size >= min_size]
    folder_counts = defaultdict(int)
    for file in large_files:
        if file.size >= large_file_size:
            folder_counts[file.folder] += 1
    return large_files, {folder: count for folder, count in folder_counts.items() if count > 1}

def main():
    print("Rog's large file finder...")
    args = parse_args()
    command = f'find {args.folder} -type f -exec du -b ' + '{} +'
    file_objects = get_file_objects(args.folder, args.hostname, args.username, args.password, command)
    large_files, folders_with_multiple_large = analyze_files(file_objects, args.min_size, args.large_file_size)

    print(f"Found {len(large_files):,} files larger than {byte_size(args.min_size)}")
    if args.large:
        for file in large_files:
            print(f"{file.path} ({byte_size(file.size)})")
        print()
        
    search_terms = ' '.join(args.search).strip('"').lower() if args.search else None
    if search_terms:
        print(f"Searching for '{search_terms}' in {len(file_objects):,} files...")
    
    print(f"Found {len(folders_with_multiple_large):,} folders with multiple very large files.")
    if args.all or args.search:
        for folder, count in folders_with_multiple_large.items():
            if search_terms and search_terms not in folder.lower():
                continue
            print(f"{folder}: {count} files")
            # print all paths in the folder
            for file in file_objects:
                if file.folder == folder:
                    if args.small or file.size >= args.large_file_size:
                        print(f"{file.path} ({byte_size(file.size)})")
                    
    if not args.all:
        print("Use --all to show all relevant paths.")


if __name__ == "__main__":
    main()
