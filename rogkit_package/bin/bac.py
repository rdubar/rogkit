
import os

from ..bin.tomlr import load_rogkit_toml

EXCLUDE_PATTERNS = [
        'Library',
        '.DS_Store',
        '.cache',
        '.modular',
        '.pyenv',
        '.local',
        '.Trash',
        '.vscode',
        '.git',
        '.gitignore',
        '.idea',
        '.pyc',
        '.ipynb_checkpoints',
        '.ropeproject',
        'site-packages',
        '__pycache__',
        'venv',
        'node_modules',
        'build',
        'dist',
        'package-lock.json',
        'package.json',
        '.virtual',
        'yarn.lock',
        'yarn-error.log'
    ]


def get_all_files(path):
    all_files = []
    for root, dirs, files in os.walk(path):
        for file in files:
            all_files.append(os.path.join(root, file))
    return all_files

def main():
    print("Rog's New Backup Tool")
    user_home = os.path.expanduser('~')

    all_files = get_all_files(user_home)

    include_files = [x for x in all_files if not any([y in x for y in EXCLUDE_PATTERNS])]

    print(f'Found {len(include_files):,} files to backup from {len(all_files):,} total files')

    # for file in include_files:
    #     if 'venv' in file:
    #         print(file)

    # get the folder this script is in
    script_dir = os.path.dirname(os.path.realpath(__file__))

    file_list_path = os.path.join(script_dir, 'bac.txt')
    with open(file_list_path, 'w') as f:
        for file in include_files:
            f.write(file + '\n')

    print(f'Wrote file list to {file_list_path}')


if __name__ == '__main__':
    main()