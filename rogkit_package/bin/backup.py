import os
import sys
import argparse
import tempfile
import yaml
from datetime import datetime
from time import perf_counter
from pathlib import Path

from .bytes import byte_size
from .seconds import convert_seconds

USER_HOME = os.path.expanduser('~')

"""
Sample ~/.backup.yaml configuration file:

# Folders to back up
source_folders:
  - /home/user/documents
  - /home/user/photos
  - /home/user/projects

# File patterns to exclude from backup
file_excludes:
  - node_modules
  - build
  - dist
  - package-lock.json
  - '*.pyc'
  - '.DS_Store'
  - '.git'
  - '*.log'

# Folder patterns to exclude from backup
folder_excludes:
  - /home/user/temp
  - /home/user/cache
  - /home/user/projects/old_versions
  - /home/user/.config

# Locations to store backups
archive_locations:
  - /mnt/external_drive/backups
  - /mnt/network_drive/backups
  - /home/user/cloud_backups
"""

# Default configurations (absolute or in user home)
DEFAULT_SOURCE_FOLDERS = ['apv', 'bin', 'dev', 'opt']

DEFAULT_FILE_EXCLUDES = [
    'node_modules', 'build', 'dist', 'package-lock.json', 'tar.gz', '.pyc', '.DS_Store', '.git',
    '.idea', '.vscode', '.ipynb_checkpoints', '__pycache__', '.log', '.sqlite',
    'package.json', '.virtual', '.docker', 'yarn.lock', 'yarn-error.log', '.mp3', '.exe',
]
DEFAULT_FOLDER_EXCLUDES = [
    '/eggs', 'env/', 'parts/', 'v27', 'internal_packages', 'data/', '/venv', '.git',
    '.idea', 'logs', 'data_dir', 'mvs', 'open-webui'
]
DEFAULT_ARCHIVE_LOCATIONS = [
    '/mnt/media1/Archive/Backups',
    '/mnt/media2/Archive/Backups',
    '/Users/rdubar/Dropbox/Archive/MacBookPro/',
    '/Users/rdubar/OneDrive - Arden Grange/Archive/Backups'
]

MEGABYTE = 1024 * 1024


def load_config():
    """Load and merge configuration from ~/.backup.yaml."""
    global DEFAULT_SOURCE_FOLDERS, DEFAULT_FILE_EXCLUDES, DEFAULT_FOLDER_EXCLUDES, DEFAULT_ARCHIVE_LOCATIONS

    config_path = os.path.join(USER_HOME, '.backup.yaml')
    if os.path.exists(config_path):
        print(f'Loading configuration from {config_path}')
        with open(config_path, 'r') as config_file:
            user_config = yaml.safe_load(config_file)

        # Override defaults if keys are provided
        DEFAULT_SOURCE_FOLDERS = user_config.get('source_folders', DEFAULT_SOURCE_FOLDERS)
        DEFAULT_FILE_EXCLUDES = user_config.get('file_excludes', DEFAULT_FILE_EXCLUDES)
        DEFAULT_FOLDER_EXCLUDES = user_config.get('folder_excludes', DEFAULT_FOLDER_EXCLUDES)
        DEFAULT_ARCHIVE_LOCATIONS = user_config.get('archive_locations', DEFAULT_ARCHIVE_LOCATIONS)


def is_path_valid(path):
    return os.path.exists(path)


