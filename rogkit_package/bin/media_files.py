# Roger's Media File Tool
import paramiko
import json
import os
import argparse
import glob
from time import perf_counter
from collections import defaultdict
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Optional
from colorama import Fore, Style

from .media_scan import get_media_info


script_dir = os.path.dirname(os.path.abspath(__file__))
CACHE_FILE = os.path.join(script_dir, "media_files_cache.json")

def size_as_string(size):
    """
    Convert a file size in bytes to a human-readable string.
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1000:
            return f"{size:.2f} {unit}"
        size /= 1000
    return f"{size:.2f} PB"


@dataclass
class MediaFile:
    title: str
    disk: str
    location: str
    filepath: str
    filename: str
    filetype: str
    filesize: int = 0
    
    def __str__(self):
        """Return a formatted string with size and file path"""
        return f"{self.size_str():<18} {self.filepath}"
    
    def size_str(self):
        """Return GB, MB, KB, or bytes with color coding"""
        if self.filesize >= 1_000_000_000:
            return f"{Fore.RED}{self.filesize / 1_000_000_000:.2f} GB{Style.RESET_ALL}"
        elif self.filesize >= 1_000_000:
            return f"{Fore.YELLOW}{self.filesize / 1_000_000:.2f} MB{Style.RESET_ALL}"
        elif self.filesize >= 1_000:
            return f"{Fore.CYAN}{self.filesize / 1_000:.2f} KB{Style.RESET_ALL}"
        return f"{Fore.GREEN}{self.filesize} bytes{Style.RESET_ALL}"

@dataclass
class MediaFolder:
    disk: str
    location: str
    title: str
    folderpath: str
    foldername: str
    files: List[MediaFile] = field(default_factory=list)
    
    def total_size(self) -> int:
        """Calculate the total size of all files in the folder."""
        return sum(file.filesize for file in self.files)

    def __str__(self):
        """Display folder details, including total size and file count."""
        size_str = size_as_string(self.total_size())
        return f"Folder: {self.foldername} ({size_str}, {len(self.files)} files)"


def parse_media_file_line(file_line: str) -> Optional[MediaFile]:
    """
    Parse a file line (size and file path) into a MediaFile dataclass.

    :param file_line: A line containing size and file path (e.g., "123456 /path/to/file").
    :return: MediaFile object
    """
    # Split the line into size and path
    try:
        size_str, file_path = file_line.split(maxsplit=1)
        filesize = int(size_str)
        parts = file_path.split('/')
        disk = parts[2] if len(parts) > 2 else "unknown"
        location = parts[4] if len(parts) > 3 else "unknown"
        if 'tv' in location.lower():  # Normalize TV location to 'TV Shows'
            location = 'TV Shows'
        title = parts[5] if len(parts) > 5 else "unknown"
        filename = os.path.basename(file_path)
        filetype = os.path.splitext(filename)[1][1:]  
        return MediaFile(title=title, disk=disk, location=location, filepath=file_path, filename=filename, filetype=filetype, filesize=filesize)
    except ValueError as e:
        print(f"Error parsing line: {file_line}. Error: {e}")
        return None

def get_remote_media_files(path: str, server_ip: str, username: str) -> List[MediaFile]:
    """
    Retrieve a list of media files from the specified path. If the path is available locally,
    retrieve the file list locally; otherwise, connect to the remote server.

    :param server_ip: IP address or hostname of the server
    :param username: Username for SSH connection
    :param path: Path to search for media files (default is /mnt/media*/Media)
    :return: List of MediaFile objects
    """
    def get_local_media_files(local_paths: List[str]) -> List[MediaFile]:
        """Retrieve media files from the local file system."""
        media_files = []
        for local_path in local_paths:
            for root, dirs, files in os.walk(local_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    try:
                        size = os.path.getsize(file_path)
                        media_file = parse_media_file_line(f"{size} {file_path}")
                        if media_file:
                            media_files.append(media_file)
                    except Exception as e:
                        print(f"Error processing local file: {file_path}, Error: {e}")
        return media_files

    # Expand wildcards in the path using glob
    matched_paths = glob.glob(path)
    if matched_paths:
        print(f"Local paths detected: {matched_paths}")
        return get_local_media_files(matched_paths)

    # If the path is not available locally, fetch files remotely
    try:
        # Create an SSH client
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        # Connect to the server using the default SSH keys
        ssh.connect(server_ip, username=username)

        # Define the command to find all files in the specified path with sizes
        find_command = f"find {path} -type f -exec du -b {{}} +"
        stdin, stdout, stderr = ssh.exec_command(find_command)
        file_lines = stdout.read().decode('utf-8').splitlines()

        # Handle errors if any
        error = stderr.read().decode('utf-8')
        if error:
            print(f"Error occurred while fetching file list: {error}")
            return []

        # Parse file paths and sizes into MediaFile objects
        media_files = [parse_media_file_line(line) for line in file_lines if line.strip()]
        return [file for file in media_files if file is not None]

    except paramiko.SSHException as e:
        print(f"SSH error: {e}")
        return []
    except Exception as e:
        print(f"Unexpected error: {e}")
        return []
    finally:
        ssh.close()


def save_file_list_to_cache(file_list: List[MediaFile]):
    """
    Save the file list to a JSON cache file.

    :param file_list: List of MediaFile objects to save
    """
    with open(CACHE_FILE, 'w') as cache_file:
        json.dump([file.__dict__ for file in file_list], cache_file)
    print(f"File list saved to cache: {CACHE_FILE}")


def load_file_list_from_cache() -> Optional[List[MediaFile]]:
    """
    Load the file list from a JSON cache file.

    :return: List of MediaFile objects, or None if cache does not exist
    """
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'r') as cache_file:
            file_data = json.load(cache_file)
            return [MediaFile(**data) for data in file_data]
    return None


def get_cache_last_modified() -> Optional[datetime]:
    """
    Get the last modified date of the cache file.

    :return: Datetime object or None if cache does not exist
    """
    if os.path.exists(CACHE_FILE):
        timestamp = os.path.getmtime(CACHE_FILE)
        return datetime.fromtimestamp(timestamp)
    return None


def filter_media_files(media_files: List[MediaFile], search: Optional[str]) -> List[MediaFile]:
    """
    Filter media files based on a case-insensitive search string.

    :param media_files: List of MediaFile objects to search
    :param search: Search string or None
    :return: Filtered list of MediaFile objects
    """
    if not search:
        return media_files
    search_lower = search.lower()
    return [
        file for file in media_files
        if search_lower in file.filename.lower() or search_lower in file.filepath.lower()
    ]
    
def find_duplicates(media_files: List[MediaFile]) -> dict:
    """
    Find duplicate media files based on title and group them by disks.

    :param media_files: List of MediaFile objects
    :return: Dictionary where keys are duplicate titles and values are lists of disks
    """
    titles = defaultdict(set)
    for file in media_files:
        titles[file.title].add(file.disk)
    
    # Filter titles that appear on more than one disk
    duplicates = {title: disks for title, disks in titles.items() if len(disks) > 1}
    return duplicates

def group_files_into_folders(media_files: List[MediaFile]) -> List[MediaFolder]:
    """
    Group MediaFile objects into MediaFolder objects, capturing folders at the "Title" level
    and including all subfolders under those.

    :param media_files: List of MediaFile objects
    :return: List of MediaFolder objects
    """
    folders = defaultdict(list)

    # Debugging counters
    invalid_paths = 0
    skipped_generic_titles = 0
    processed_files = 0

    for file in media_files:
        # Split the path into components: /mnt/[disk]/Media/[Location]/[Title]
        parts = file.filepath.split('/')
        if len(parts) < 5:
            invalid_paths += 1
            continue

        disk = parts[2]
        location = parts[4]
        title = parts[5]

        # Skip generic folder names like "Movies" or "TV Shows"
        if title.lower() in ["movies", "tv shows", "music", "audiobook", "tv programmes"]:
            skipped_generic_titles += 1
            continue

        folder_key = (disk, location, title)  # Unique identifier for the folder
        folders[folder_key].append(file)
        processed_files += 1

    # Debugging output
    if invalid_paths:
        print(f"Invalid paths skipped: {invalid_paths}")
    if skipped_generic_titles:
        print(f"Generic titles skipped: {skipped_generic_titles}")

    # Create MediaFolder objects
    media_folders = []
    for (disk, location, title), files in folders.items():
        # Construct folderpath from the title level
        folderpath = f"/mnt/{disk}/Media/{location}/{title}"
        media_folders.append(MediaFolder(
            disk=disk,
            location=location,
            title=title,
            folderpath=folderpath,
            foldername=title,
            files=files
        ))

    return media_folders

def is_extra_file(name: str) -> bool:
    """
    Determine if a file is an extra file based on its name.

    :param name: The file name to check.
    :return: True if the file name contains any of the keywords, False otherwise.
    """
    for keyword in ['sample', 'trailer', 'featurette', 'extra', 'other', 'interview', 'behindthescenes', 'deleted']:
        if keyword in name.lower():
            return True
    return False  # Explicitly return False if no keywords match

def show_folders(media_folders: List[MediaFolder], min_folder_size: int = 500_000_000, not_other: bool = False):
    """
    Display folders containing large files, optionally filtering out extras.

    :param media_folders: List of MediaFolder objects to inspect.
    :param min_folder_size: Minimum file size to consider (default: 500MB).
    :param not_other: If True, exclude files flagged as extras.
    """
    big_folders = []
    
    for folder in media_folders:
        # Exclude TV folders
        if 'tv' in folder.location.lower():
            continue
        
        # Skip folders with a total size less than the threshold (e.g., 1GB here)
        if folder.total_size() < min_folder_size * 2:
            continue
        
        # Filter files in the folder that are larger than the threshold
        large_files = [file for file in folder.files if file.filesize > min_folder_size]
        
        # Apply the "not_other" filter if specified
        if not_other:
            filtered_files = [file for file in large_files if not is_extra_file(file.filepath)]
            large_files = filtered_files  # Update large_files after filtering extras
        
        # Only include folders with more than one qualifying file
        if len(large_files) > 1:
            big_folders.append((folder, large_files))  # Pass folder and filtered large files together

    # Generate descriptive output
    total_str = size_as_string(min_folder_size * 2)
    size_str = size_as_string(min_folder_size)
    description = f"{len(big_folders):,} of {len(media_folders):,} folders have a total size > {total_str} and more than one file > {size_str}."
    print(description)
    
    # Print detailed information for matching folders
    for folder, large_files in big_folders:
        print(folder)
        for file in large_files:
            print(f"  {file}")
        print()
    
    if len(big_folders) == 0:
        print("No folders found matching the criteria.")
    elif len(big_folders) > 10:
        print(description)
        
def show_extras(media_files: List[MediaFile]):
    
        folders = set()
        for file in media_files:
            parts = file.filepath.split('/')
            if len(parts) > 7:
                folder = '/'.join(parts[:-1])
                folders.add(folder)
    
        print("Extra folders found:")

        # Define the categories you're looking for
        collate = ['Subs', 'Extras', 'Behind the Scenes', 'Deleted Scenes', 'Featurettes', 'Interviews', 'Trailers']
        
        # Dictionary to keep count of the collated folders
        collate_counts = {}

        # Loop through the EXTRAS_FOLDERS and categorize them
        for folder in folders:
            # Extract the last part of the folder path (the actual folder name)
            last_dir = folder.split('/')[-1]

            # Check if this folder name is in our collate categories
            if last_dir in collate:
                collate_counts[last_dir] = collate_counts.get(last_dir, 0) + 1

        # Display the results
        print(f"Total extra folders: {len(folders)}")

        # Print counts for collated folders
        for folder, count in collate_counts.items():
            print(f"{folder}: {count}")
        print()

        # Print all folders that don't belong to the collate categories
        for folder in folders:
            last_dir = folder.split('/')[-1]
            if last_dir not in collate:
                print(folder)

def main():
    # Set up argument parser
    parser = argparse.ArgumentParser(description="Roger's Media File Tool")
    parser.add_argument('search', nargs='?', default=None, help="Case-insensitive search string for media files")
    parser.add_argument('-a', "--all", action="store_true", help="List all media files")
    parser.add_argument('-e', "--extras", action="store_true", help="Check extra folders")
    parser.add_argument('-i', "--info", action="store_true", help="Show media file details (for local files)")
    parser.add_argument('-f', "--folders", action="store_true", help="List media folders with more than one large files")
    parser.add_argument('-r', "--refresh", action="store_true", help="Refresh the file list from the server")
    parser.add_argument('-o', "--other", action="store_true", help="Show folders with more than one  large files not classed as an 'extra'")
    parser.add_argument('-p', "--path", default="/mnt/media*/Media", help="Path to search for media files")
    parser.add_argument('-s', "--server", default="pi5", help="Server hostname or IP address")
    parser.add_argument('-u', "--username", default="rog", help="Username for SSH connection")
    args = parser.parse_args()

    print("Rog's Media File Tool")

    # Check cache and fetch last modified time
    cache_last_modified = get_cache_last_modified()
    if not args.refresh and cache_last_modified:
        print(f"Cache found. Last saved on: {cache_last_modified.strftime('%Y-%m-%d %H:%M:%S')}")
        media_files = load_file_list_from_cache()
    else:
        # Fetch from the server
        start_time = perf_counter()
        print(f"Connecting to {args.server} and fetching media file list from {args.path}...")
        media_files = get_remote_media_files(args.path, args.server, args.username)
        elapsed_time = perf_counter() - start_time

        if not media_files:
            print("No media files found or error occurred.")
            return

        print(f"Found {len(media_files):,} media files in {elapsed_time:.2f} seconds.")
        save_file_list_to_cache(media_files)
    
    # get a set with the unique disks
    disks = {file.disk for file in media_files}
    
    # Create MediaFolder objects
    media_folders = group_files_into_folders(media_files)
        
    # Apply search filter if provided
    if args.search:
        filtered_files = filter_media_files(media_files, args.search)
        print(f"Filtered media files matching '{args.search or 'all'}': {len(filtered_files):,} of {len(media_files):,}")
        # Display results
        
        if filtered_files and args.info:
            if not os.path.exists(filtered_files[0].filepath):
                print('Media info not available for remote files.')
                args.info = False
        
        for file in filtered_files:
            print(file)
            if args.info:
                if os.path.exists(file.filepath):
                    print(get_media_info(file.filepath))
        total_size = sum(file.filesize for file in filtered_files)
        print(f"Total size: {size_as_string(total_size)}")
        return
    elif args.all:
        # Display all files
        for file in media_files:
            print(file)
    print(f"Total media files: {len(media_files):,} on {len(disks)} disks ({', '.join(disks)})")
    total_size = sum(file.filesize for file in media_files)
    print(f"Total size: {size_as_string(total_size)}")

    # Find duplicates (titles that appear on more than one disk)
    duplicates = find_duplicates(media_files)

    # Display results
    if not duplicates:
        print("No duplicate titles found.")
    else:
        print(f"Duplicate titles found: {len(duplicates)}")
        for title, disks in duplicates.items():
            print(f"{title}: {', '.join(disks)}")
            
    if args.folders or args.other:
        # Get MediaFolders where the total size > 1GB and more than one file is > 500MB
        if args.other:
            print("Showing folders with more than one large file not classed as an 'extra':")
        else:
            print("Showing folders with more than one large file:")
        show_folders(media_folders, not_other=args.other)
        
    if args.extras:
        show_extras(media_files)

if __name__ == "__main__":
    main()