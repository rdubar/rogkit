import os
import argparse
import io
import pyheif
from PIL import Image
from .bytes import byte_size

def list_heic_files(directory):
    """List all HEIC files in the given directory."""
    return [file for file in os.listdir(directory) if file.lower().endswith('.heic')]

def read_heic_file(input_image_path):
    """Read a HEIC file and convert it to a PIL Image object."""
    heif_file = pyheif.read(input_image_path)
    return Image.frombytes(
        heif_file.mode, 
        heif_file.size, 
        heif_file.data,
        "raw",
        heif_file.mode,
        heif_file.stride,
    )

def resize_image(img, max_size):
    """Resize the image to the given maximum size."""
    img.thumbnail((max_size, max_size))
    return img

def compress_image(image):
    """Compress the image to a file size less than 110KB."""
    quality = 85
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=quality)
    while buffer.getbuffer().nbytes > 110000 and quality > 10:
        buffer = io.BytesIO()
        quality -= 5
        image.save(buffer, format="JPEG", quality=quality)
        if quality <= 10:
            break
    return buffer

def process_images(directory, confirm):
    """Process each HEIC file in the directory."""
    files = list_heic_files(directory)
    if not confirm:
        print("Files to be processed:", files)
        return
    
    # create a folder called "heic" in the directory and move all the heic files there (if it doesn't exist)
    heic_folder = os.path.join(directory, "heic")
    if not os.path.exists(heic_folder):
        os.mkdir(heic_folder)

    for file in files:
        path = os.path.join(directory, file)
        img = read_heic_file(path)
        resized_img = resize_image(img, 800)
        compressed_img = compress_image(resized_img)

        output_filename = file.rsplit('.', 1)[0] + ".jpg"
        output_path = os.path.join(directory, output_filename)

        with open(output_path, 'wb') as f:
            f.write(compressed_img.getvalue())

        size = byte_size(os.path.getsize(output_path))
        print(f"Processed: {output_filename} {size}")
        os.rename(path, os.path.join(directory, "heic", file))
    print(f"Moved {len(files)} .heic files to {heic_folder}")

def main():
    """Main function to handle argument parsing."""
    parser = argparse.ArgumentParser(description="Resize and convert HEIC files to JPEG.")
    parser.add_argument("directory", nargs='?', default=".", help="Directory to process (default: current directory)")
    parser.add_argument("-c", "--confirm", action="store_true", help="Confirm processing of files")
    args = parser.parse_args()

    print("Convert all HEIC files in the directory to JPEG.")
    process_images(args.directory, args.confirm)
    if not args.confirm:
        print("Use -c or --confirm to process the files.")

if __name__ == "__main__":
    main()