def create_backup(verbose=False, archive_locations=DEFAULT_ARCHIVE_LOCATIONS):
    """Create a new backup."""
    start_time = perf_counter()

    valid_archive_locations = [loc for loc in archive_locations if is_path_valid(loc)]

    if not valid_archive_locations:
        print('No valid archive location found.')
        sys.exit(1)

    primary_archive_path = valid_archive_locations[0]
    extra_archive_paths = valid_archive_locations[1:] if len(valid_archive_locations) > 1 else []

    current_date = datetime.today().strftime('%Y-%m-%d-%H-%M')
    backup_filename = f'backup-{current_date}.tar.gz'
    os.makedirs(primary_archive_path, exist_ok=True)

    backup_file_path = os.path.join(primary_archive_path, backup_filename)

    print(f'Backing up the following folders: {DEFAULT_SOURCE_FOLDERS}')
    print(f'Backup path: {backup_file_path}')
    
    source_folders = []
    user_home = Path.home() 
    for folder in DEFAULT_SOURCE_FOLDERS:
        if is_path_valid(folder):
            source_folders.append(folder)
        else:
            user_folder = os.path.join(user_home, folder)
            if is_path_valid(user_folder):
                source_folders.append(user_folder)
    if not source_folders:
        print(f'No valid source folders found in {DEFAULT_SOURCE_FOLDERS}.')
        sys.exit(1)

    file_count, total_file_size, skipped_count = 0, 0, 0

    # Collect files to backup
    with tempfile.NamedTemporaryFile(mode='w+', delete=False) as file_list:
        for folder in source_folders:
            for root, _, files in os.walk(folder):
                for file in files:
                    if not any(exclude in file for exclude in DEFAULT_FILE_EXCLUDES) and not any(exclude in root for exclude in DEFAULT_FOLDER_EXCLUDES):
                        file_path = os.path.join(root, file)
                        file_list.write(file_path + '\n')
                        file_count += 1
                        try:
                            total_file_size += os.path.getsize(file_path)
                        except (FileNotFoundError, PermissionError):
                            skipped_count += 1
                            continue
                    else:
                        skipped_count += 1
                        
    if verbose: 
        [print(f'Added: {line.strip()}') for line in open(file_list.name)]

    elapsed_time = convert_seconds(perf_counter() - start_time)
    print(f'Found {file_count:,} files to backup ({byte_size(total_file_size)}). Skipped {skipped_count:,}. Elapsed time: {elapsed_time}.')

    # Create backup archive
    temp_backup_path = backup_file_path + '.tmp'
    try:
        os.system(f'tar -czf {temp_backup_path} -T {file_list.name}')
    except Exception as e:
        print(f'Error during backup: {e}')
        os.remove(temp_backup_path)
    finally:
        os.remove(file_list.name)

    if not os.path.exists(temp_backup_path):
        print('Backup failed.')
        sys.exit(1)

    os.rename(temp_backup_path, backup_file_path)

    # Copy backup to extra locations
    for extra_path in extra_archive_paths:
        try:
            os.makedirs(extra_path, exist_ok=True)
            os.system(f'cp {backup_file_path} "{os.path.join(extra_path, backup_filename)}"')
            print(f'Backup copied to {extra_path}')
        except Exception as e:
            print(f'Error copying backup to {extra_path}: {e}')

    total_elapsed = convert_seconds(perf_counter() - start_time)
    archive_size = os.path.getsize(backup_file_path)
    print(f'Backup created with {file_count:,} files ({byte_size(archive_size)}) in {total_elapsed}.')
    print(f'Backup path: {backup_file_path}')


def list_backups():
    """List existing backups from all archive locations."""
    print("Listing backups from all configured archive locations...\n")

    folder_count = 0
    for location in DEFAULT_ARCHIVE_LOCATIONS:
        if os.path.exists(location):
            folder_count += 1
            print(f'\nBackups in: {location}')
            try:
                # List all backups in the location
                backups = [f for f in os.listdir(location) if f.startswith('backup-') and f.endswith('.tar.gz')]
                if backups:
                    for backup in sorted(backups):
                        # Build the full path
                        backup_path = os.path.join(location, backup)
                        backup_size = os.path.getsize(backup_path)
                        # Print full path along with details
                        print(f' {byte_size(backup_size):<10}    {backup_path:60} ')
                else:
                    print("No backups found in this location.")
            except Exception as e:
                print(f"Error listing backups in {location}: {e}")
    
    if folder_count == 0:
        print("\nNo valid archive locations found.")
        
            
def main():
    load_config()  # Load YAML configuration

    parser = argparse.ArgumentParser(description='Backup and list backups')
    parser.add_argument('-b', '--backup', action='store_true', help='Create a new backup')
    parser.add_argument('-l', '--list', action='store_true', help='List existing backups')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    args = parser.parse_args()
    
    if args.list:
        list_backups()
        
    if args.backup:
        create_backup(verbose=args.verbose)
    
    if not any(vars(args).values()):
        parser.print_help()


if __name__ == '__main__':
    main()