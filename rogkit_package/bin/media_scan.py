import os
import sys
import ffmpeg
from .bytes import byte_size

def bitrate2k(text: str) -> str:
    """Convert bitrate from bytes to kilobytes."""
    if text.isdigit():
        return f"{int(text) // 1024:,}kb"
    return text

def get_media_info(file_path):
    """Get media info as a formatted string for the provided file."""
    if not file_path.lower().endswith((
        '.mp4', '.avi', '.mkv', '.mov', '.flv', '.wmv', '.webm',
        '.mpg', '.mpeg', '.m4v', '.3gp', '.3g2', '.ts', '.vob',
        '.f4v', '.f4p', '.f4a', '.f4b', '.m4a', '.m4b'
    )):
        return "Invalid media file type"

    try:
        # Get probe data from ffmpeg
        probe = ffmpeg.probe(file_path)
        video_stream = next(
            (stream for stream in probe['streams'] if stream['codec_type'] == 'video'),
            None
        )
        audio_stream = next(
            (stream for stream in probe['streams'] if stream['codec_type'] == 'audio'),
            None
        )

        # Initialize the info string
        info = []

        # Video details
        if video_stream is not None:
            resolution = f"{video_stream.get('width', 'N/A')}x{video_stream.get('height', 'N/A')}"
            codec = video_stream.get('codec_name', 'N/A')
            bitrate = bitrate2k(video_stream.get('bit_rate', 'N/A'))
            info.append(f"Video: {resolution} | Codec: {codec} | Bitrate: {bitrate}")

        # Audio details
        if audio_stream is not None:
            audio_codec = audio_stream.get('codec_name', 'N/A')
            audio_bitrate = bitrate2k(audio_stream.get('bit_rate', 'N/A'))
            info.append(f"Audio: Codec: {audio_codec} | Bitrate: {audio_bitrate}")

        # File size
        file_size = os.path.getsize(file_path)
        size_info = byte_size(file_size)
        info.append(f"Size: {size_info}")

        # Combine info into a single line
        return f"{file_path} | " + " | ".join(info)

    except ffmpeg.Error as e:
        return f"ffmpeg error occurred: {e.stderr}"
    except Exception as e:
        return f"Error occurred: {e}"

def process_file(file_path):
    """Process a single media file and return its formatted media report."""
    return get_media_info(file_path)

def main(path):
    if os.path.isfile(path):
        # Single file provided
        report = process_file(path)
        print(report)
    elif os.path.isdir(path):
        # Directory provided
        for root, dirs, files in os.walk(path):
            for file in files:
                file_path = os.path.join(root, file)
                report = process_file(file_path)
                print(report)
    else:
        print(f"Invalid path: {path}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python media_scan.py <file_or_directory_path>")
        sys.exit(1)
    main(sys.argv[1])
    