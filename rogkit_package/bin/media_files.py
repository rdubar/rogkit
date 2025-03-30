# Roger's Media File Tool
import paramiko
import json
import os
import argparse
import glob
import re
import shutil
import sys
from typing import List
from time import perf_counter
from collections import defaultdict
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Optional
from colorama import Fore, Style

from .media_scan import get_media_info
from .seconds import time_ago_in_words
from .bytes import byte_size


script_dir = os.path.dirname(os.path.abspath(__file__))
CACHE_FILE = os.path.join(script_dir, "media_files_cache.json")
ARCHIVE_FILE = os.path.join(script_dir, "media_files_cache_archive.json")

MIN_FILE_SIZE_MB = 200  # Minimum file size to consider as a valid replacement

MEDIA_TYPES = { 'mp4', 'mkv', 'avi', 'mov', 'wmv', 'flv', 'webm', 'mpg', 'mpeg', 'm4v', '3gp', 'vob', 'ts', 'divx', 'xvid' }


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
    
    def match_title(self, title):
        """Return the standardized title for matching."""
        return standardize_title(self.title)
    
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
    
    def match_title(self, title):
        """Return the standardized title for matching."""
        return standardize_title(self.title)
    

def standardize_title(title: str) -> str:
    """
    Standardize the title by:
    - Removing special characters (excluding spaces and alphanumerics)
    - Converting to lowercase
    - Trimming spaces
    - Removing any text after a closing parenthesis ")"
    """
    # Remove anything after a ")"
    title = re.split(r'\)', title, maxsplit=1)[0]
    # Remove special characters except spaces and alphanumerics
    title = re.sub(r'[^a-zA-Z0-9\s]', '', title)
    # Convert to lowercase and strip leading/trailing whitespace
    title = title.lower().strip()
    return title

