#!/usr/bin/env python3
"""
DVD/ISO to movie file converter.

Mounts ISO files, extracts and concatenates VOB files from VIDEO_TS directories,
and converts them to MP4/MKV format with optional compression using ffmpeg.
"""
import os
import sys
import subprocess
import argparse
import re
import time


def is_mounted(mount_dir):
    """Check if a directory is already mounted."""
    result = subprocess.run(["mountpoint", "-q", mount_dir])
    return result.returncode == 0


def mount_iso(iso_path, mount_dir="/mnt/iso", verbose=False):
    # TODO: allow mount_dir default to come from configuration/environment.
    """Mount an ISO file to the specified directory."""
    if not os.path.exists(mount_dir):
        os.makedirs(mount_dir)
    if is_mounted(mount_dir):
        print(f"{mount_dir} is already mounted.")
        return mount_dir
    print(f"Mounting {iso_path} to {mount_dir}")
    subprocess.run(["sudo", "mount", "-o", "loop", iso_path, mount_dir], check=True)
    return mount_dir


def find_vob_files(video_ts_path, verbose=False):
    """Get all VOB files in sorted order."""
    print(f"Searching for VOB files in {video_ts_path}...")
    if not os.path.exists(video_ts_path):
        raise ValueError(f"{video_ts_path} does not exist.")

    vob_files = sorted(
        [os.path.join(video_ts_path, f) for f in os.listdir(video_ts_path) if f.lower().endswith(".vob")]
    )
    if not vob_files:
        raise ValueError("No VOB files found.")
    print(f"Found {len(vob_files)} VOB files.")
    return vob_files


def concatenate_vob_files(vob_files, output_path="combined.vob", verbose=False):
    """Concatenate VOB files into one."""
    print(f"Concatenating {len(vob_files)} VOB files into {output_path}...")
    with open(output_path, "wb") as outfile:
        for vob in vob_files:
            print(f"Adding {vob} to {output_path}")
            with open(vob, "rb") as infile:
                outfile.write(infile.read())
    print(f"Finished concatenating VOB files into {output_path}")


def convert_to_movie_format(vob_path, output_path, format="mp4", compress=None, verbose=False):
    """
    Convert a VOB file to MP4 or MKV format with optional compression.
    - compress=None: No compression, copy streams directly.
    - compress=23: Reasonable compression (default for ffmpeg CRF).
    """
    if compress is None:
        # No compression, just copy streams
        print(f"Converting {vob_path} to {output_path} ({format.upper()} format) at maximum speed (no compression)...")
        command = ["ffmpeg", "-i", vob_path, "-c", "copy", "-f", format, output_path]
    else:
        # Compress using the specified CRF value
        compress = int(compress)  # Ensure compress is an integer
        print(f"Converting {vob_path} to {output_path} ({format.upper()} format) with compression level: {compress}...")
        command = [
            "ffmpeg",
            "-i", vob_path,
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", str(compress),
            "-c:a", "aac",
            output_path
        ]

    if verbose:
        print(f"Running command: {' '.join(command)}")

    try:
        subprocess.run(command, check=True)
        print(f"Conversion completed. Output file: {output_path}")
    except subprocess.CalledProcessError as e:
        print(f"Error during conversion: {e}")
        raise


def unmount_iso(mount_dir="/mnt/iso", verbose=False):
    # TODO: allow mount_dir default to come from configuration/environment.
    """Unmount the ISO if mounted."""
    if is_mounted(mount_dir):
        print(f"Unmounting {mount_dir}")
        subprocess.run(["sudo", "umount", mount_dir], check=True)
    else:
        print(f"{mount_dir} is not mounted.")


def infer_movie_name(input_path):
    """
    Infer movie name based on the directory or file name.
    
    Sanitizes the name for use as a filename.
    """
    base_name = os.path.basename(input_path)
    movie_name = re.sub(r"[^\w\-]", "_", base_name).strip("_")  # Replace invalid filename characters
    return movie_name


def main():
    """CLI entry point for ISO/DVD to movie converter."""
    start_time = time.time()
    
    parser = argparse.ArgumentParser(
        description="Combine VOB files from ISO or VIDEO_TS directory into a single movie file.",
        epilog="Example usage:\n"
               "  1. No compression (default): miso\n"
               "  2. Default compression: miso -c\n"
               "  3. Custom compression: miso -c 18\n"
               "  4. Output as MKV: miso --format mkv",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("path", nargs="?", help="Path to ISO file or VIDEO_TS directory")
    parser.add_argument("-o", "--output", help="Output file name (default: inferred from input)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")
    parser.add_argument("--format", choices=["mp4", "mkv"], default="mp4", help="Output format (default: mp4)")
    parser.add_argument(
        "-c", "--compress", nargs="?", const=23, type=int,
        help="Enable compression. Specify a CRF value (default: 23, typical range: 18-28).\n"
             "Lower values = better quality & larger file size.\n"
             "No compression if omitted."
    )

    args = parser.parse_args()

    # Show help if no arguments are provided
    if not args.path:
        parser.print_help()
        sys.exit(1)

    input_path = args.path
    verbose = args.verbose
    output_format = args.format
    compress = args.compress

    # Infer output file name
    movie_name = infer_movie_name(input_path)
    default_output = f"{movie_name}.{output_format}"
    output_path = args.output or default_output

    # TODO: prefer configured mount directory over hard-coded /mnt/iso.
    mount_dir = "/mnt/iso"
    video_ts_path = input_path

    try:
        # Check if input is an ISO file or VIDEO_TS directory
        if os.path.isfile(input_path) and input_path.lower().endswith(".iso"):
            print(f"Input is an ISO file: {input_path}")
            mount_dir = mount_iso(input_path, verbose=verbose)
            video_ts_path = os.path.join(mount_dir, "VIDEO_TS")
        elif os.path.isdir(input_path):
            print(f"Input is a VIDEO_TS directory: {input_path}")
        else:
            print("Error: The path provided is not a valid ISO file or VIDEO_TS directory.")
            sys.exit(1)

        # Find and concatenate VOB files
        vob_files = find_vob_files(video_ts_path, verbose=verbose)
        vob_output = f"{movie_name}.vob"
        concatenate_vob_files(vob_files, output_path=vob_output, verbose=verbose)

        # Convert to movie format with optional compression
        convert_to_movie_format(vob_output, output_path, format=output_format, compress=compress, verbose=verbose)

        # Clean up intermediate VOB file
        print(f"Removing intermediate file: {vob_output}")
        os.remove(vob_output)

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

    finally:
        # Unmount ISO if mounted
        if os.path.isfile(input_path) and input_path.lower().endswith(".iso"):
            unmount_iso(mount_dir, verbose=verbose)

    # Print total time taken
    end_time = time.time()
    total_time = round(end_time - start_time, 2)
    print(f"Operation completed in {total_time} seconds.")
    
if __name__ == "__main__":
    main()
    