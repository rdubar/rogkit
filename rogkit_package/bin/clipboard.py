#!/usr/bin/env python3
"""
Clipboard utility for copying text.

Simple wrapper around pyclip for cross-platform clipboard operations.
"""
import sys

# Optional import - gracefully handle if pyclip is not available
try:
    import pyclip  # type: ignore
    PYCLIP_AVAILABLE = True
except ImportError:
    PYCLIP_AVAILABLE = False


def _clipboard_setup_hint() -> str:
    """Return a platform-specific hint for setting up clipboard support."""
    if sys.platform == "linux":
        return "Install wl-clipboard on Wayland, or xclip/xsel on X11."
    return "Install a system clipboard backend supported by pyclip."


def copy_to_clipboard(text: str, verbose: bool = True) -> bool:
    """
    Copy text to system clipboard.
    
    Args:
        text: Text to copy
        verbose: Show detailed error messages if True
        
    Note:
        Requires pyclip to be installed. If not available, prints a message instead.
    """
    if not PYCLIP_AVAILABLE:
        if verbose:
            print("Clipboard functionality not available (pyclip not installed).")
            print(f"Text to copy: {text}")
        return False
    
    try:
        pyclip.copy(text)
        if verbose:
            print("Copied to clipboard.")
        return True
    except Exception as e:
        if verbose:
            print(f"Error copying to clipboard: {e}")
            print(_clipboard_setup_hint())
        else:
            print(f"Could not copy to clipboard. {_clipboard_setup_hint()}")
        return False


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for clipboard utility."""
    if argv is None:
        argv = sys.argv[1:]

    if not PYCLIP_AVAILABLE:
        print("Error: pyclip is not installed")
        print("Install with: uv sync --group cli")
        return 1
    
    # join all text in args
    if not argv:
        print("Usage: clip.py <text>\nCopy <text> to clipboard.")
        return 1
    text = ' '.join(argv)
    return 0 if copy_to_clipboard(text) else 1

if __name__ == '__main__':
    raise SystemExit(main())
