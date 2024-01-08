#!/usr/bin/env python3
import argparse
import random
from clipboard import copy_to_clipboard

def randomcase(string):
    return ''.join(random.choice([c.upper(), c.lower()]) for c in string)

def main():
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
