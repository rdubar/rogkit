"""
Image transparency utility.

Makes specified colors transparent in images based on hex color and tolerance.
Uses PIL and NumPy for efficient pixel manipulation.
"""
import argparse
from PIL import Image  # type: ignore
import numpy as np  # type: ignore


def hex_to_rgb(hex_color):
    """Convert hex color to an RGB tuple."""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def apply_transparency(image_path, target_hex_color='#FFFFFF', tolerance=8):
    """Apply transparency to colors within tolerance of the target color."""
    # Convert target color to RGB and calculate tolerance threshold
    target_color = hex_to_rgb(target_hex_color)
    img = Image.open(image_path).convert("RGBA")
    data = np.array(img)
    
    # Calculate squared distance for each pixel and the target color
    rgb_data = data[:, :, :3]
    distances = np.sqrt(np.sum((rgb_data - np.array(target_color))**2, axis=2))

    # Calculate max distance based on tolerance (as a percentage of the max possible distance in RGB space)
    max_distance = np.sqrt(3 * (255**2)) * (tolerance / 100.0)
    
    # Identify pixels within the tolerance
    transparency_mask = distances < max_distance
    data[transparency_mask] = [0, 0, 0, 0]  # Set pixels within tolerance to transparent
    
    # Create a new image from the modified data and save it
    new_img = Image.fromarray(data)
    new_image_path = image_path.rsplit('.', 1)[0] + '-transparentify.png'
    new_img.save(new_image_path)
    old_size = img.size / 1024
    new_size = new_img.size / 1024
    pixels_changed = np.sum(transparency_mask)
    print(f"""
Image saved as {new_image_path}
{pixels_changed} pixels made transparent.
Old size: {old_size:.2f} KB
New size: {new_size:.2f} KB
    """)


# Example usage with argparse
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Make a specific color within a given tolerance transparent in an image.")
    parser.add_argument("image_path", type=str, help="Path to the input image.")
    parser.add_argument("-c", "--color", type=str, default="FFFFFF", help="Hex color to make transparent (default: FFFFFF).")
    parser.add_argument("-t", "--tolerance", type=int, default=8, help="Tolerance percentage for color matching (default: 8%%).")
    parser.add_argument('-d', '--debug', action='store_true', help='Print debug information.')
    args = parser.parse_args()
    if args.debug:
        apply_transparency(args.image_path, args.color, args.tolerance)
    else:
        try:
            apply_transparency(args.image_path, args.color, args.tolerance)
        except Exception as e:
            print(e)
