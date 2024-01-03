#!/usr/bin/env python3
import argparse
import secrets
import string
import sys

def generate_password(length=16, alpha=True, numeric=True, special=True):
    alphabet = ''
    if alpha:
        alphabet += string.ascii_letters
    if numeric:
        alphabet += string.digits
    if special:
        alphabet += string.punctuation
    password = ''.join(secrets.choice(alphabet) for i in range(length))
    return password

def main():
    parser = argparse.ArgumentParser(description='Generate a password.')
    parser.add_argument('-l', '--length', type=int, default=16,
                        help='length of the password')
    parser.add_argument('-a', '--alpha', action='store_true',
                        help='include alphabetic characters')
    parser.add_argument('-n', '--numeric', action='store_true',
                        help='include numeric characters')
    parser.add_argument('-s', '--special', action='store_true',
                        help='include special characters')
    args = parser.parse_args()
    # if no options are given, include all
    if not (args.alpha or args.numeric or args.special):
        args.alpha = args.numeric = args.special = True
    password = generate_password(length=args.length, alpha=args.alpha, numeric=args.numeric, special=args.special)
    print(password)

if __name__ == "__main__":
    main()