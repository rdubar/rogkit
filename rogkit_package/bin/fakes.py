#!/usr/bin/env python3
"""
Fake data generator using Faker library.

Generates realistic fake data (names, addresses, sentences, phone numbers)
for testing and development purposes. Automatically copies output to clipboard.
"""
from typing import Optional
import argparse
from faker import Faker
from .clipboard import copy_to_clipboard


def fake_data(mode: Optional[str] = None) -> str:
    """Generate fake data based on mode (name, address, sentence, phone, text)."""
    fake = Faker()

    match mode:
        case 'name':
            return fake.name()
        case 'address':
            return fake.address()
        case 'sentence':
            return fake.sentence()
        case 'phone':
            return fake.phone_number()
        case _:
            return fake.text()

def main():
    """CLI entry point for fake data generator."""
    parser = argparse.ArgumentParser(description='Generate fake data.')
    parser.add_argument('mode', nargs='?', help='Type of data to generate (name, address, sentence, phone).', default='text')
    parser.add_argument('-l', '--list', action='store_true', help='List available modes.')
    parser.add_argument('-n',"--number", type=int, default=1, help='Number of items to generate.')
    args = parser.parse_args()

    if args.list:
        print('name\naddress\nsentence\nphone\ntext')
        return
    
    for i in range(args.number):
        result = fake_data(args.mode)
        print(result)
    copy_to_clipboard(result)

if __name__ == "__main__":
    main()
