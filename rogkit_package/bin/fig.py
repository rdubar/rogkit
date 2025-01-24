import argparse

import pyfiglet
from colorama import Fore, init

# Initialize colorama
init(autoreset=True)


def generate_ascii_art(
    text, color="white", font="standard", horizontal_layout="default", vertical_layout="default", width=80
):
    """
    Generate ASCII art from text with additional customization options.

    Args:
        text (str): The text to convert into ASCII art.
        color (str): The color of the ASCII art. Options: "blue", "red", "green", "yellow", "white".
        font (str): The font to use for ASCII art. Default is "standard".
        horizontal_layout (str): The horizontal layout of the text. Options: "default", "fitted", "full", "kerned", "controlled-smushing".
        vertical_layout (str): The vertical layout of the text. Options: "default", "fitted", "controlled-smushing".
        width (int): The maximum width of the ASCII art. Default is 80.

    Returns:
        str: The colored ASCII art string.
    """
    # Create a Figlet object with the specified font and width
    figlet = pyfiglet.Figlet(font=font, width=width)

    # Adjust horizontal and vertical layout if applicable
    if horizontal_layout != "default":
        figlet.horizontalLayout = horizontal_layout
    if vertical_layout != "default":
        figlet.verticalLayout = vertical_layout

    # Generate ASCII art
    ascii_art = figlet.renderText(text)

    # Map color names to colorama color codes
    color_map = {
        "blue": Fore.BLUE,
        "red": Fore.RED,
        "green": Fore.GREEN,
        "yellow": Fore.YELLOW,
        "white": Fore.WHITE,
    }
    selected_color = color_map.get(color.lower(), Fore.WHITE)

    # Return the colored ASCII art
    return selected_color + ascii_art


def main():
    parser = argparse.ArgumentParser(description="Generate ASCII art from text")
    parser.add_argument(
        "text",
        type=str,
        nargs="*",  # Accept zero or more words
        help="Text to convert into ASCII art (default: None)",
    )
    parser.add_argument(
        "-c", "--color",
        type=str,
        choices=["blue", "red", "green", "yellow", "white"],
        default="white",
        help="Color of the text (default: white)",
    )
    parser.add_argument(
        "-f", "--font",
        type=str,
        default="standard",
        help="Font to use for ASCII art (default: standard). Use --list-fonts to see all available fonts.",
    )
    parser.add_argument(
        "-hor", "--horizontal-layout",
        type=str,
        choices=["default", "fitted", "full", "kerned", "controlled-smushing"],
        default="default",
        help="Horizontal layout of the text (default: default).",
    )
    parser.add_argument(
        "-ver", "--vertical-layout",
        type=str,
        choices=["default", "fitted", "controlled-smushing"],
        default="default",
        help="Vertical layout of the text (default: default).",
    )
    parser.add_argument(
        "-w", "--width",
        type=int,
        default=80,
        help="Maximum width of the ASCII art (default: 80).",
    )
    parser.add_argument(
        "-l", "--list-fonts",
        action="store_true",
        help="List all available fonts and exit.",
    )

    args = parser.parse_args()

    # Handle --list-fonts
    if args.list_fonts:
        fonts = pyfiglet.FigletFont.getFonts()
        print("Available fonts:")
        for font in fonts:
            print(font)
        exit(0)

    # Check if text is provided
    if not args.text:
        print("No text provided. Use --list-fonts to see available fonts.")
        exit(0)

    # Join the text into a single string (to handle spaces)
    text = " ".join(args.text)

    # Generate and print ASCII art
    ascii_art = generate_ascii_art(
        text,
        color=args.color,
        font=args.font,
        horizontal_layout=args.horizontal_layout,
        vertical_layout=args.vertical_layout,
        width=args.width,
    )
    print(ascii_art)



if __name__ == "__main__":
    main()