def parse_media_file_line(file_line: str) -> Optional[MediaFile]:
    """
    Parse a file line (size and file path) into a MediaFile dataclass.

    :param file_line: A line containing size and file path (e.g., "123456 /path/to/file").
    :return: MediaFile object or None if the line is invalid.
    """
    try:
        # Strip leading/trailing whitespace and split into size and path
        file_line = file_line.strip()
        size_str, file_path = file_line.split(maxsplit=1)  # Split only at the first whitespace
        filesize = int(size_str)  # Convert size to integer
        
        # Split the file path into giot statusparts
        parts = file_path.split('/')
        
        # Validate that the parts list has enough elements
        if len(parts) < 6:
            # print(f"Skipping line due to insufficient parts: {parts}")
            return None
        
        # Extract disk, location, and title with safe indexing
        disk = parts[2] if len(parts) > 2 else "unknown"
        location = parts[4] if len(parts) > 4 else "unknown"
        
        # Normalize 'TV Shows' location for consistency
        if 'tv' in location.lower():
            location = 'TV Shows'
        
        title = standardize_title(parts[5]) if len(parts) > 5 else "unknown"
        filename = os.path.basename(file_path)  # Extract the file name
        filetype = os.path.splitext(filename)[1][1:]  # Extract the file extension without the dot
        
        # Create and return the MediaFile object
        return MediaFile(
            title=title,
            disk=disk,
            location=location,
            filepath=file_path,
            filename=filename,
            filetype=filetype,
            filesize=filesize
        )
    
    except ValueError as e:
        # Handle issues with splitting or integer conversion
        print(f"Error parsing line: {file_line}. Error: {e}")
        return None
    except IndexError as e:
        # Handle issues with unexpected path structure
        print(f"Index error with line: {file_line}. Error: {e}")
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
        if ' ' in path:
            path = f'"{path}"'
        find_command = f'find {path} -type f -exec du -b {{}} +'
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
    Find duplicate media files based on standardized title and group them by disk.
    
    :param media_files: List of MediaFile objects
    :return: Dictionary where keys are duplicate titles, and values are dictionaries
             with disk names as keys and total sizes as values.
    """
    title_disk_sizes = defaultdict(lambda: defaultdict(int))

    for file in media_files:
        standardized_title = standardize_title(file.title)
        title_disk_sizes[standardized_title][file.disk] += file.filesize

    # Filter to include only titles that appear on more than one disk
    duplicates = {
        title: sizes for title, sizes in title_disk_sizes.items() if len(sizes) > 1
    }

    return duplicates

def display_duplicates(duplicates: dict):
    """
    Display duplicate media titles with their total file sizes on each disk.

    :param duplicates: Dictionary of duplicates returned by `find_duplicates()`.
    """
    if not duplicates:
        print("No duplicate titles found.")
        return

    print("\n==== Duplicate Media Titles ====")
    for title, disk_sizes in duplicates.items():
        print(f"\n{Fore.CYAN}{title}{Style.RESET_ALL}:")
        for disk, size in disk_sizes.items():
            size_str = size_as_string(size)  # Convert size to human-readable format
            print(f"  - {disk}: {Fore.YELLOW}{size_str}{Style.RESET_ALL}")
        

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
    for keyword in ['sample', 'trailer', 'featurette', 'extra', 'other', 'interview', 'behindthescenes', 'deleted', '.pt']:
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
                
def process_exact_matches(exact_matches: List[str], media_files: List[MediaFile]) -> List[str]:
    """
    Get a list of the main folder paths on media3 for exact matches.

    :param exact_matches: List of titles with exact matches across disks.
    :param media_files: List of MediaFile objects containing file information.
    :return: List of main folder paths on media3 for exact matches.
    """
    main_folders = set()

    # Iterate through media files and find exact matches on media3
    for file in media_files:
        if file.title in exact_matches and file.disk == "media3":
            # Extract the main folder path (up to title level)
            parts = file.filepath.split('/')
            if len(parts) > 6:  # Ensure valid structure
                main_folder = '/'.join(parts[:6])  # Keep up to "/disk/Media/Location/Title"
                main_folders.add(main_folder)  # Add to the set

    # Convert the set to a sorted list for consistent output
    sorted_folders = sorted(main_folders)

    # Print the main folders for verification
    print(f"Main folders on media3 ({len(sorted_folders)}):")
    for folder in sorted_folders:
        print(f'trash-put "{folder}"')
    
    return sorted_folders


def find_small_media_folders(media_folders: List[MediaFolder], min_folder_size: int = 500_000_000):
    """
    Find media folders with a total size less than the threshold.

    :param media_folders: List of MediaFolder objects to inspect.
    :param min_folder_size: Minimum total size to consider (default: 500MB).
    """
    small_folders = []
    
    for folder in media_folders:
        # Skip Music folders
        if 'music' in folder.location.lower() or 'audiobook' in folder.location.lower():
            continue
        # Skip folders with a total size greater than the threshold
        if folder.total_size() > min_folder_size:
            continue
        
        small_folders.append(folder)

    # Generate descriptive output
    total_str = size_as_string(min_folder_size)
    description = f"{len(small_folders):,} of {len(media_folders):,} folders have a total size < {total_str}."
    print(description)
    
    # Print detailed information for matching folders
    for folder in small_folders:
        print(folder)
        # print the files in the folder
        for file in folder.files:
            print(f"  {file}")
    
    if len(small_folders) == 0:
        print("No folders found matching the criteria.")
    elif len(small_folders) > 10:
        print(description)


def find_small_media_files(media_files: List[MediaFile], max_size: int = 300_000_000, report=True) -> List[MediaFile]:
    """
    Find media files smaller than the specified size.

    :param media_files: List of MediaFile objects.
    :param max_size: Maximum file size in bytes (default: 300MB).
    :return: List of small MediaFile objects.
    """
    types = MEDIA_TYPES
    
    small_files = [file for file in media_files if file.filesize < max_size and file.filetype in types]

    if report:
        # Generate descriptive output
        size_str = size_as_string(max_size)
        description = f"{len(small_files):,} of {len(media_files):,} files are smaller than {size_str}."
        print(description)

        # Display the small files
        for file in small_files:
            print(file)

        if not small_files:
            print("No small media files found.")

    return small_files

def find_hidden_files(media_files: List[MediaFile], report=True) -> List[MediaFile]:
    """
    Find hidden files (starting with a dot) in the media files list.

    :param media_files: List of MediaFile objects.
    :return: List of hidden MediaFile objects.
    """
    hidden_files = [file for file in media_files if os.path.basename(file.filepath).startswith('.')]
    if report:
        print(f"{len(hidden_files):,} hidden files found.")
        for file in hidden_files:
            print(file)
    return hidden_files

def check_against_archive(media_files: List[MediaFile], archive_file: str = ARCHIVE_FILE, show_all: bool = False):
    """
    Compare the archive cache with the current media files and detect missing media.
    A movie is only considered missing if its main folder doesn't exist with at least 200MB of media on *any* disk.
    """

    if not os.path.exists(archive_file):
        print(f"❌ Archive file not found: {archive_file}")
        return

    try:
        with open(archive_file, 'r') as f:
            archive_data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"❌ Error reading JSON from archive: {e}")
        return

    # Prepare lookup for archive file info
    archive_files = {file['filepath']: (file['filesize'], file['disk']) for file in archive_data}
    media_file_paths = {media_file.filepath for media_file in media_files}

    # Track folder-level total sizes in the current cache
    media_folder_sizes = defaultdict(int)  # {folder_path: total_size}
    for media_file in media_files:
        folder_path = os.path.dirname(media_file.filepath)
        media_folder_sizes[folder_path] += media_file.filesize

    # Identify missing file paths
    missing_files = {
        path: (size, disk)
        for path, (size, disk) in archive_files.items()
        if path not in media_file_paths
    }

    media_extensions = MEDIA_TYPES
    MIN_VALID_SIZE_BYTES = MIN_FILE_SIZE_MB * 1_000_000  # 200MB in bytes

    # Candidate folders that might be missing
    candidate_missing_folders = defaultdict(lambda: defaultdict(int))  # {folder_path: {disk: total_size}}
    for filepath, (filesize, disk) in missing_files.items():
        ext = filepath.lower().split('.')[-1]
        if ext in media_extensions:
            folder_path = os.path.dirname(filepath)
            candidate_missing_folders[folder_path][disk] += filesize

    # Ignore folders that are actually present elsewhere
    filtered_missing = {}
    EXCLUDED_SUBFOLDERS = {'extras', 'featurettes', 'deleted scenes', 'behind the scenes', 'interviews', 'sample', 'trailers', 'picture gallery', 'promo material'}

    for folder_path, disk_info in candidate_missing_folders.items():
        folder_name = os.path.basename(folder_path).lower()

        if folder_name in EXCLUDED_SUBFOLDERS:
            continue  # Skip extras folders entirely

        # Find if this folder (basename match) exists *anywhere* in current media
        folder_basename = os.path.basename(folder_path)
        found_equivalent = any(
            os.path.basename(existing_folder) == folder_basename and
            size >= MIN_VALID_SIZE_BYTES
            for existing_folder, size in media_folder_sizes.items()
        )

        if not found_equivalent:
            filtered_missing[folder_path] = disk_info

    # Report
    if not filtered_missing:
        print("✅ No important media files are missing.")
        return

    total_missing_size = sum(sum(sizes.values()) for sizes in filtered_missing.values())
    print(f"⚠️ {len(filtered_missing):,} missing movies detected, totaling {size_as_string(total_missing_size)}.")

    # Display top N
    displayed_count = 0
    show_count = 20
    for folder, disks in sorted(filtered_missing.items(), key=lambda x: -sum(x[1].values())):
        if not show_all and displayed_count >= show_count:
            break
        title = os.path.basename(folder)
        disk_info = ", ".join(f"{disk}: {size_as_string(size)}" for disk, size in disks.items())
        print(f"{title} ({disk_info})")
        displayed_count += 1

    if displayed_count < len(filtered_missing):
        print(f"...and {len(filtered_missing) - displayed_count:,} more missing movies.")
    else:
        print(f"All {len(filtered_missing):,} missing movies displayed.")

def restore_backup_media(media_files: List[MediaFile], verbose: bool = False):
    """
    Restore media files from a backup disk based on the main media file list.
    """
    from .media_scan import get_media_info  # Optional, for debugging or extra info

    backup_disk_path = "/media/rog/?"
    default_restore_disk = "media1"
    print(f'Checking backup media files in: "{backup_disk_path}"')

    # Wrap path in quotes to handle spaces when running remotely
    backup_media_files = get_remote_media_files(backup_disk_path, "pi5", "rog")
    print(f"Found {len(backup_media_files):,} total files on backup disk.")

    # Create a set of standardized titles from the existing media files    
    main_titles_dict = {standardize_title(media.title): media for media in media_files}

    matched = []
    unmatched = []
    title_list = []
    records_to_check = []
    errors = []

    for record in backup_media_files:
        
        # Try to extract the folder name as the title
        parts = record.filepath.split('/')
        if len(parts) < 6:
            continue

        backup_title = standardize_title(parts[5])  # Folder name as title

        folder = record.filepath.split('/')[4].lower()
        if not folder in ['movies', 'new']: 
            continue

        if backup_title in main_titles_dict:
            record.disk = main_titles_dict[backup_title].disk
            message = f"Matched backup: {backup_title}"
            matched.append(backup_title)
        else:
            record.disk = default_restore_disk
            message = f"Not in main cache: {backup_title}"
            unmatched.append(backup_title)
        
        if backup_title not in title_list:

            title_list.append(backup_title)
            if verbose:
                print(message)
                
        records_to_check.append(record)

    print(f"Matching complete: {len(matched)} matched, {len(unmatched)} unmatched in {len(title_list)} titles.")
    
    # Now see if we are on the local disk for perform a backup restore
    if not os.path.exists(backup_disk_path):
        print(f'Backup disk not found: "{backup_disk_path}"')
        return
    
    # Restore the files from the backup disk
    total = len(records_to_check)
    for count, record in enumerate(records_to_check):
        # print(f"Restoring: {record.filepath} to {record.disk}")
        new_file_path = f'/mnt/{record.disk}/Media/Movies/' + '/'.join(record.filepath.split('/')[5:])

        if not os.path.exists(record.filepath):
            print(f"File not found: {record.filepath}")
            sys.exit(1)

        size_of_backup = os.path.getsize(record.filepath)
        if os.path.exists(new_file_path):
            
            size_of_existing = os.path.getsize(new_file_path)
            if size_of_backup == size_of_existing:
                if verbose: 
                    print(f"Skipping identical file: {new_file_path}")
                continue
            else:
                print(f"Replacing {new_file_path} with {record.filepath}")
        
        # Copy the file from the backup disk to the main media disk
        print(f"[{count}/{total}] Copying {record.filename} to {record.disk}")
        try:
            os.makedirs(os.path.dirname(new_file_path), exist_ok=True)
            shutil.copy(record.filepath, new_file_path)
        except Exception as e:
            print(f"Error copying {record.filename} to {new_file_path}: {e}")
            errors.append([record.filepath, e])
            continue
        size_of_new = os.path.getsize(new_file_path)
        if size_of_new != size_of_backup:
            print(f"Error copying {record.filepath} to {record.disk}")
        elif verbose:
            print(f"Copied {record.filepath} to {new_file_path}")
            
    print(f"Restore complete: {len(records_to_check)} files restored.")
    
    if errors:
        print(f"Errors: {len(errors)}")
        if verbose: 
            for error in errors:
                path, e = error
                print(f"{path}: {e}")


def main():
    # Set up argument parser
    parser = argparse.ArgumentParser(description="Roger's Media File Tool")
    parser.add_argument('search', nargs='*', default=None, help="Case-insensitive search string for media files")
    parser.add_argument('-a', "--all", action="store_true", help="List all media files")
    parser.add_argument('-c', "--check", action="store_true", help="Check against archive")
    parser.add_argument('-e', "--extras", action="store_true", help="Check extra folders")
    parser.add_argument('-i', "--info", action="store_true", help="Show media file details (for local files)")
    parser.add_argument('-f', "--folders", action="store_true", help="List media folders with more than one large file")
    parser.add_argument('-d', "--duplicates", action="store_true", help="Show duplicate media titles across disks (default)")
    parser.add_argument('-r', "--refresh", action="store_true", help="Refresh the file list from the server")
    parser.add_argument('-o', "--other", action="store_true", help="Show folders with more than one large file not classed as an 'extra'")
    parser.add_argument('-p', "--path", default="/mnt/media*/Media", help="Path to search for media files")
    parser.add_argument('--hidden', action="store_true", help="Include hidden files")
    parser.add_argument('-R', "--restore", action="store_true", help="Restore media files from backup disk")
    parser.add_argument('-v', "--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--server", default="pi5", help="Server hostname or IP address")
    parser.add_argument("--username", default="rog", help="Username for SSH connection")
    
    args = parser.parse_args()
    search = ' '.join(args.search) if args.search else None

    print("Rog's Media File Tool")

    # Check cache and fetch last modified time
    cache_last_modified = get_cache_last_modified()
    time_ago_in_seconds = datetime.now().timestamp() - cache_last_modified.timestamp() if cache_last_modified else 0

    if cache_last_modified:
        time_ago_str = time_ago_in_words(time_ago_in_seconds)
        print(f"Cache last modified {time_ago_str} ago.")
    else:
        print("Cache not found or never modified.")
        
    # Auto-refresh if cache older than one hour
    if time_ago_in_seconds > 3600:
        print("Cache is older than one hour, refreshing...")
        args.refresh = True

    # Refresh cache if requested or outdated
    if not args.refresh and cache_last_modified:
        media_files = load_file_list_from_cache()
    else:
        print(f"Fetching media file list from {args.server}:{args.path}...")
        media_files = get_remote_media_files(args.path, args.server, args.username)
        if not media_files:
            print("No media files found or error occurred.")
            return
        print(f"Found {len(media_files):,} media files.")
        save_file_list_to_cache(media_files)

    # Group media files into folders
    media_folders = group_files_into_folders(media_files)

    if search:
        filtered_files = filter_media_files(media_files, search)
        print(f"Filtered media files matching '{search}': {len(filtered_files):,} of {len(media_files):,}")
        for file in filtered_files:
            print(file)
            if args.info:
                print(get_media_info(file.filepath))
        return

    print(f"Total {len(media_files):,} files in {len(media_folders):,} media folders.")

    # Display duplicates if requested
    if True or args.duplicates:
        duplicates = find_duplicates(media_files)
        display_duplicates(duplicates)

    # Show folders with multiple large files
    if args.folders or args.other:
        show_folders(media_folders, not_other=args.other)

    if args.extras:
        show_extras(media_files)

    if args.hidden:
        find_hidden_files(media_files)
    
    if args.check:
        check_against_archive(media_files, show_all=args.all)
        
    if args.restore:
        restore_backup_media(media_files, verbose=args.verbose)

if __name__ == "__main__":
    main()