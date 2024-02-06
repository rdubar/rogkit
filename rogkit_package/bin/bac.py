import os
import time
import subprocess
from datetime import datetime
import tempfile

from ..bin.tomlr import load_rogkit_toml  # Placeholder for actual import
from ..bin.seconds import convert_seconds
from ..bin.bytes import byte_size

EXCLUDE_PATTERNS = [
    '.csm_setup', 'Library', '.DS_Store', '.cache', '.modular',
    '.pyenv', '.local', '.Trash', '.vscode', '.git', '.gitignore', '.idea',
    '.pyc', '.ipynb_checkpoints', '.ropeproject', 'site-packages', '__pycache__',
    'venv', 'node_modules', 'build', 'dist', 'package-lock.json', 'package.json',
    '.virtual', '.docker', 'yarn.lock', 'yarn-error.log', 'tar.gz'
]

def get_all_files(path):
    all_files = []
    for root, _, files in os.walk(path):
        files = [os.path.join(root, file) for file in files if file_filter(os.path.join(root, file))]
        all_files.extend(files)
    return all_files

def file_filter(file_path):
    return not any(excluded in file_path for excluded in EXCLUDE_PATTERNS)

def main():
    print("Rog's New Backup Tool")
    start_time = time.perf_counter()
    user_home = os.path.expanduser('~')

    print(f'Finding files in {user_home}')
    all_files = get_all_files(user_home)
    include_files = all_files  # Filter is applied during file collection

    print(f'Found {len(include_files):,} files to backup from {len(all_files):,} total files.')

    # Use NamedTemporaryFile for the list of files and TemporaryFile for the actual backup
    with tempfile.NamedTemporaryFile(mode='w+', delete=False) as file_list:
        file_list.writelines(f"{file}\n" for file in include_files)
        file_list.flush()

        with tempfile.NamedTemporaryFile(delete=False) as backup_temp:
            backup_name = f'backup-{datetime.today().strftime("%Y-%m-%d")}.{len(include_files):,}.tar.gz'
            backup_path = os.path.join(user_home, backup_name)

            try:
                subprocess.run(['tar', '-czf', backup_temp.name, '-T', file_list.name], check=True)
                os.rename(backup_temp.name, backup_path)  # Move the temporary backup to its final location
                size = os.path.getsize(backup_path)
            except Exception as e:
                print(f'Error during backup: {e}')
                return
            finally:
                os.remove(file_list.name)  # Clean up the file list after backup

    elapsed_time = convert_seconds(time.perf_counter() - start_time)
    size_str = byte_size(size)
    print(f'Backup complete: {len(include_files):,} files backed up to {backup_path} ({size_str}) in {elapsed_time}')

if __name__ == '__main__':
    main()
