#!/usr/bin/env python3
"""
RogKit Backup Utility
"""
import os
import re
import argparse
import subprocess
import tempfile
import shutil
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Set
from time import perf_counter
from seconds import convert_seconds
from bytes import byte_size

DEFAULT_CONFIG = {
    "base_dirs": [os.path.expanduser("~")],
    "include_patterns": [".bash_aliases", ".bashrc"],
    "exclude_patterns": ["__pycache__", ".git", "venv/", "Dropbox-Uploader", ".tar.gz", ".pyc", ".rst", "/usr/include", "/usr/lib"],
    "archive_dirs": ["/mnt/expansion/Archive/pi", 
                     "/mnt/archive/Archive/pi", 
                     "/mnt/c/Users/RogerDubar/Dropbox/Archive/wsl2",
                     "/mnt/c/Users/RogerDubar/OneDrive - Arden Grange/Archive/Backups"],
    "include_files": ["/etc/fstab"]
}

@dataclass
class BackupUtility:
    base_dirs: List[str] = field(default_factory=lambda: DEFAULT_CONFIG["base_dirs"])
    include_patterns: List[str] = field(default_factory=lambda: DEFAULT_CONFIG["include_patterns"])
    exclude_patterns: List[str] = field(default_factory=lambda: DEFAULT_CONFIG["exclude_patterns"])
    archive_dirs: List[str] = field(default_factory=lambda: DEFAULT_CONFIG["archive_dirs"])
    include_files: List[str] = field(default_factory=lambda: DEFAULT_CONFIG["include_files"])
    exclude_regex: re.Pattern = field(init=False)
    total_files_found: int = field(default=0, init=False)
    
    init: bool = field(default=False, init=False)
    files_to_include = []
    files_to_exlude = []
    report_text: str = 'Backup report not initialised'

    def __post_init__(self):
        self.exclude_regex = re.compile("|".join(re.escape(p) for p in self.exclude_patterns), re.IGNORECASE)
        self.set_backup_directories()  # sets up primary_archive_dir & secondary_archive_dirs
        self.backup_log = os.path.join(self.primary_archive_dir, 'backup.log')
        self.backup_text = os.path.join(self.primary_archive_dir, 'backup.txt')
    
    def set_backup_directories(self):
        if not self.archive_dirs:
            print('No archive location specified. Using home directory.')
            self.archive_dirs = [str(Path.home())]
        archive_here = []
        archive_lost = []
        for dir in self.archive_dirs:
            if os.path.isdir(dir):
                archive_here.append(dir)
            else:
                archive_lost.append(dir)
        if not archive_here:
            print('Archive location not specified:', self.archive_dirs)
            exit(1)
        self.primary_archive_dir = archive_here[0]
        self.secondary_archive_dirs = archive_here[1:]
        return True

    def create_backup(self, backup_filename):
        if not self.files_to_include:
            self.init_backup()
        print('Creating backup...')

        # Write file paths to a temporary file
        with tempfile.NamedTemporaryFile(mode='w+', delete=False) as temp_file:
            for file_path in self.files_to_include:
                temp_file.write(file_path + '\n')
            temp_file_name = temp_file.name

        # Create the tar command with --hard-dereference option
        command = ["tar", "--hard-dereference", "-czf", backup_filename, "-T", temp_file_name]

        # Execute the command
        try:
            subprocess.run(command, check=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f"Error during backup: {e}")
            return False
        finally:
            # Clean up the temporary file
            os.remove(temp_file_name)

    def should_include(self, file_path, base_dir):
        # Determine if a file should be included
        # Updated logic to use base_dir
        if os.path.basename(file_path) in self.include_files:
            return True
        for pattern in self.include_patterns:
            if pattern in file_path:
                return True
        if file_path.startswith(os.path.join(base_dir, ".")):
            return False
        return not self.exclude_regex.search(file_path)

    def generate_file_list(self, base_dir, visited_links: Set[str] = None):
        # Generate a list of files to be backed up
        if visited_links is None:
            visited_links = set()
        include_list = []
        exclude_list = []
        for root, dirs, files in os.walk(base_dir, followlinks=True):
            for name in files:
                self.total_files_found += 1
                file_path = os.path.join(root, name)
                if self.should_include(file_path, base_dir):
                    include_list.append(file_path)
                else:
                    exclude_list.append(file_path)
            for name in dirs:
                dir_path = os.path.join(root, name)
                if os.path.islink(dir_path) and dir_path not in visited_links:
                    visited_links.add(dir_path)
                    linked_dir = os.readlink(dir_path)
                    include_list.extend(self.generate_file_list(linked_dir, visited_links))
        self.files_to_include = include_list
        self.files_to_exlude = exclude_list
        return include_list
    
    def init_backup(self, verbose=False, force=False):
        if self.init and not force:
            return
        # Get a list of files to be archived
        print('Scanning files...')
        include_dir = []
        exclude_dir = []
        for dir in self.base_dirs:
            if os.path.isdir(dir):
                include_dir.append(dir)
            else:
                exclude_dir.append(dir)
                
        if verbose:
            print('Including: ', include_dir)
            if len(exclude_dir) > 0:
                print('Ignoring:  ', exclude_dir)

        # Start with specified include files
        complete_list = self.include_files.copy()
        self.total_files_found = len(complete_list)

        # Generate file list for each included directory
        for dir in include_dir:
            this_list = self.generate_file_list(dir)
            if verbose:
                print(f'Found {len(this_list):,} files in {dir}')
            complete_list.extend(this_list)  

        if len(include_dir) > 1:
            if verbose:
                print(f'Total {len(complete_list):,} files in {len(include_dir):,} directories')
        
        self.report_text = f'Total: {self.total_files_found:,}  Archive: {len(complete_list):,}  Ignore: {self.total_files_found - len(complete_list):,}'
        print(self.report_text)
        self.init = True

    def perform_backup(self, verbose=False):        
        # Create a temporary file
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_backup_path = temp_file.name

            # Attempt to create the backup
            if not self.create_backup(temp_backup_path):
                print('Backup failed')
                os.remove(temp_backup_path)  # Clean up the temp file
                return False

            # Rename the temporary file to the final backup file
            backup_filename = f'backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.tar.gz'
            backup_path = os.path.join(self.primary_archive_dir, backup_filename)
            shutil.move(temp_backup_path, backup_path)

            # Rest of your function's logic
            size = byte_size(os.path.getsize(backup_path))
            print(f'Backup saved to {backup_path} ({size})')
        
        # Update the backup log 
        with open(self.backup_log, 'a') as f:
            f.write(f'{datetime.now().strftime("%Y%m%d_%H%M%S")},{size} {self.report_text}\n')
            
        if verbose:
            [print(x) for x in self.files_to_include]
        
        # Write the human-readable file list to the archive folder as backup.txt
        with open(self.backup_text, 'w') as f:
            f.write('\n'.join(self.files_to_include))
            
        # Now copy the backup to the other dirs in the list
        for dir in self.secondary_archive_dirs:
            print(f'Copying backup to {dir}')
            subprocess.run(['cp', backup_path, dir + '/' + backup_filename], check=True)
            
        return True

    def report_values(self):
        # do deep listing of all values in this object in a nice format
        for k, v in vars(self).items():
            print(f'{k}: {v}')
    
    def show_report_text(self):
        # print out the backup_text file
        if not os.path.isfile(self.backup_text):
            print(f'No backup text file found: {self.backup_text}')
            return
        filedate = datetime.fromtimestamp(os.path.getmtime(self.backup_text)).strftime("%Y-%m-%d %H:%M:%S")
        print(f'Backup text file: {self.backup_text} ({filedate})')
        with(open(self.backup_text, 'r')) as f:
            print(f.read()) 
    
    def list_archives(self):
        # list the primary backup directory
        print(f'Listing {self.primary_archive_dir}')
        files = sorted(os.listdir(self.primary_archive_dir))
        for file_ in files:
            file_path = os.path.join(self.primary_archive_dir, file_)
            print(f'{file_:40} {byte_size(os.path.getsize(file_path))}')  
            
    def show_log(self):
        # list the backup log
        if not os.path.isfile(self.backup_log):
            print(f'No backup log file found: {self.backup_log}')
            return
        filedate = datetime.fromtimestamp(os.path.getmtime(self.backup_log)).strftime("%Y-%m-%d %H:%M:%S")
        print(f'Backup log file: {self.backup_log} ({filedate})')
        with(open(self.backup_log, 'r')) as f:
            print(f.read())
    
    def extract(self):
        print(f'Extracting latest archive from {self.primary_archive_dir}')

        # List all files and get the latest archive
        try:
            files = sorted(Path(self.primary_archive_dir).glob('*.tar.gz'))
        except Exception as e:
            print(f"Error listing files in {self.primary_archive_dir}: {e}")
            return

        if not files:
            print("No backup files found.")
            return

        latest = files[-1]
        latest_name = latest.stem.replace('.tar','')  # Get the name without extension

        # Create a directory named after the archive
        extract_dir = os.path.join(self.primary_archive_dir, latest_name)
        try:
            os.makedirs(extract_dir, exist_ok=True)
        except Exception as e:
            print(f"Error creating directory {extract_dir}: {e}")
            return

        # Extract the archive into the created directory
        try:
            print(f'Extracting {latest} to {extract_dir}')
            subprocess.run(['tar', '-xzf', str(latest), '-C', extract_dir], check=True)    
            print('Done')
        except subprocess.CalledProcessError as e:
            print(f"Error extracting {latest}: {e}")
    
    def last_backup(self, verbose=False):
        # Attempt to get the latest backup file
        latest_backup_file = self.get_latest_backup_file()
        if not latest_backup_file:
            return 'No backup files found'

        # Get the timestamp of the latest backup
        last_backup_time = datetime.fromtimestamp(os.path.getmtime(latest_backup_file))
        elapsed_time_str = self.format_time_since(last_backup_time)
        if verbose:
            return f"Latest backup: {latest_backup_file.stem} at {last_backup_time.strftime('%Y-%m-%d %H:%M:%S')} ({elapsed_time_str})"
        else:
            return elapsed_time_str

    def get_latest_backup_file(self):
        try:
            files = list(Path(self.primary_archive_dir).glob('*.tar.gz'))
            if files:
                # Sort files by last modification time in descending order and return the latest file
                latest_file = max(files, key=lambda x: x.stat().st_mtime)
                return latest_file
        except Exception as e:
            print(f"Error listing files in {self.primary_archive_dir}: {e}")
        return None

    def format_time_since(self, past_datetime):
        time_diff = datetime.now() - past_datetime
        time_string = convert_seconds(time_diff.total_seconds())
        return "Last backup: " + time_string
        
    def _print_report(self, files_):
        [print(x) for x in files_]
        if len(files_) > 5:
            print(self.report_text)       
        
    def show_include(self):
        self.init_backup()
        files_ = self.files_to_include
        print(f'{len(files_)} files to include in the archive:')
        self._print_report(files_)
        
    def show_exclude(self):
        self.init_backup()
        files_ = self.files_to_exlude
        print(f'{len(files_)} files to exclude from the archive:')
        self._print_report(files_)
    

