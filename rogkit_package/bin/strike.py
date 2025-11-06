#!/usr/bin/env python3
"""
Strikethrough text formatter.

Adds Unicode combining strikethrough characters to text
(e.g., "hello" → "h̶e̶l̶l̶o̶").
"""
import sys


def strikethru(text):
    """Add strikethrough Unicode combining characters to text."""
    return ''.join([f'\u0336{c}' for c in text])


def main():
    """CLI entry point for strikethrough formatter."""
    # join all text in args
    if len(sys.argv) < 2:
        print("Usage: strike.py <text>\nStrikethru <text>.")
        exit(1)
    text = ' '.join(sys.argv[1:])
    text = strikethru(text).strip()
    print(text)

if __name__ == '__main__':
    main()