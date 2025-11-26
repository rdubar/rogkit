"""
Image batch processor and converter.

Converts HEIC/WEBP/JPG images to compressed JPEGs with configurable max dimensions
and file size. Supports batch processing with backup of originals.
"""
from __future__ import annotations

import argparse
import io
import subprocess
from pathlib import Path
from typing import Iterable, List, Optional

import pyheif  # type: ignore
from PIL import Image  # type: ignore

from .bytes import byte_size


SUPPORTED_EXTS = (".heic", ".webp", ".jpg", ".jpeg")


def list_image_files(directory: Path) -> List[Path]:
    """List supported image files in the directory."""
    try:
        return sorted([p for p in directory.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS])
    except Exception as e:  # pragma: no cover - defensive
        print(f"Error listing files in {directory}: {e}")
        return []


def convert_heic_to_jpg(input_image_path: Path, output_image_path: Path) -> Optional[Image.Image]:
    """Convert HEIC to JPG using ImageMagick."""
    try:
        subprocess.run(["magick", "convert", str(input_image_path), str(output_image_path)], check=True)
        return Image.open(output_image_path)
    except Exception as e:  # pragma: no cover - external tool dependency
        print(f"Error converting HEIC to JPG with ImageMagick: {e}")
        return None


def read_heic_file(input_image_path: Path) -> Optional[Image.Image]:
    """Read a HEIC file and convert it to a PIL Image object."""
    try:
        heif_file = pyheif.read(str(input_image_path))
        return Image.frombytes(
            heif_file.mode,
            heif_file.size,
            heif_file.data,
            "raw",
            heif_file.mode,
            heif_file.stride,
        )
    except pyheif.error.HeifError as e:
        print(f"Error reading HEIC file: {e}")
        output_image_path = input_image_path.with_suffix(".jpg")
        return convert_heic_to_jpg(input_image_path, output_image_path)


def resize_image(img: Image.Image, max_size: int) -> Image.Image:
    """Resize the image so the longest side is max_size (pixels)."""
    max_size = int(max_size)
    img_copy = img.copy()
    img_copy.thumbnail((max_size, max_size))
    return img_copy


def compress_image(image: Image.Image, max_size_kb: int, verbose: bool = False) -> io.BytesIO:
    """Compress the image to be under the desired size (KB)."""
    target_bytes = int(max_size_kb) * 1024
    quality = 85
    buffer = io.BytesIO()

    def _save(q: int) -> io.BytesIO:
        buf = io.BytesIO()
        image.save(buf, format="JPEG", quality=q, optimize=True)
        return buf

    buffer = _save(quality)
    if verbose:
        print(f"Initial Quality: {quality}, Size: {buffer.getbuffer().nbytes / 1024:.2f} KB")

    while quality > 10 and buffer.getbuffer().nbytes > target_bytes:
        quality -= 5
        buffer = _save(quality)
        if verbose:
            print(f"Adjusted Quality: {quality}, Size: {buffer.getbuffer().nbytes / 1024:.2f} KB")

    return buffer


def process_images(
    directory: Path,
    *,
    confirm: bool = False,
    max_size_kb: int = 110,
    max_length_px: int = 800,
    verbose: bool = False,
    debug: bool = False,
) -> None:
    """Process each image file in the directory."""
    files = list_image_files(directory)
    if not files:
        print("No image files found in the directory.")
        return

    if not confirm:
        print(f"Found {len(files)} files to process:")
        for f in files:
            print(f"  {f.name}")
        print("Use -c/--confirm to process the files.")
        return

    backup_dir = directory / "images_backup"
    backup_dir.mkdir(exist_ok=True)

    moved = 0
    for file in files:
        path = directory / file.name
        is_heic = path.suffix.lower() == ".heic"

        if not is_heic and path.stat().st_size < max_size_kb * 1024:
            print(f"Skipping: {file.name} is already less than {max_size_kb}KB.")
            continue

        try:
            if is_heic:
                img = read_heic_file(path)
            else:
                img = Image.open(path)
        except Exception as e:
            if debug:
                raise
            print(f"Error opening image {file.name}: {e}")
            continue

        if img is None:
            if debug:
                raise RuntimeError(f"Failed to read image {file.name}")
            print(f"Skipping {file.name} due to a read error.")
            continue

        try:
            resized_img = resize_image(img, max_length_px)
        except Exception as e:
            if debug:
                raise
            print(f"Skipping {file.name} due to an error in resizing: {e}")
            continue

        try:
            compressed_img = compress_image(resized_img, max_size_kb, verbose=verbose)
        except Exception as e:
            if debug:
                raise
            print(f"Error compressing image {file.name}: {e}")
            continue

        output_filename = f"{path.stem}-{max_size_kb}.jpg"
        output_path = directory / output_filename

        if output_path.exists():
            print(f"Skipping: {output_path} already exists.")
            continue

        with output_path.open("wb") as f:
            f.write(compressed_img.getvalue())

        size = byte_size(output_path.stat().st_size)
        print(f"Processed: {output_filename} {size}")
        path.rename(backup_dir / file.name)
        moved += 1

    print(f"Moved {moved} image files to {backup_dir}")


def _int_arg(value: str, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def main() -> None:
    """CLI entry point for image batch processor."""
    default_max_dimension = 1_200  # longest side of the image in pixels
    default_max_size = 200  # maximum size of the image in KB
    parser = argparse.ArgumentParser(description="Resize and convert images in the current directory.")
    parser.add_argument("directory", nargs="?", default=".", help="Directory to process (default: current directory)")
    parser.add_argument("-c", "--confirm", action="store_true", help="Confirm processing of files")
    parser.add_argument("-d", "--debug", action="store_true", help="Run in debug mode (raise on errors)")
    parser.add_argument(
        "-s",
        "--max_size",
        nargs="?",
        default=default_max_size,
        help=f"Set the max size of the image in KB (default: {default_max_size}KB)",
    )
    parser.add_argument(
        "-l",
        "--max_length",
        nargs="?",
        default=default_max_dimension,
        help=f"Set the max length of the image (default: {default_max_dimension})",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Show verbose output")
    args = parser.parse_args()

    print('\nimager: If not working please use "magick" utility to convert HEIC to JPG\n')
    print(f"Resize image files in a directory and convert them to JPEGs with a maximum size of {args.max_size}kb.")

    max_size_kb = _int_arg(args.max_size, default_max_size)
    max_length_px = _int_arg(args.max_length, default_max_dimension)

    try:
        process_images(
            Path(args.directory).expanduser().resolve(),
            confirm=args.confirm,
            max_size_kb=max_size_kb,
            max_length_px=max_length_px,
            verbose=args.verbose,
            debug=args.debug,
        )
    except Exception as e:  # pragma: no cover - CLI safety net
        print("An error occurred:", e)
        print("Use -d or --debug to see the full error.")
        if args.debug:
            raise
        return

    if not args.confirm:
        print("Use -c or --confirm to process the files.")


if __name__ == "__main__":
    main()
