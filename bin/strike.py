#!/usr/bin/env python3
import sys

def strikethru(text):
    # use ansi to strikethru text
    return ''.join([f'\u0336{c}' for c in text])

def main():
    # join all text in args
    if len(sys.argv) < 2:
        print("Usage: strike.py <text>\Strikethru <text>.")
        exit(1)
    text = ' '.join(sys.argv[1:])
    text = strikethru(text).strip()
    print(text)

if __name__ == '__main__':
    main()