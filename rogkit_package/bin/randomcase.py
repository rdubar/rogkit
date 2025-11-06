#!/usr/bin/env python3
"""
Random case text generator.

Converts text to random case (e.g., "hello" → "HeLLo") and
optionally copies the result to clipboard.
"""
import argparse
import random
from .clipboard import copy_to_clipboard


def randomcase(string):
    """Randomize the case of each character in a string."""
    return ''.join(random.choice([c.upper(), c.lower()]) for c in string)

def main():
    """CLI entry point for random case generator."""
    parser = argparse.ArgumentParser(description='Randomize the case of a string.')
    parser.add_argument('string', nargs='*', type=str, help='string to make random case')
    args = parser.parse_args()

    clipboard = True
    # Join the list of arguments into a single string
    combined_string = ' '.join(args.string)
    if combined_string == '':
        combined_string = 'Please provide a string to randomize.'
        clipboard = False
    print(randomcase(combined_string))
    if clipboard:
        copy_to_clipboard(randomcase(combined_string))

if __name__ == "__main__":
    main()
