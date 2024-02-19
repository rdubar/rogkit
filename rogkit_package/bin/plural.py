#!/usr/bin/env python3
import argparse
import re

def plural(word, count):
    if not word or count == 1:
        return word

    # Handling irregular plural forms and common endings more efficiently
    irregulars = {"day": "days", 'man': 'men', 'woman': 'women', 'child': 'children', 
                  'tooth': 'teeth', 'foot': 'feet', 'mouse': 'mice', 'person': 'people',
                  "sheep": "sheep", "deer": "deer", "fish": "fish", "species": "species"}
    if word.lower() in irregulars:
        return irregulars[word.lower()]

    special_cases = {
        ('y',): lambda w: w[:-1] + 'ies',
        ('o',): lambda w: w + 'es',
        ('f',): lambda w: w[:-1] + 'ves',
        ('fe',): lambda w: w[:-2] + 'ves',
        ('s', 'x', 'z', 'sh', 'ch'): lambda w: w + 'es'
    }
    for endings, rule in special_cases.items():
        if word.endswith(endings):
            return rule(word)
    return word + 's'

def parse_input(input_string):
    """Parse input string to find count and word, regardless of their order."""
    match = re.search(r'(\d+)\s+(\w+)|(\w+)\s+(\d+)', input_string)
    if not match:
        raise ValueError("Input does not match expected format.")
    word = match.group(2) or match.group(3)
    count = int(match.group(1) or match.group(4))
    return word, count

def main():
    parser = argparse.ArgumentParser(description='Pluralize a word based on the count provided.')
    parser.add_argument('input', nargs='?', help='Input string containing a count and a word, in any order.')
    args = parser.parse_args()

    if not args.input:
        input_str = input("Enter a count and a word: ")    
    else:
        input_str = " ".join(args.input)
    word, count = parse_input(input_str)
    print(plural(word, count))

if __name__ == "__main__":
    main()