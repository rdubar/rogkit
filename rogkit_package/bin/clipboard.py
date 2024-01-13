#!/usr/bin/env python3
import sys
import pyclip

def copy_to_clipboard(text, verbose=True):
    try:
        pyclip.copy(text)
        print("Copied to clipboard.")
    except Exception as e:
        if verbose:
            print(f"Error copying to clipboard: {e}")
        else:
            print("Could not copy to clipboard.")

def main():
    # join all text in args
    if len(sys.argv) < 2:
        print("Usage: clip.py <text>\nCopy <text> to clipboard.")
        exit(1)
    text = ' '.join(sys.argv[1:])
    copy_to_clipboard(text)

if __name__ == '__main__':
    main()