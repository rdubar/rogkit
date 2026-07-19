"""
ASCII art text generator using pyfiglet.

Creates colorized ASCII art banners from text input with
customizable fonts, colors, and layouts.
"""
import argparse

import pyfiglet  # type: ignore

try:  # optional rich formatting
    from rich.console import Console
    from rich.text import Text

    console = Console()
    RICH_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover
    console = None
    RICH_AVAILABLE = False


def _print_message(message: str, *, style: str | None = None, plain: bool = False) -> None:
    """Print with optional rich styling, fallback to plain print."""
    if RICH_AVAILABLE and not plain:
        console.print(Text(message, style=style) if style else message)
    else:
        print(message)


def generate_ascii_art(
    text: str,
    color: str = "white",
    font: str = "standard",
    horizontal_layout: str = "default",
    vertical_layout: str = "default",
    width: int = 80,
) -> str:
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

    return figlet.renderText(text)


def main() -> None:
    """CLI entry point for ASCII art generator."""
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
    parser.add_argument(
        "-p", "--plain",
        action="store_true",
        help="Plain text output (no rich styling).",
    )

    args = parser.parse_args()

    # Handle --list-fonts
    if args.list_fonts:
        fonts = pyfiglet.FigletFont.getFonts()
        _print_message("Available fonts:", plain=args.plain)
        for font in fonts:
            _print_message(font, plain=args.plain)
        exit(0)

    # Check if text is provided
    if not args.text:
        _print_message("No text provided. Use --list-fonts to see available fonts.", plain=args.plain)
        exit(0)

    # Join the text into a single string (to handle spaces)
    text = " ".join(args.text)

    # Generate and print ASCII art
    try:
        ascii_art = generate_ascii_art(
            text,
            color=args.color,
            font=args.font,
            horizontal_layout=args.horizontal_layout,
            vertical_layout=args.vertical_layout,
            width=args.width,
        )
        _print_message(ascii_art, style=args.color, plain=args.plain)
    except pyfiglet.FontNotFound:
        _print_message(f"Error: Font '{args.font}' not found. Use --list-fonts to see available fonts.", style="red", plain=args.plain)
    except pyfiglet.LayoutError:
        _print_message("Error: Invalid layout configuration.", style="red", plain=args.plain)
    except pyfiglet.SizeError:
        _print_message("Error: Invalid width configuration.", style="red", plain=args.plain)
    except Exception as e:
        _print_message(f"An error occurred: {e}", style="red", plain=args.plain)


if __name__ == "__main__":
    main()
