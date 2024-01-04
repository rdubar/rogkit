#!/usr/bin/env python3
import argparse
import random

def randomcase(string):
    return ''.join(random.choice([c.upper(), c.lower()]) for c in string)

def main():
    parser = argparse.ArgumentParser(description='Randomize the case of a string.')
    parser.add_argument('string', nargs='*', type=str, help='string to randomize')
    args = parser.parse_args()

    # Join the list of arguments into a single string
    combined_string = ' '.join(args.string)
    if combined_string == '':
        combined_string = 'Please provide a string to randomize.'
    print(randomcase(combined_string))

if __name__ == "__main__":
    main()
