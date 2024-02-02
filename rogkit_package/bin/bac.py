import os
import time
from datetime import datetime
import tempfile

from ..bin.tomlr import load_rogkit_toml  # TODO: implement TOML setup
from ..bin.seconds import convert_seconds
from ..bin.bytes import byte_size

# Consolidated and corrected EXCLUDE_PATTERNS list
EXCLUDE_PATTERNS = [
    'bac.txt', '.csm_setup', 'Library', '.DS_Store', '.cache', '.modular',
    '.pyenv', '.local', '.Trash', '.vscode', '.git', '.gitignore', '.idea',
    '.pyc', '.ipynb_checkpoints', '.ropeproject', 'site-packages', '__pycache__',
    'venv', 'node_modules', 'build', 'dist', 'package-lock.json', 'package.json',
    '.virtual', '.docker', 'yarn.lock', 'yarn-error.log', 'tar.gz'
]

def get_all_files(path):
    """Get all files in a directory, excluding those matching patterns in EXCLUDE_PATTERNS."""
    all_files = []
    for root, _, files in os.walk(path):
        files = [os.path.join(root, file) for file in files]
        all_files.extend(files)
    return all_files

def file_filter(file_path):
    """Check if the file should be included based on EXCLUDE_PATTERNS."""
    return not any(excluded in file_path for excluded in EXCLUDE_PATTERNS)

def main():
    print("Rog's New Backup Tool")
    start_time = time.perf_counter()
    user_home = os.path.expanduser('~')

    print(f'Finding files in {user_home}')
    all_files = get_all_files(user_home)
    include_files = list(filter(file_filter, all_files))

    print(f'Found {len(include_files):,} files to backup from {len(all_files):,} total files.')

    file_list_path = tempfile.NamedTemporaryFile(delete=False).name
    with open(file_list_path, 'w') as f:
        f.writelines(f"{file}\n" for file in include_files)

    # Create a backup name with timestamp and file count
    backup_name = f'backup-{datetime.today().strftime("%d-%m-%Y")}.{len(include_files):,}.tar.gz'
    backup_path = os.path.join(user_home, backup_name)

    # Use tar command to create the backup directly
    os.system(f'tar -czf {backup_path} -T {file_list_path}')

    elapsed_time = convert_seconds(time.perf_counter() - start_time)
    size = os.path.getsize(backup_path)

    if size:
        size_str = byte_size(size)
        print(f'Backup complete: {len(include_files):,} files backed up to {backup_path} ({size_str}) in {elapsed_time}')
    else:
        print(f'Error creating backup: {backup_path} in {elapsed_time}')

if __name__ == '__main__':
    main()