def main():
    start_time = perf_counter()
    parser = argparse.ArgumentParser(description="Backup Utility")

    # Common and important options are typically placed at the top
    parser.add_argument("-b", "--backup", action="store_true", help="Perform a backup")
    parser.add_argument("-x", "--extract", action="store_true", help="Extract the latest archive to test")
    parser.add_argument("--history", action="store_true", help="Show the history of the backup directory")
    parser.add_argument("-p", "--path", type=str, help="Specify a custom backup directory")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose mode")

    # More specific or less commonly used options can be placed next
    parser.add_argument("-e", "--exclude", action="store_true", help="Show the files that would be excluded from the archives")
    parser.add_argument("-i", "--include", action="store_true", help="Show the files that would be incuded in the archive")
    parser.add_argument("-s", "--settings", action="store_true", help="Report current backup settings")
    parser.add_argument("-t", "--text", action="store_true", help="Show the last backup.txt file")
    parser.add_argument("-l", "--log", action="store_true", help="Show the backup log")
    parser.add_argument("--debug", action="store_true", help="Run in debug mode.")
    short_help = 'Use: backup -b to run backup, backup -h for help.'
    args = parser.parse_args()
    
    print("Rog's New Backup Utility")
    backup_util = BackupUtility()
    print(backup_util.last_backup())
    
    if args.include:
        backup_util.show_include()
        
    if args.exclude:
        backup_util.show_exclude()

    if args.history:
        backup_util.list_archives()

    if args.settings:
        backup_util.report_values()

    if args.text:
        backup_util.show_report_text()
    
    if args.log:
        backup_util.show_log()
    
    if args.extract:
        backup_util.extract()

    if args.path:
        backup_util.archive_dirs = [args.path] + backup_util.archive_dirs
    
    if args.backup:
        if args.debug:
            backup_util.perform_backup(verbose=args.verbose)
        else:
            try:
                backup_util.perform_backup(verbose=args.verbose)
            except Exception as e:
                print(f"Error during backup: {e}")
    else:
        print(short_help)
        
    run_time = perf_counter() - start_time
    if run_time > 1:
        print(f'Completed in {run_time:.2f} seconds')

if __name__ == "__main__":
    main()
