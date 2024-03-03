import argparse
from PIL import Image
import numpy as np

def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def color_distance(c1, c2):
    return sum((a-b)**2 for a, b in zip(c1, c2))**0.5

def transparentify(image_path, hex_color='#FFFFFF', tolerance=8):
    # Convert hex color to RGB and calculate tolerance
    target_color = hex_to_rgb(hex_color)
    tolerance = (255 * tolerance / 100)**2  # Square of Euclidean distance

    # Load the image
    img = Image.open(image_path)
    img = img.convert("RGBA")  # Ensure image is in RGBA format

    # Convert image to NumPy array for processing
    data = np.array(img)

    # Prepare target color for broadcasting
    target_color_array = np.array(target_color)[None, None, :]

    # Calculate squared distances from the target color
    distances = np.sum((data[...,:3] - target_color_array)**2, axis=-1)

    # Find pixels to make transparent
    areas_to_make_transparent = distances < tolerance
    data[areas_to_make_transparent, 3] = 0  # Set alpha to 0 where condition is True

    # Convert back to an image
    img = Image.fromarray(data)
    
    # Save the modified image
    new_image_path = image_path.rsplit('.', 1)[0] + '-transparentify.png'
    img.save(new_image_path)
    print(f"Image saved as {new_image_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Make a specified color in an image transparent.')
    parser.add_argument('image_path', type=str, help='Path to the input image.')
    parser.add_argument('-c', '--color', type=str, default='FFFFFF', help='Color to make transparent in hex (default: FFFFFF).')
    parser.add_argument('-t', '--tolerance', type=int, default=8, help='Tolerance percentage for color matching (default: 8%).')
    parser.add_argument('-d', '--debug', action='store_true', help='Print debug information.')

    args = parser.parse_args()
    if args.debug:
        transparentify(args.image_path, args.color, args.tolerance)
    else:
        try:
            transparentify(args.image_path, args.color, args.tolerance)
        except Exception as e:
            print(e)
        