import ffmpeg
import os
import sys

def get_media_info(file_path):
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
                'bitrate': video_stream['bit_rate']
            }

        # Get audio information if available
        if audio_stream is not None:
            info['audio'] = {
                'codec': audio_stream['codec_name'],
                'bitrate': audio_stream['bit_rate']
            }

        return info

    except ffmpeg.Error as e:
        print(f"Error occurred: {e.stderr}", file=sys.stderr)
        return None

def main(directory):
    for root, dirs, files in os.walk(directory):
        for file in files:
            file_path = os.path.join(root, file)
            info = get_media_info(file_path)
            if info is not None:
                print(f"File: {file_path}")
                for stream_type, details in info.items():
                    print(f"  {stream_type.capitalize()}:")
                    for key, value in details.items():
                        print(f"    {key.capitalize()}: {value}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python media_scan.py <directory_path>")
        sys.exit(1)
    
    main(sys.argv[1])
