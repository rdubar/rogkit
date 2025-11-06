"""
PDF creator from images.

Converts a folder of JPG/PNG images into a single PDF document with A4 page size,
automatically rotating landscape images and centering content.
"""
import os
import argparse
from PIL import Image  # type: ignore
from reportlab.pdfgen import canvas  # type: ignore
from reportlab.lib.pagesizes import A4  # type: ignore


def create_pdf_from_images(folder_path, output_pdf):
    """Create PDF from all JPG/PNG images in folder, sorted by name."""
    # Get all .jpg and .png files in the directory in name order
    images = sorted([f for f in os.listdir(folder_path) if f.endswith('.jpg') or f.endswith('.png')])

    c = canvas.Canvas(output_pdf, pagesize=A4)

    for image in images:
        image_path = os.path.join(folder_path, image)
        with Image.open(image_path) as img:
            # Rotate image if it's in landscape
            if img.width > img.height:
                img = img.rotate(270, expand=True)
            
            # Calculate scale to fit A4 (taking into account DPI)
            dpi = img.info.get('dpi', (300, 300))
            scale_x = 595.0 / (img.width * 72 / dpi[0])
            scale_y = 842.0 / (img.height * 72 / dpi[1])
            scale = min(scale_x, scale_y)
            
            # Calculate new dimensions
            new_width = img.width * scale
            new_height = img.height * scale
            
            # Center the image
            x = (595 - new_width * 72 / dpi[0]) / 2
            y = (842 - new_height * 72 / dpi[1]) / 2
            
            # Convert to points
            new_width_pt = new_width * 72 / dpi[0]
            new_height_pt = new_height * 72 / dpi[1]
            
            # Save the possibly rotated and scaled image to a temporary file
            temp_path = "temp_image.jpg"
            img.save(temp_path)
            
            # Draw the image
            c.drawInlineImage(temp_path, x, y, new_width_pt, new_height_pt)
            c.showPage()
            
            # Optionally, remove the temporary file after adding it to the PDF
            os.remove(temp_path)
    c.save()

    print(f'PDF saved to {output_pdf}')

def main():
    """CLI entry point for PDF creator."""
    parser = argparse.ArgumentParser(description="Convert images in a folder to a single PDF document.")
    parser.add_argument("folder", type=str, help="The folder containing images to be converted.")
    args = parser.parse_args()

    folder_path = args.folder
    output_pdf = os.path.join(folder_path, "output.pdf")

    create_pdf_from_images(folder_path, output_pdf)

if __name__ == "__main__":
    main()
