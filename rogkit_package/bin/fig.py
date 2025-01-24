import pyfiglet
from colorama import Fore, init

# Initialize colorama
init(autoreset=True)

def generate_ascii_art(text, color="white"):
    """
    Generate ASCII art from text with optional color.

    Args:
        text (str): The text to convert into ASCII art.
        color (str): The color of the ASCII art (default: "white").
                    Valid colors are "blue", "red", "green", "yellow", and "white".

    Returns:
        str: The colored ASCII art string.
    """
    # Generate ASCII art
    ascii_art = pyfiglet.figlet_format(text)

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
    import argparse

    parser = argparse.ArgumentParser(description="Generate ASCII art from text")
    parser.add_argument("text", type=str, help="Text to convert into ASCII art")
    parser.add_argument(
        "--color",
        type=str,
        choices=["blue", "red", "green", "yellow", "white"],
        default="white",
        help="Color of the text (default: white)",
    )
    args = parser.parse_args()

    # Generate and print ASCII art
    ascii_art = generate_ascii_art(args.text, args.color)
    print(ascii_art)


if __name__ == "__main__":
    main()