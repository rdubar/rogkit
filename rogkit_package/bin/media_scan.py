import ffmpeg
import os
import sys
from .bytes import byte_size 

def bitrate2k(text: str) -> str:
    if text.isdigit():
        return f"{int(text) // 1024:,}kb"
    return text

def get_media_info(file_path):
    if not file_path.lower().endswith((
        '.mp4', '.avi', '.mkv', '.mov', '.flv', '.wmv', '.webm',
        '.mpg', '.mpeg', '.m4v', '.3gp', '.3g2', '.ts', '.vob',
        '.f4v', '.f4p', '.f4a', '.f4b', '.m4a', '.m4b'
    )):
        return
    try:
        # Get probe data
        probe = ffmpeg.probe(file_path)
        video_stream = next(
            (stream for stream in probe['streams'] if stream['codec_type'] == 'video'),
            None
        )
        audio_stream = next(
            (stream for stream in probe['streams'] if stream['codec_type'] == 'audio'),
            None
        )

        # Initialize info dictionary
        info = {}

        # Get video information if available
        if video_stream is not None:
            video_info = {}
            if 'width' in video_stream and 'height' in video_stream:
                video_info['resolution'] = f"{video_stream['width']}x{video_stream['height']}"
            if 'codec_name' in video_stream:
                video_info['codec'] = video_stream['codec_name']
            if 'bit_rate' in video_stream:
                video_info['bitrate'] = bitrate2k(video_stream['bit_rate'])
            else:
                video_info['bitrate'] = 'N/A'
            info['video'] = video_info

        # Get audio information if available
        if audio_stream is not None:
            audio_info = {}
            if 'codec_name' in audio_stream:
                audio_info['codec'] = audio_stream['codec_name']
            if 'bit_rate' in audio_stream:
                audio_info['bitrate'] = bitrate2k(audio_stream['bit_rate'])
            else:
                audio_info['bitrate'] = 'N/A'
            info['audio'] = audio_info

        # Get file size in human-friendly format
        file_size = os.path.getsize(file_path)
        size_info = {'size': byte_size(file_size)}
        info['size'] = size_info

        return info

    except ffmpeg.Error as e:
        print(f"ffmpeg error occurred: {e.stderr}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"Error occurred: {e}", file=sys.stderr)
        return None

def process_file(file_path, output_lines, longest):
    """Process a single media file and append its info to output_lines."""
    info = get_media_info(file_path)
    out = [file_path]
    if info is not None:
        for stream_type, details in info.items():
            for key, value in details.items():
                out.append(value)
        longest[0] = max(longest[0], len(file_path))
    output_lines.append(out)

def main(path):
    output_lines = []  # Store each line of output here
    longest = [0]  # Keep track of the longest file path for formatting (use list for mutability)

    if os.path.isfile(path):
        # Single file provided
        process_file(path, output_lines, longest)
    elif os.path.isdir(path):
        # Directory provided
        for root, dirs, files in os.walk(path):
            for file in files:
                file_path = os.path.join(root, file)
                process_file(file_path, output_lines, longest)
    else:
        print(f"Invalid path: {path}")
        sys.exit(1)

    # Print results
    for line in output_lines:
        file_path = line[0]
        print(f"{file_path.ljust(longest[0])}     ", end=" ")  # Print the file path, padded to align columns
        for info in line[1:]:  # Print the rest of the info for this file
            print(f'{info:>10}', end=" ")
        print()  # Newline after each file's info

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python media_scan.py <file_or_directory_path>")
        sys.exit(1)
    main(sys.argv[1])
    