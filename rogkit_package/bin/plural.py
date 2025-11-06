#!/usr/bin/env python3
"""
Pluralizer CLI Tool

This script pluralizes English words based on a numerical count. It supports both
regular and irregular pluralization rules, and attempts to intelligently handle
common plural forms and exceptions.

Usage:
    plural.py "2 cat"
    plural.py cat 2
    plural.py giraffe
    plural.py

    If no argument is provided, the program will prompt for input interactively.
    If only a word is provided (e.g., "giraffe"), a default count of 2 is assumed.
    The script avoids re-pluralizing words that already appear to be plural.

Pluralization rules include:
    - Irregular forms (e.g., "man" → "men")
    - Special endings (e.g., "baby" → "babies", "box" → "boxes", "leaf" → "leaves")
    - Invariant nouns (e.g., "sheep" stays "sheep")
    - Exceptions for words ending in "f" or "fe" that take a regular "s" (e.g., "giraffe" → "giraffes")

Intended as a simple utility for command-line environments.
"""
import argparse
import re


def looks_plural(word):
    """Check if a word already appears to be plural."""
    return (
        word.lower() in {
            'men', 'women', 'children', 'teeth', 'feet', 'mice', 'people',
            'sheep', 'deer', 'fish', 'species'
        } or
        re.search(r'(ies|ves|ches|shes|xes|zes|s)$', word.lower()) is not None
    )

def plural(word, count=2):
    """
    Pluralize a word based on count.
    
    Args:
        word: The word to pluralize
        count: Number of items (default: 2). Returns singular if count is 1
        
    Returns:
        Pluralized word or original if count is 1
    """
    if not word or count == 1:
        return word
    
    if looks_plural(word):
        return word

    irregulars = {
        "day": "days", 'man': 'men', 'woman': 'women', 'child': 'children', 
        'tooth': 'teeth', 'foot': 'feet', 'mouse': 'mice', 'person': 'people',
        "sheep": "sheep", "deer": "deer", "fish": "fish", "species": "species"
    }

    if word.lower() in irregulars:
        return irregulars[word.lower()]

    # Words ending in 'f' or 'fe' that take regular 's' plural
    f_exceptions = {'roof', 'belief', 'chef', 'chief', 'giraffe'}

    # Pluralization rules
    if word.lower() in f_exceptions:
        return word + 's'
    elif word.endswith('fe'):
        return word[:-2] + 'ves'
    elif word.endswith('f'):
        return word[:-1] + 'ves'
    elif word.endswith(('s', 'x', 'z', 'sh', 'ch')):
        return word + 'es'
    elif word.endswith('y') and word[-2].lower() not in 'aeiou':
        return word[:-1] + 'ies'
    elif word.endswith('o'):
        return word + 'es'
    else:
        return word + 's'

def parse_input(input_string):
    """
    Parse input string to find count and word, regardless of order.
    
    Supports formats: "2 cat", "cat 2", or just "cat" (assumes count of 2)
    """
    match = re.search(r'(\d+)\s+(\w+)|(\w+)\s+(\d+)', input_string)
    if match:
        word = match.group(2) or match.group(3)
        count = int(match.group(1) or match.group(4))
        return word, count

    # Try just a word (e.g. "sheep") – assume count of 2
    if re.match(r'^\w+$', input_string.strip()):
        return input_string.strip(), 2

    raise ValueError("Input does not match expected format.")

def main():
    """CLI entry point for pluralization utility."""
    parser = argparse.ArgumentParser(description='Pluralize a word based on the count provided.')
    parser.add_argument('input', nargs=argparse.REMAINDER, help='Count and word, e.g., "2 cat" or "cat 2"')
    args = parser.parse_args()

    if not args.input:
        input_str = input("Enter a count and a word (e.g., '3 cat' or 'cat 3'): ")
    else:
        input_str = " ".join(args.input)

    try:
        word, count = parse_input(input_str)
        print(plural(word, count=count))
    except ValueError as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()