import os
import argparse
from .media_settings import media_paths
from ..bin.files import media_info

def shrink_list(paths, search=None):
    """
    Filters a list of video objects for MPEG-2 codec, with optional title search.

    Args:
        paths (list): List of video objects, each expected to have `title` and `codec` attributes.
        search (str, optional): If provided, filters video titles containing this string (case-insensitive).
    """
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
    """
    Check if a file exists, is a video, and contains the specified codec string in the filename.

    Args:
        path (str): Path to the video file.
        codec (str): Codec string to check.

    Returns:
        bool: True if file matches criteria, else False.
    """
    if not os.path.exists(path):
        return False
    if not os.path.isfile(path):
        return False
    if not path.endswith('.mkv') and not path.endswith('.mp4'):
        return False
    return codec.lower() in path.lower()

def find_all_uncompressed_dvds():
    """
    Scans all configured media_paths for .mkv or .mp4 files (DVD rips).

    Returns:
        list[str]: List of file paths that are video files.
    """
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
    return total_files

def main():
    parser = argparse.ArgumentParser(description="Find uncompressed MPEG2 DVD rips.")
    parser.add_argument('-s', '--search', help='Optional search term to filter by title.')
    args = parser.parse_args()

    files = find_all_uncompressed_dvds()

    # Assume media_info returns objects with `title` and `codec` attributes
    videos = [media_info(f) for f in files]
    shrink_list(videos, search=args.search)

if __name__ == '__main__':
    main()