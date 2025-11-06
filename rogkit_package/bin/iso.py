#!/usr/bin/env python3
"""
DVD/ISO main feature extractor using HandBrake.

Scans ISO/DVD files, identifies the longest title (main feature),
and extracts it to MKV format using HandBrakeCLI.
"""
import subprocess
import sys
import re
import os


def find_longest_title(scan_output):
    """
    Parse HandBrake scan output to find the longest title.
    
    Args:
        scan_output: HandBrake scan output text
        
    Returns:
        Title number of the longest title
        
    Raises:
        RuntimeError: If no titles with durations found
    """
    durations = {}
    current_title = None

    for line in scan_output.splitlines():
        title_match = re.match(r'^\+ title (\d+):', line)
        if title_match:
            current_title = int(title_match.group(1))

        duration_match = re.search(r'duration: (\d+):(\d+):(\d+)', line)
        if duration_match and current_title is not None:
            h, m, s = map(int, duration_match.groups())
            total_seconds = h * 3600 + m * 60 + s
            durations[current_title] = total_seconds

    if not durations:
        raise RuntimeError("No titles with durations found in scan output.")

    return max(durations.items(), key=lambda x: x[1])[0]


def extract_main_feature(iso_path, output_path=None):
    """
    Extract the main feature from an ISO/DVD file.
    
    Args:
        iso_path: Path to ISO or DVD file
        output_path: Optional output MKV path (default: <iso_name>_main.mkv)
    """
    if not os.path.exists(iso_path):
        print("❌ ISO file not found:", iso_path)
        sys.exit(1)

    print("🔍 Scanning ISO:", iso_path)
    try:
        result = subprocess.run(
            ["HandBrakeCLI", "-i", iso_path, "-t", "0"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            check=True
        )
    except subprocess.CalledProcessError as e:
        print("❌ Failed to scan ISO:", e)
        print(e.output)
        sys.exit(1)

    longest_title = find_longest_title(result.stdout)
    print(f"✅ Found longest title: {longest_title}")

    base_name = os.path.splitext(os.path.basename(iso_path))[0].replace(" ", "_")
    if not output_path:
        output_path = base_name + "_main.mkv"

    print("🎬 Extracting title", longest_title, "to", output_path)

    command = [
        "HandBrakeCLI",
        "-i", iso_path,
        "-o", output_path,
        "-t", str(longest_title),
        "-e", "x264",
        "-q", "18",
        "-B", "160",
        "--aencoder", "copy:ac3",
        "--audio", "1",
        "--markers"
    ]

    subprocess.run(command)

    print("✅ Done! Saved to:", output_path)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: iso.py <path_to_iso> [output_file.mkv]")
        sys.exit(1)

    iso_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None

    extract_main_feature(iso_path, output_path)