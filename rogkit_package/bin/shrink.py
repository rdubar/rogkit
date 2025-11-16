#!/usr/bin/env python3
"""
Video shrink utility for RogKit.

Features:
- Search recursively for likely DVD rips that can be shrunk.
- Estimate potential space savings for a given video file.
- Optionally re-encode a video using ffmpeg with sensible defaults.

The resulting shrunk file is saved alongside the original using the
suffix "-shrunk" before the file extension.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

VIDEO_EXTENSIONS = {
    ".mkv",
    ".mp4",
    ".mov",
    ".avi",
    ".mpg",
    ".mpeg",
    ".m4v",
    ".ts",
    ".m2ts",
    ".vob",
    ".iso",
}

DEFAULT_MIN_SIZE_GB = 4.0
DEFAULT_VIDEO_KBPS = 2000
DEFAULT_AUDIO_KBPS = 160
DEFAULT_REDUCTION_FACTOR = 0.6  # Target roughly 40% savings if bitrate known.


def human_size(num_bytes: float) -> str:
    """Return a human readable size for bytes."""
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(num_bytes)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} PB"


def find_candidate_videos(root: Path, min_size_gb: float) -> List[Path]:
    """Recursively find large video files likely to be DVD rips."""
    min_size_bytes = min_size_gb * (1024**3)
    candidates: List[Path] = []
    for path in root.rglob("*"):
        try:
            if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS:
                if path.stat().st_size >= min_size_bytes:
                    candidates.append(path)
            elif path.is_dir() and path.name.upper() == "VIDEO_TS":
                candidates.append(path)
        except (PermissionError, OSError):
            continue
    return sorted(candidates)


def ensure_tool_available(tool: str) -> bool:
    """Check if a CLI tool is available in PATH."""
    return shutil.which(tool) is not None


def probe_video_metadata(
    video_path: Path,
) -> Tuple[Optional[float], Optional[int], Optional[int], Optional[str]]:
    """
    Use ffprobe to extract duration and bitrates.

    Returns:
        duration_seconds, overall_bitrate_bps, video_bitrate_bps, video_codec_name
    """
    if not ensure_tool_available("ffprobe"):
        return None, None, None, None

    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_entries",
        "format=duration,bit_rate,size:stream=codec_type,bit_rate,codec_name",
        str(video_path),
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None, None, None, None

    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None, None, None, None

    duration: Optional[float] = None
    format_bitrate: Optional[int] = None
    video_bitrate: Optional[int] = None
    video_codec: Optional[str] = None

    fmt = data.get("format", {})
    if "duration" in fmt:
        try:
            duration = float(fmt["duration"])
        except (TypeError, ValueError):
            duration = None
    if "bit_rate" in fmt:
        try:
            format_bitrate = int(fmt["bit_rate"])
        except (TypeError, ValueError):
            format_bitrate = None

    for stream in data.get("streams", []):
        if stream.get("codec_type") == "video":
            if "bit_rate" in stream:
                try:
                    video_bitrate = int(stream["bit_rate"])
                except (TypeError, ValueError):
                    video_bitrate = None
            codec_name = stream.get("codec_name")
            if isinstance(codec_name, str) and codec_name:
                video_codec = codec_name
            break

    return duration, format_bitrate, video_bitrate, video_codec


def estimate_target_size(
    duration_seconds: Optional[float],
    current_bitrate_bps: Optional[int],
    target_video_kbps: int,
    audio_kbps: int,
    reduction_factor: float,
) -> Optional[int]:
    """Estimate the encoded size in bytes."""
    if not duration_seconds or duration_seconds <= 0:
        return None

    if current_bitrate_bps and current_bitrate_bps > 0:
        current_video_kbps = max((current_bitrate_bps / 1000) - audio_kbps, target_video_kbps)
        adjusted_video_kbps = min(current_video_kbps * reduction_factor, target_video_kbps)
        adjusted_video_kbps = max(800, adjusted_video_kbps)  # avoid going too low by default
    else:
        adjusted_video_kbps = target_video_kbps

    total_kbps = adjusted_video_kbps + audio_kbps
    estimated_bits = duration_seconds * total_kbps * 1000
    return int(estimated_bits / 8)


def build_ffmpeg_command(
    source: Path,
    destination: Path,
    codec: str,
    crf: int,
    preset: str,
    audio_kbps: int,
    extra_args: Iterable[str],
) -> List[str]:
    """Construct the ffmpeg command for encoding."""
    cmd: List[str] = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "info",
        "-y",
        "-i",
        str(source),
        "-c:v",
        codec,
        "-preset",
        preset,
        "-crf",
        str(crf),
        "-c:a",
        "aac",
        "-b:a",
        f"{audio_kbps}k",
        "-movflags",
        "+faststart",
    ]
    cmd.extend(extra_args)
    cmd.append(str(destination))
    return cmd


def confirm(prompt: str, assume_yes: bool = False) -> bool:
    """Prompt the user for confirmation."""
    if assume_yes:
        return True
    response = input(f"{prompt} [y/N]: ").strip().lower()
    return response in {"y", "yes"}


def perform_search(args: argparse.Namespace) -> None:
    """Handle --search mode."""
    root = Path(args.target).expanduser().resolve() if args.target else Path.cwd().resolve()
    print(f"Scanning for large video files under {root} ...")
    candidates = find_candidate_videos(root, args.min_size_gb)

    if not candidates:
        print("No likely DVD rips found.")
        return

    print(f"Found {len(candidates)} candidate(s):")
    for path in candidates:
        try:
            if path.is_dir():
                print(f"DIR  {path}")
            else:
                size = human_size(path.stat().st_size)
                print(f"FILE {path} ({size})")
        except (PermissionError, OSError):
            print(f"SKIP {path} (unreadable)")


def perform_shrink(args: argparse.Namespace) -> None:
    """Handle shrink workflow for a single file."""
    if not args.target:
        print("Error: provide a video file to shrink or use --search.", file=sys.stderr)
        sys.exit(1)

    source = Path(args.target).expanduser().resolve()
    if not source.exists() or not source.is_file():
        print(f"Error: {source} is not a valid file.", file=sys.stderr)
        sys.exit(1)

    if not ensure_tool_available("ffmpeg"):
        print("Error: ffmpeg is not available on PATH. Install it first.", file=sys.stderr)
        sys.exit(1)

    duration, overall_bitrate, video_bitrate, video_codec = probe_video_metadata(source)
    source_size = source.stat().st_size

    print(f"Source: {source}")
    print(f"Size  : {human_size(source_size)}")
    if duration:
        print(f"Duration: {duration / 60:.2f} minutes")
    if video_codec:
        print(f"Video codec: {video_codec}")

    estimated_size = estimate_target_size(
        duration,
        video_bitrate or overall_bitrate,
        args.target_video_kbps,
        args.audio_kbps,
        args.reduction_factor,
    )

    if estimated_size:
        projected_savings = source_size - estimated_size
        if projected_savings > 0:
            print(
                f"Estimated shrunk size: {human_size(estimated_size)} "
                f"(savings ≈ {human_size(projected_savings)})"
            )
        else:
            print("Warning: Estimated size is larger than or equal to source; adjust settings.")
    else:
        print("Warning: Unable to estimate target size (missing ffprobe data).")

    if args.dry_run:
        print("Dry run complete. No files were created.")
        return

    destination = source.with_name(f"{source.stem}-shrunk{source.suffix}")
    if destination.exists():
        if not confirm(f"{destination} already exists. Overwrite?", args.yes):
            print("Aborted.")
            return

    print(f"Output will be written to: {destination}")

    if not confirm("Proceed with re-encoding?", args.yes):
        print("Aborted.")
        return

    extra_args: List[str] = []
    if args.copy_subs:
        extra_args.extend(["-map", "0", "-c:s", "copy"])
    else:
        extra_args.extend(["-map", "0:v:0", "-map", "0:a:0?"])

    ffmpeg_cmd = build_ffmpeg_command(
        source=source,
        destination=destination,
        codec=args.codec,
        crf=args.crf,
        preset=args.preset,
        audio_kbps=args.audio_kbps,
        extra_args=extra_args,
    )

    print("Running ffmpeg command:")
    print(" ".join(ffmpeg_cmd))

    try:
        subprocess.run(ffmpeg_cmd, check=True)
    except subprocess.CalledProcessError as exc:
        print(f"ffmpeg failed with exit code {exc.returncode}.", file=sys.stderr)
        if destination.exists():
            destination.unlink(missing_ok=True)
        sys.exit(exc.returncode)
    except KeyboardInterrupt:
        print("Encoding interrupted by user.")
        if destination.exists():
            destination.unlink(missing_ok=True)
        sys.exit(1)

    print("Encoding completed successfully.")
    if estimated_size:
        final_size = destination.stat().st_size
        actual_savings = source_size - final_size
        print(f"Final size: {human_size(final_size)} (saved {human_size(actual_savings)})")
    else:
        print(f"Final size: {human_size(destination.stat().st_size)}")
    print("Original file has been preserved. Use --replace to swap manually if desired.")


def parse_arguments(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Find and shrink large video files using ffmpeg."
    )
    parser.add_argument(
        "target",
        nargs="?",
        help="Video file to shrink or starting directory when using --search.",
    )
    parser.add_argument(
        "--search",
        action="store_true",
        help="Search recursively for likely DVD rips starting from the current directory or provided target.",
    )
    parser.add_argument(
        "--min-size-gb",
        type=float,
        default=DEFAULT_MIN_SIZE_GB,
        help="Minimum file size in GB to consider during --search (default: %(default)s).",
    )
    parser.add_argument(
        "--codec",
        choices=["libx265", "libx264"],
        default="libx265",
        help="Video codec to use for shrinking (default: %(default)s).",
    )
    parser.add_argument(
        "--crf",
        type=int,
        default=28,
        help="CRF quality setting for ffmpeg (lower is higher quality; default: %(default)s).",
    )
    parser.add_argument(
        "--preset",
        default="medium",
        help="ffmpeg preset controlling encode speed vs compression (default: %(default)s).",
    )
    parser.add_argument(
        "--target-video-kbps",
        type=int,
        default=DEFAULT_VIDEO_KBPS,
        help="Target video bitrate used when estimating output size (default: %(default)s kbps).",
    )
    parser.add_argument(
        "--audio-kbps",
        type=int,
        default=DEFAULT_AUDIO_KBPS,
        help="Target audio bitrate for encoding and estimation (default: %(default)s kbps).",
    )
    parser.add_argument(
        "--reduction-factor",
        type=float,
        default=DEFAULT_REDUCTION_FACTOR,
        help="Scale factor applied to current bitrate when estimating size (default: %(default)s).",
    )
    parser.add_argument(
        "--copy-subs",
        action="store_true",
        help="Attempt to copy subtitle streams (if present) instead of dropping them.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only display what would happen without invoking ffmpeg.",
    )
    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Assume yes for all confirmation prompts.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> None:
    """CLI entry point."""
    args = parse_arguments(argv)
    if args.search:
        perform_search(args)
    else:
        perform_shrink(args)


if __name__ == "__main__":
    main()

