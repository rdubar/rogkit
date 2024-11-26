#!/usr/bin/env python3
import os
import sys
import subprocess
import argparse
import re


def is_mounted(mount_dir):
    """Check if a directory is already mounted."""
    result = subprocess.run(["mountpoint", "-q", mount_dir])
    return result.returncode == 0


def mount_iso(iso_path, mount_dir="/mnt/iso", verbose=False):
    if not os.path.exists(mount_dir):
        os.makedirs(mount_dir)
    if is_mounted(mount_dir):
        if verbose:
            print(f"{mount_dir} is already mounted.")
        return mount_dir
    if verbose:
        print(f"Mounting {iso_path} to {mount_dir}")
    subprocess.run(["sudo", "mount", "-o", "loop", iso_path, mount_dir], check=True)
    return mount_dir


def find_vob_files(video_ts_path, verbose=False):
    """Get all VOB files in sorted order."""
    if not os.path.exists(video_ts_path):
        raise ValueError(f"{video_ts_path} does not exist.")

    vob_files = sorted(
        [os.path.join(video_ts_path, f) for f in os.listdir(video_ts_path) if f.lower().endswith(".vob")]
    )
    if verbose:
        print(f"Found VOB files: {vob_files}")
    return vob_files


def concatenate_vob_files(vob_files, output_path="combined.vob", verbose=False):
    """Concatenate VOB files into one."""
    if not vob_files:
        raise ValueError("No VOB files found to concatenate.")
    if verbose:
        print(f"Concatenating files into {output_path}")
    with open(output_path, "wb") as outfile:
        for vob in vob_files:
            if verbose:
                print(f"Adding {vob} to {output_path}")
            with open(vob, "rb") as infile:
                outfile.write(infile.read())


def convert_to_mp4(vob_path, output_path, verbose=False):
    """Convert a VOB file to MP4 format using ffmpeg."""
    if verbose:
        print(f"Converting {vob_path} to {output_path} (MP4 format).")
    subprocess.run(
        ["ffmpeg", "-i", vob_path, "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-c:a", "aac", output_path],
        check=True
    )


def unmount_iso(mount_dir="/mnt/iso", verbose=False):
    """Unmount the ISO if mounted."""
    if is_mounted(mount_dir):
        if verbose:
            print(f"Unmounting {mount_dir}")
        subprocess.run(["sudo", "umount", mount_dir], check=True)
    elif verbose:
        print(f"{mount_dir} is not mounted.")


def infer_movie_name(input_path):
    """Infer movie name based on the directory or file name."""
    base_name = os.path.basename(input_path)
    movie_name = re.sub(r"[^\w\-]", "_", base_name).strip("_")  # Replace invalid filename characters
    return movie_name


def main():
    parser = argparse.ArgumentParser(
        description="Combine VOB files from ISO or VIDEO_TS directory into a single movie file."
    )
    parser.add_argument("path", help="Path to ISO file or VIDEO_TS directory")
    parser.add_argument("-o", "--output", help="Output file name (default: inferred from input)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")
    parser.add_argument("--format", choices=["vob", "mp4"], default="mp4", help="Output format (default: mp4)")

    args = parser.parse_args()
    input_path = args.path
    verbose = args.verbose
    output_format = args.format

    # Infer output file name
    movie_name = infer_movie_name(input_path)
    default_output = f"{movie_name}.{output_format}"
    output_path = args.output or default_output

    mount_dir = "/mnt/iso"
    video_ts_path = input_path

    try:
        # Check if input is an ISO file or VIDEO_TS directory
        if os.path.isfile(input_path) and input_path.lower().endswith(".iso"):
            # Mount the ISO file
            mount_dir = mount_iso(input_path, verbose=verbose)
            video_ts_path = os.path.join(mount_dir, "VIDEO_TS")
        elif not os.path.isdir(video_ts_path):
            print("Error: The path provided is not a valid ISO file or VIDEO_TS directory.")
            sys.exit(1)

        # Find and concatenate VOB files
        vob_files = find_vob_files(video_ts_path, verbose=verbose)
        vob_output = f"{movie_name}.vob"
        concatenate_vob_files(vob_files, output_path=vob_output, verbose=verbose)

        # Convert to movie format if required
        if output_format == "mp4":
            convert_to_mp4(vob_output, output_path, verbose=verbose)
            os.remove(vob_output)  # Clean up intermediate VOB file

        if verbose:
            print(f"Movie file created: {output_path}")

    finally:
        # Unmount ISO if mounted
        if os.path.isfile(input_path) and input_path.lower().endswith(".iso"):
            unmount_iso(mount_dir, verbose=verbose)


if __name__ == "__main__":
    main()