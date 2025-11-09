"""
Large file finder over SSH.

Scans remote directories via SSH to identify large files and folders
containing multiple large files. Useful for media library management.
"""
import dataclasses
import argparse
import os
import subprocess
from collections import defaultdict
import paramiko  # type: ignore[import]
from .bytes import byte_size
from .tomlr import load_rogkit_toml

DEFAULT_MEDIA_CONFIG = {
    "remote_host": "192.168.0.50",
    "remote_user": "rog",
    "remote_password": "",
    "remote_folders": ["/mnt/media1/Media/Movies"],
}
        
@dataclasses.dataclass
class FileObject:
    """Represents a file with path, size, and parent folder."""
    path: str
    size: int = 0
    folder: str = ""

    def __post_init__(self):
        parts = self.path.split('/')
        self.name = parts[-1]
        self.folder = '/'.join(parts[:-1])

def load_media_config():
    """Load media-related defaults from rogkit config."""
    config = load_rogkit_toml()
    media_config = config.get("media", {})
    merged = {**DEFAULT_MEDIA_CONFIG, **media_config}
    raw_folders = merged.get("remote_folders")

    if not raw_folders:
        legacy_folder = media_config.get("remote_folder") or merged.get("remote_folder")
        if legacy_folder:
            raw_folders = legacy_folder

    if isinstance(raw_folders, str):
        folders = [raw_folders]
    elif isinstance(raw_folders, (list, tuple, set)):
        folders = [str(folder) for folder in raw_folders]
    else:
        folders = list(DEFAULT_MEDIA_CONFIG["remote_folders"])

    return {
        "hostname": merged.get("remote_host", DEFAULT_MEDIA_CONFIG["remote_host"]),
        "username": merged.get("remote_user", DEFAULT_MEDIA_CONFIG["remote_user"]),
        "password": merged.get("remote_password", DEFAULT_MEDIA_CONFIG["remote_password"]),
        "folders": folders,
    }

def parse_args(defaults):
    """Parse command-line arguments for large file finder."""
    parser = argparse.ArgumentParser(description="List large files and folders with multiple large files over SSH.")
    parser.add_argument('search', nargs='*', help='Text to search for.')
    parser.add_argument('-a', '--all', action='store_true', help='Show all relevant paths') 
    parser.add_argument('-s', '--small', action='store_true', help='Show small files') 
    parser.add_argument('-l', '--large', action='store_true', help='Show large files') 
    parser.add_argument('--folder', type=str, required=False, help='Folder to check (default: all configured remote folders)')
    parser.add_argument('--hostname', type=str, required=False, default=defaults["hostname"], help='SSH server hostname')
    parser.add_argument('--username', type=str, required=False, default=defaults["username"], help='SSH username')
    parser.add_argument('--password', type=str, required=False, default=defaults["password"], help='SSH password')
    parser.add_argument('--min_size', type=int, default=500_000_000, help='Minimum file size in bytes')
    parser.add_argument('--large_file_size', type=int, default=50000000, help='Size defining a very large file')
    return parser.parse_args()

def execute_command(command: str, folder: str, hostname: str, username: str, password: str | None):
    """Execute command locally if folder exists, otherwise execute remotely via SSH."""
    if os.path.exists(folder):
        process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        output, error = process.communicate()
        if error:
            print(f"Error: {error}")
        return output

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        if password:
            client.connect(hostname=hostname, username=username, password=password)
        else:
            client.connect(hostname=hostname, username=username)
        _, stdout, stderr = client.exec_command(command)
        output = stdout.read().decode()
        error = stderr.read().decode()
        if error:
            print(f"Error: {error}")
        return output
    finally:
        client.close()

def get_file_objects(folder, hostname, username, password, command):
    """Execute remote command and parse output into FileObject instances."""
    file_objects = []
    output = execute_command(command, folder, hostname, username, password)

    if not output:
        return file_objects
    
    for line in output.split('\n'):
        if line:  # Check if line is not empty
            size, path = line.split('\t', 1)
            file_objects.append(FileObject(path=path, size=int(size)))
    return file_objects

def analyze_files(file_objects, min_size, large_file_size):
    """Analyze file objects to identify large files and folders with multiple large files."""
    large_files = [file for file in file_objects if file.size >= min_size]
    folder_counts = defaultdict(int)
    for file in large_files:
        if file.size >= large_file_size:
            folder_counts[file.folder] += 1
    return large_files, {folder: count for folder, count in folder_counts.items() if count > 1}

def main():
    """CLI entry point for large file finder."""
    print("Rog's large file finder...")
    defaults = load_media_config()
    args = parse_args(defaults)
    target_folders = [args.folder] if args.folder else defaults["folders"]

    if not target_folders:
        print("No media folders configured. Add remote_folders to the [media] section of your rogkit config.")
        return 1

    all_file_objects = []
    for folder in target_folders:
        print(f"Scanning {folder} ...")
        command = f'find {folder} -type f -exec du -b ' + '{} +'
        try:
            folder_objects = get_file_objects(folder, args.hostname, args.username, args.password, command)
        except (OSError, subprocess.SubprocessError, paramiko.SSHException) as exc:  # pragma: no cover - defensive
            print(f"Error scanning {folder}: {exc}")
            continue
        all_file_objects.extend(folder_objects)

    if not all_file_objects:
        print("No files found in the selected folders.")
        return 0

    large_files, folders_with_multiple_large = analyze_files(all_file_objects, args.min_size, args.large_file_size)

    print(f"Found {len(large_files):,} files larger than {byte_size(args.min_size)} across {len(target_folders)} folder(s)")
    if args.large:
        for file in large_files:
            print(f"{file.path} ({byte_size(file.size)})")
        print()
        
    search_terms = ' '.join(args.search).strip('"').lower() if args.search else None
    if search_terms:
        print(f"Searching for '{search_terms}' in {len(all_file_objects):,} files...")
    
    print(f"Found {len(folders_with_multiple_large):,} folders with multiple very large files.")
    if args.all or args.search:
        for folder, count in folders_with_multiple_large.items():
            if search_terms and search_terms not in folder.lower():
                continue
            print(f"{folder}: {count} files")
            # print all paths in the folder
            for file in all_file_objects:
                if file.folder == folder:
                    if args.small or file.size >= args.large_file_size:
                        print(f"{file.path} ({byte_size(file.size)})")
                    
    if not args.all:
        print("Use --all to show all relevant paths.")


if __name__ == "__main__":
    main()
