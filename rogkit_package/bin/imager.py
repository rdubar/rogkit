import os
import argparse
import io
import pyheif
from PIL import Image
from .bytes import byte_size

def list_image_files(directory):
    """List all HEIC, webp, jpg and jpeg files in the given directory."""
    return [file for file in os.listdir(directory) if file.lower().endswith(('.heic', '.webp', '.jpg', '.jpeg'))]

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

def compress_image(image, max_size):
    """Compress the image to a file size less than 110KB."""
    quality = 85
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=quality)
    while buffer.getbuffer().nbytes > max_size and quality > 10:
        buffer = io.BytesIO()
        quality -= 5
        image.save(buffer, format="JPEG", quality=quality)
    return buffer

def process_images(directory, confirm, max_size):
    """Process each image file in the directory."""
    files = list_image_files(directory)
    if not confirm:
        print("Files to be processed:", files)
        return
    
    # create a folder called "images_backup" in the directory and move all the heic files there (if it doesn't exist)
    images_backup = "images_backup"
    images_backup_folder = os.path.join(directory, images_backup)
    if not os.path.exists(images_backup_folder):
        os.mkdir(images_backup_folder)

    for file in files:
        path = os.path.join(directory, file)
        if file.lower().endswith('.heic'):
            img = read_heic_file(path)
        else:
            img = Image.open(path)
        resized_img = resize_image(img, 800)
        compressed_img = compress_image(resized_img, max_size)

        output_filename = file.rsplit('.', 1)[0] + "-imager.jpg"
        output_path = os.path.join(directory, output_filename)

        with open(output_path, 'wb') as f:
            f.write(compressed_img.getvalue())

        size = byte_size(os.path.getsize(output_path))
        print(f"Processed: {output_filename} {size}")
        os.rename(path, os.path.join(directory, images_backup, file))
    print(f"Moved {len(files)} image files to {images_backup_folder}")

def main():
    """Main function to handle argument parsing."""
    parser = argparse.ArgumentParser(description="Resize and convert HEIC files to JPEG.")
    parser.add_argument("directory", nargs='?', default=".", help="Directory to process (default: current directory)")
    parser.add_argument("-c", "--confirm", action="store_true", help="Confirm processing of files")
    parser.add_argument("-d", "--debug", action="store_true", help="Run in debug mode (show full errors)")
    parse_args = parser.add_argument("-s", "--size", nargs='?', default=110, help="Set the max size of the image in KB (default: 110KB)")
    args = parser.parse_args()

    print("Resize image files in a directory and convert them to JPEG.")
    if args.debug:
        print("Debug mode enabled.")
        process_images(args.directory, args.confirm, args.size)
    else:
        try:
            process_images(args.directory, args.confirm, args.size)
        except Exception as e:
            print("An error occurred:", e)
            print("Use -d or --debug to see the full error.")
            exit(1)
    if not args.confirm:
        print("Use -c or --confirm to process the files.")

if __name__ == "__main__":
    main()