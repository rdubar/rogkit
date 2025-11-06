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


def copy_to_clipboard(text, verbose=True):
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
            print("⚠️  Clipboard functionality not available (pyclip not installed)")
            print(f"Text to copy: {text}")
        return
    
    try:
        pyclip.copy(text)
        print("✓ Copied to clipboard.")
    except Exception as e:
        if verbose:
            print(f"Error copying to clipboard: {e}")
        else:
            print("Could not copy to clipboard.")

def main():
    """CLI entry point for clipboard utility."""
    if not PYCLIP_AVAILABLE:
        print("❌ Error: pyclip is not installed")
        print("Install with: pip install pyclip")
        exit(1)
    
    # join all text in args
    if len(sys.argv) < 2:
        print("Usage: clip.py <text>\nCopy <text> to clipboard.")
        exit(1)
    text = ' '.join(sys.argv[1:])
    copy_to_clipboard(text)

if __name__ == '__main__':
    main()