import ffmpeg
import os
import sys

def bitrate2k(text: str) -> str:
    if text.isdigit():
        return f"{int(text) // 1024:,}kb"
    return text

def get_media_info(file_path):
    if not file_path.lower().endswith(('.mp4', '.avi', '.mkv', '.mov', '.flv', '.wmv', '.webm', '.mpg', '.mpeg', '.m4v', '.3gp', '.3g2', '.ts', '.vob', '.f4v', '.f4p', '.f4a', '.f4b', '.m4a', '.m4b')):
        return
    try:
        # Get probe data
        probe = ffmpeg.probe(file_path)
        video_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
        audio_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'audio'), None)

        # Initialize info dictionary
        info = {}

        # Get video information if available
        if video_stream is not None:
            info['video'] = {
                'resolution': f"{video_stream['width']}x{video_stream['height']}",
                'codec': video_stream['codec_name'],
                'bitrate': bitrate2k(video_stream['bit_rate'])
            }

        # Get audio information if available
        if audio_stream is not None:
            info['audio'] = {
                'codec': audio_stream['codec_name'],
                'bitrate': bitrate2k(audio_stream['bit_rate'])
            }

        return info

    except ffmpeg.Error as e:
        print(f"Error occurred: {e.stderr}", file=sys.stderr)
        return None

def main(directory):
    output_lines = []  # Store each line of output here
    longest = 0  # Keep track of the longest file path for formatting

    for root, dirs, files in os.walk(directory):
        for file in files:
            file_path = os.path.join(root, file)
            info = get_media_info(file_path)
            if info is not None:
                out = [file_path]  # Start with file path
                for stream_type, details in info.items():
                    for key, value in details.items():
                        out.append(value)
                if len(file_path) > longest:
                    longest = len(file_path)
                output_lines.append(out)  # Add this file's info to the output list

    for line in output_lines:
        file_path = line[0]
        print(f"{file_path.ljust(longest)}     ", end=" ")  # Print the file path, padded to align columns
        for info in line[1:]:  # Print the rest of the info for this file
            print(f'{info:>10}', end=" ")
        print()  # Newline after each file's info



if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python media_scan.py <directory_path>")
        sys.exit(1)
    
    main(sys.argv[1])
