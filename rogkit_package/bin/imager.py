import os
import argparse
import io
import pyheif
from PIL import Image
from .bytes import byte_size
import subprocess

def list_image_files(directory):
    """List all HEIC, webp, jpg and jpeg files in the given directory."""
    try:
        return [file for file in os.listdir(directory) if file.lower().endswith(('.heic', '.webp', '.jpg', '.jpeg'))]
    except Exception as e:
        print(f"Error listing files in {directory}: {e}")
        exit(1)

def convert_heic_to_jpg(input_image_path, output_image_path):
    """Convert HEIC to JPG using ImageMagick."""
    try:
        subprocess.run(["magick", "convert", input_image_path, output_image_path], check=True)
        return Image.open(output_image_path)
    except Exception as e:
        print(f"Error converting HEIC to JPG with ImageMagick: {e}")
        return None

def read_heic_file(input_image_path):
    """Read a HEIC file and convert it to a PIL Image object."""
    try:
        heif_file = pyheif.read(input_image_path)
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
        # Fallback to ImageMagick conversion if pyheif fails
        output_image_path = input_image_path.rsplit('.', 1)[0] + ".jpg"
        return convert_heic_to_jpg(input_image_path, output_image_path)

def resize_image(img, max_size):
    """Resize the image to the given maximum size."""
    try:
        max_size = int(max_size)
        if hasattr(img, 'thumbnail'):
            img.thumbnail((max_size, max_size))
        return img
    except Exception as e:
        print(f"Error resizing image: {e}")
        exit(1)

def compress_image(image, max_size, verbose=False):
    """Compress the image to a file size less than max_size."""
    max_size *= 1024  # Convert max_size from kilobytes to bytes
    quality = 85
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=quality)
    if verbose:
        print(f"Initial Quality: {quality}, Size: {buffer.getbuffer().nbytes / 1024:.2f} KB")
    
    while quality > 10:
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=quality)
        current_size = buffer.getbuffer().nbytes
        if verbose:
            print(f"Adjusted Quality: {quality}, Size: {current_size / 1024:.2f} KB")
        if current_size <= max_size:
            break  # Exit the loop if the current size is less than or equal to the max size
        quality -= 5

    return buffer

def process_images(directory, confirm=False, max_size=110, max_length=800, verbose=False, debug=False):
    """Process each image file in the directory."""
    files = list_image_files(directory)
    if confirm and not files:
        print("No image files found in the directory.")
        return
    if not confirm:
        print("Files to be processed:", files)
        return
    
    images_backup = "images_backup"
    images_backup_folder = os.path.join(directory, images_backup)
    if not os.path.exists(images_backup_folder):
        os.mkdir(images_backup_folder)

    moved = 0
    for file in files:
        path = os.path.join(directory, file)
        is_heic = file.lower().endswith('.heic')

        if not is_heic and os.path.getsize(path) < max_size * 1024:
            print(f'Skipping: {file} is already less than {max_size}KB.')
            continue

        if is_heic:
            img = read_heic_file(path)
            if img is None and not debug:
                print(f"Skipping {file} due to a read error.")
                continue
        else:
            try:
                img = Image.open(path)
            except Exception as e:
                print(f"Error opening image {file}: {e}")
                continue

        resized_img = resize_image(img, max_length)
        if resized_img is None:
            print(f"Skipping {file} due to an error in resizing.")
            continue

        try:
            compressed_img = compress_image(resized_img, max_size, verbose=verbose)
        except Exception as e:
            print(f"Error compressing image: {e}")
            continue

        output_filename = file.rsplit('.', 1)[0] + f"-{max_size}.jpg"
        output_path = os.path.join(directory, output_filename)

        if os.path.exists(output_path):
            print(f'Skipping: {output_path} already exists.')
            continue

        with open(output_path, 'wb') as f:
            f.write(compressed_img.getvalue())

        size = byte_size(os.path.getsize(output_path))
        print(f"Processed: {output_filename} {size}")
        os.rename(path, os.path.join(directory, images_backup, file))
        moved += 1
    
    print(f"Moved {moved} image files to {images_backup_folder}")

def main():
    default_max_dimension = 1_200  # longest side of the image in pixels
    default_max_size = 200  # maximum size of the image in KiloBytes
    """Main function to handle argument parsing."""
    parser = argparse.ArgumentParser(description="Resize and convert images in the current directory.")
    parser.add_argument("directory", nargs='?', default=".", help="Directory to process (default: current directory)")
    parser.add_argument("-c", "--confirm", action="store_true", help="Confirm processing of files")
    parser.add_argument("-d", "--debug", action="store_true", help="Run in debug mode (show full errors)")
    parser.add_argument("-s", "--max_size", nargs='?', default=default_max_size, 
                        help=f"Set the max size of the image in KB (default: {default_max_size}KB)")
    parser.add_argument("-l", "--max_length", nargs='?', default=default_max_dimension, 
                        help=f"Set the max length of the image (default: {default_max_dimension})")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show verbose output")
    args = parser.parse_args()

    print('\nimager: If not working please use "magick" utility to convert HEIC to JPG\n')

    print(f"Resize image files in a directory and convert them to JPEGs with a maximum size of {args.max_size}kb.")
    if args.debug:
        print("Debug mode enabled.")
        process_images(args.directory, 
                    confirm=args.confirm, 
                    max_size=args.max_size, 
                    max_length=args.max_length, 
                    verbose=args.verbose,
                    debug=args.debug)
    else:
        try:
            process_images(args.directory, 
                        confirm=args.confirm, 
                        max_size=args.max_size, 
                        max_length=args.max_length, 
                        verbose=args.verbose)
        except Exception as e:
            print("An error occurred:", e)
            print("Use -d or --debug to see the full error.")
            exit(1)
    if not args.confirm:
        print("Use -c or --confirm to process the files.")

if __name__ == "__main__":
    main()
