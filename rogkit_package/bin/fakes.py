#!/usr/bin/env python3
from typing import Optional
import argparse
from faker import Faker
from .clipboard import copy_to_clipboard

def fake_data(mode: Optional[str] = None) -> str:
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
