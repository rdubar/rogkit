#!/usr/bin/env python3
"""
DVD/ISO to movie file converter.

Mounts ISO files, extracts and concatenates VOB files from VIDEO_TS directories,
and converts them to MP4/MKV format with optional compression using ffmpeg.
"""
import argparse
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional

CHUNK_SIZE = 64 * 1024  # Streamed copy to avoid loading full VOBs into memory.


def is_mounted(mount_dir: Path) -> bool:
    """Check if a directory is already mounted."""
    result = subprocess.run(["mountpoint", "-q", str(mount_dir)], check=False)
    return result.returncode == 0


def mount_iso(iso_path: Path, mount_dir: Path = Path("/mnt/iso"), verbose: bool = False) -> Path:
    # TODO: allow mount_dir default to come from configuration/environment.
    """Mount an ISO file to the specified directory."""
    mount_dir.mkdir(parents=True, exist_ok=True)
    if is_mounted(mount_dir):
        print(f"{mount_dir} is already mounted.")
        return mount_dir
    print(f"Mounting {iso_path} to {mount_dir}")
    subprocess.run(["sudo", "mount", "-o", "loop", str(iso_path), str(mount_dir)], check=True)
    return mount_dir


def find_vob_files(video_ts_path: Path, verbose: bool = False) -> List[Path]:
    """Get all VOB files in sorted order."""
    print(f"Searching for VOB files in {video_ts_path}...")
    if not video_ts_path.exists():
        raise ValueError(f"{video_ts_path} does not exist.")

    vob_files = sorted([path for path in video_ts_path.iterdir() if path.suffix.lower() == ".vob"])
    if not vob_files:
        raise ValueError("No VOB files found.")
    print(f"Found {len(vob_files)} VOB files.")
    return vob_files


def concatenate_vob_files(
    vob_files: List[Path],
    output_path: Path = Path("combined.vob"),
    verbose: bool = False,
) -> None:
    """Concatenate VOB files into one."""
    print(f"Concatenating {len(vob_files)} VOB files into {output_path}...")
    with output_path.open("wb") as outfile:
        for vob in vob_files:
            print(f"Adding {vob} to {output_path}")
            with vob.open("rb") as infile:
                while True:
                    chunk = infile.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    outfile.write(chunk)
    print(f"Finished concatenating VOB files into {output_path}")


def convert_to_movie_format(
    vob_path: Path,
    output_path: Path,
    format: str = "mp4",
    compress: Optional[int] = None,
    verbose: bool = False,
) -> None:
    """
    Convert a VOB file to MP4 or MKV format with optional compression.
    - compress=None: No compression, copy streams directly.
    - compress=23: Reasonable compression (default for ffmpeg CRF).
    """
    if compress is None:
        # No compression, just copy streams
        print(f"Converting {vob_path} to {output_path} ({format.upper()} format) at maximum speed (no compression)...")
        command = ["ffmpeg", "-i", str(vob_path), "-c", "copy", "-f", format, str(output_path)]
    else:
        # Compress using the specified CRF value
        compress = int(compress)
        if compress < 0:
            raise ValueError("Compression (CRF) must be non-negative.")
        print(f"Converting {vob_path} to {output_path} ({format.upper()} format) with compression level: {compress}...")
        command = [
            "ffmpeg",
            "-i",
            str(vob_path),
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", str(compress),
            "-c:a", "aac",
            str(output_path),
        ]

    if verbose:
        print(f"Running command: {' '.join(command)}")

    try:
        subprocess.run(command, check=True)
        print(f"Conversion completed. Output file: {output_path}")
    except subprocess.CalledProcessError as e:
        print(f"Error during conversion: {e}")
        raise


def unmount_iso(mount_dir: Path = Path("/mnt/iso"), verbose: bool = False) -> None:
    # TODO: allow mount_dir default to come from configuration/environment.
    """Unmount the ISO if mounted."""
    if is_mounted(mount_dir):
        print(f"Unmounting {mount_dir}")
        subprocess.run(["sudo", "umount", str(mount_dir)], check=True)
    else:
        print(f"{mount_dir} is not mounted.")


def infer_movie_name(input_path: Path) -> str:
    """
    Infer movie name based on the directory or file name.
    
    Sanitizes the name for use as a filename.
    """
    base_name = input_path.name
    movie_name = re.sub(r"[^\w\-]", "_", base_name).strip("_")  # Replace invalid filename characters
    return movie_name


def main() -> None:
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

    input_path = Path(args.path).expanduser().resolve()
    verbose = args.verbose
    output_format = args.format
    compress = args.compress

    # Infer output file name
    movie_name = infer_movie_name(input_path)
    default_output = f"{movie_name}.{output_format}"
    output_path = Path(args.output).expanduser() if args.output else Path(default_output)

    # TODO: prefer configured mount directory over hard-coded /mnt/iso.
    mount_dir = Path("/mnt/iso")
    video_ts_path = input_path

    try:
        # Check if input is an ISO file or VIDEO_TS directory
        if input_path.is_file() and input_path.suffix.lower() == ".iso":
            print(f"Input is an ISO file: {input_path}")
            mount_dir = mount_iso(input_path, verbose=verbose)
            video_ts_path = mount_dir / "VIDEO_TS"
        elif input_path.is_dir():
            print(f"Input is a VIDEO_TS directory: {input_path}")
        else:
            print("Error: The path provided is not a valid ISO file or VIDEO_TS directory.")
            sys.exit(1)

        # Find and concatenate VOB files
        vob_files = find_vob_files(video_ts_path, verbose=verbose)
        vob_output = Path(f"{movie_name}.vob")
        concatenate_vob_files(vob_files, output_path=vob_output, verbose=verbose)

        # Convert to movie format with optional compression
        convert_to_movie_format(vob_output, output_path, format=output_format, compress=compress, verbose=verbose)

        # Clean up intermediate VOB file
        print(f"Removing intermediate file: {vob_output}")
        try:
            vob_output.unlink()
        except FileNotFoundError:
            if verbose:
                print(f"Intermediate VOB already removed: {vob_output}")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

    finally:
        # Unmount ISO if mounted
        if input_path.is_file() and input_path.suffix.lower() == ".iso":
            unmount_iso(mount_dir, verbose=verbose)

    # Print total time taken
    end_time = time.time()
    total_time = round(end_time - start_time, 2)
    print(f"Operation completed in {total_time} seconds.")
    
if __name__ == "__main__":
    main()
    