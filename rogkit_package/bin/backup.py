# New experimental backup tool

import os, sys, argparse, tempfile
from datetime import datetime
from time import perf_counter

from .bytes import byte_size
from .seconds import convert_seconds

user_home = os.path.expanduser('~')

folders_to_backup = [ 'apv', 'dev', 'opt' ]

files_to_exlude = [ 'node_modules', 'build', 'dist', 'package-lock.json', 'tar.gz', '.pyc', '.DS_Store', '.git', 
                   '.idea', '.vscode', '.ipynb_checkpoints', '__pycache__', '.log', '.sqlite', 
                    'package.json', '.virtual', '.docker', 'yarn.lock', 'yarn-error.log']

folders_to_exclude = ['/eggs', 'env/', 'parts/', 'v27', 'internal_packages', 'data/', '/venv', '.git', 'idea']

BACKUP_FOLDERS = ['Dropbox/Archive/MacBookPro/', '/Users/rdubar/OneDrive - Arden Grange/Archive/Backups']

MEGA_BYTE = 1024 * 1024

def create_backup(verbose=False):

    start_time = perf_counter()
    
    backup_path = BACKUP_FOLDERS[0]
    backup_extras = BACKUP_FOLDERS[1:] if len(BACKUP_FOLDERS) > 1 else []

    # current date and time for backup filename withhours and minutes
    current_date = datetime.today().strftime('%Y-%m-%d-%H-%M')

    backup_name = f'backup-{current_date}.tar.gz'

    # make sure the backup path folder exists
    os.makedirs(os.path.join(user_home, backup_path), exist_ok=True)

    path_for_backup = os.path.join(user_home,backup_path, backup_name)

    print(f'Backing up the following folders: {folders_to_backup}') 
    print(f'Backup path: {path_for_backup}')

    file_count = 0
    file_total_size = 0
    skipped = 0

    # create a temporary file to store the list of files to backup
    with tempfile.NamedTemporaryFile(mode='w+', delete=False) as file_list:
        for folder in folders_to_backup:
            for root, dirs, files in os.walk(os.path.join(user_home, folder)):
                for file in files:
                    if not any(exclude in file for exclude in files_to_exlude) and not any(exclude in root for exclude in folders_to_exclude):
                        file_list.write(os.path.join(root, file) + '\n')
                        file_count += 1
                        size = os.path.getsize(os.path.join(root, file))
                        file_total_size += size
                        if verbose:
                            warning = '' if size < MEGA_BYTE else '****'
                            print(f'{byte_size(size):>10}   {os.path.join(root, file)} {warning}')
                    else:
                        skipped += 1
                        
        current_elapsed_time = convert_seconds(perf_counter() - start_time)
        print(f'Found {file_count:,} files to backup ({byte_size(file_total_size)}). Skipped {skipped:,}. Elapsed time: {current_elapsed_time}.')
        
        print(f'Creating backup file: {path_for_backup}')
        
        temp_backup_name = path_for_backup + '.tmp'

        # create the backup
        try:
            os.system(f'tar -czf {temp_backup_name} -T {file_list.name}')
        except Exception as e:
            print(f'Error during backup: {e}')
            os.remove(temp_backup_name)
        finally:
            # remove the temporary file with the list of files
            os.remove(file_list.name)

    if not os.path.exists(temp_backup_name):
        print('Backup failed.')
        os.remove(temp_backup_name)
        sys.exit(1)        

    try:
        os.rename(temp_backup_name, path_for_backup)
    except Exception as e:
        print(f'Error moving backup to final location: {e}')
        sys.exit(1)

    # Now copy the backup to the other locations
    for extra_backup in backup_extras:
        try:
            os.makedirs(os.path.join(user_home, extra_backup), exist_ok=True)
            os.system(f'cp {path_for_backup} "{os.path.join(user_home, extra_backup)}"')
            print(f'Backup copied to {extra_backup}')
        except Exception as e:
            print(f'Error copying backup to {extra_backup}: {e}')
        
    elapsed_time = perf_counter() - start_time
    print(f'Backup created with {file_count:,} files ({byte_size(file_total_size)}) in {convert_seconds(elapsed_time)}.')
    print(f'Backup path: {path_for_backup}')
    
def list_backups():
    backups = [f for f in os.listdir(os.path.join(user_home, 'Dropbox/Archive/MacBookPro')) if f.startswith('backup-')]
    # Create a list of tuples containing backup information
    backup_info = []
    for backup in backups:
        backup_path = os.path.join(user_home, 'Dropbox/Archive/MacBookPro', backup)
        backup_size = byte_size(os.path.getsize(backup_path))
        backup_date = datetime.strptime(backup[7:22], '%Y-%m-%d-%H-%M')
        backup_info.append((backup_size, backup_path, backup_date))

    # Sort the list by backup date
    backup_info.sort(key=lambda x: x[2])

    # Print the sorted backup information
    for size, path, date in backup_info:
        print(f'{size:10}   {date:%Y-%m-%d %H:%M}   {path}')
        
def extract_latest():
    backups = [f for f in os.listdir(os.path.join(user_home, 'Dropbox/Archive/MacBookPro')) if f.startswith('backup-')]
    if not backups:
        print('No backups found.')
        return
    latest_backup = max(backups)
    backup_path = os.path.join(user_home, BACKUP_FOLDER, latest_backup)
    extract_dir = os.path.join(user_home, BACKUP_FOLDER, latest_backup[:-7])
    if not os.path.exists(extract_dir):
        os.makedirs(extract_dir)
    print(f'Extracting latest backup: {backup_path} to {extract_dir}')
    os.system(f'tar -xzf {backup_path} -C {extract_dir}')
    

def main():
    # create argparse with options -b --backup and -l --list
    parser = argparse.ArgumentParser(description='Backup and list backups')
    parser.add_argument('-b', '--backup', action='store_true', help='Create a new backup')
    parser.add_argument('-l', '--list', action='store_true', help='List backups')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    parser.add_argument('-x', '--extract', action='store_true', help='Extract the latest backup')
    args = parser.parse_args()
    
    if args.extract:
        extract_latest()
        exit(0)
    
    if args.list:
        list_backups()
    elif args.backup:
        create_backup(verbose=args.verbose)
    else:
        print("Rog's New Macbook Backup Tool")
        parser.print_help()
    
if __name__ == '__main__':
    main()