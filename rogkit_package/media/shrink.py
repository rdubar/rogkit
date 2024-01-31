import os
from .media_settings import media_paths
from ..bin.files import media_info

def shrink_list(paths, search=None):
    print('Experimental File Shrinker')
    if not paths:
        print("No results.")
        return
    total_records = len(paths)
    amount = "all" if not search else f'{len(paths):,} of {total_records:,}'
    print('Shrink: Checking', amount, 'dvd matches...')
    if search:
        check = search.lower()
        paths = [path for path in paths if check in path.title.lower()]
    paths = [path for path in paths if path.codec == 'mpeg2video']  
    for path in paths:
        print(path)

def is_file_codec(path, codec):
    if not os.path.exists(path):
        return False
    if not os.path.isfile(path):
        return False
    if not path.endswith('.mkv') and not path.endswith('.mp4'):
        return False
    return codec.lower() in path.lower()


def find_all_uncompressed_dvds():
    print('Find all uncompressed DVD rips.')
    total_files = []
    for path in media_paths:
        if not os.path.exists(path):
            print(f'Path not found: {path}')
            continue
        print(f'Checking path: {path}')
        for root, dirs, files in os.walk(path):
            for file in files:
                if file.endswith('.mkv') or file.endswith('.mp4'):
                    total_files.append(os.path.join(root, file))
