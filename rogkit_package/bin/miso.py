#!/usr/bin/env python3
import os
import sys
import subprocess
import argparse

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
        return mount_dir  # Return without mounting if already mounted
    if verbose:
        print(f"Mounting {iso_path} to {mount_dir}")
    subprocess.run(["sudo", "mount", "-o", "loop", iso_path, mount_dir], check=True)
    return mount_dir

def find_vob_files(video_ts_path, verbose=False):
    # Get all VOB files in sorted order
    vob_files = sorted(
        [os.path.join(video_ts_path, f) for f in os.listdir(video_ts_path) if f.endswith(".VOB")]
    )
    if verbose:
        print(f"Found VOB files: {vob_files}")
    return vob_files

def concatenate_vob_files(vob_files, output_path="combined.vob", verbose=False):
    if verbose:
        print(f"Concatenating files into {output_path}")
    with open(output_path, "wb") as outfile:
        for vob in vob_files:
            if verbose:
                print(f"Adding {vob} to {output_path}")
            with open(vob, "rb") as infile:
                outfile.write(infile.read())

def unmount_iso(mount_dir="/mnt/iso", verbose=False):
    if is_mounted(mount_dir):
        if verbose:
            print(f"Unmounting {mount_dir}")
        subprocess.run(["sudo", "umount", mount_dir], check=True)
    elif verbose:
        print(f"{mount_dir} is not mounted.")

def main():
    parser = argparse.ArgumentParser(description="Combine VOB files from ISO or VIDEO_TS directory into a single file.")
    parser.add_argument("path", help="Path to ISO file or VIDEO_TS directory")
    parser.add_argument("-o", "--output", default="combined.vob", help="Output file name (default: combined.vob)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")

    args = parser.parse_args()
    input_path = args.path
    output_path = args.output
    verbose = args.verbose

    mount_dir = "/mnt/iso"
    video_ts_path = input_path

    # Check if input is an ISO file or VIDEO_TS directory
    if os.path.isfile(input_path) and input_path.endswith(".iso"):
        # Mount the ISO file
        mount_dir = mount_iso(input_path, verbose=verbose)
        video_ts_path = os.path.join(mount_dir, "VIDEO_TS")
    elif not os.path.isdir(video_ts_path):
        print("Error: The path provided is not a valid ISO file or VIDEO_TS directory.")
        sys.exit(1)

    # Find and concatenate VOB files
    vob_files = find_vob_files(video_ts_path, verbose=verbose)
    concatenate_vob_files(vob_files, output_path=output_path, verbose=verbose)

    # Unmount ISO if mounted
    if os.path.isfile(input_path) and input_path.endswith(".iso"):
        unmount_iso(mount_dir, verbose=verbose)

    if verbose:
        print(f"Combined VOB file created as '{output_path}'.")

if __name__ == "__main__":
    main()