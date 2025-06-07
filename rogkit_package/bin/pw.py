#!/usr/bin/env python3
import argparse
import secrets
import string
import math
from dataclasses import dataclass
from .bignum import bignum, seconds_time
from .clipboard import copy_to_clipboard

@dataclass
class PasswordGenerator:
    length: int = 16
    alpha: bool = True
    numeric: bool = True
    special: bool = True
    dashes: bool = False
    password: str = None
    check: bool = False
    info: bool = False
    max_length: int = 1_000_000

    def __post_init__(self):
        self.alphabet = self._create_alphabet()

    def _create_alphabet(self):
        alphabet_set = set()
        if self.alpha:
            alphabet_set.update(string.ascii_letters)
        if self.numeric:
            alphabet_set.update(string.digits)
        if self.special:
            alphabet_set.update(string.punctuation)
        if self.dashes:
            alphabet_set.update('-_')
        
        return ''.join(alphabet_set)
        
    def generate_password(self):
        try:
            self.password = ''.join(secrets.choice(self.alphabet) for _ in range(self.length))
        except Exception as e:
            print(f"Error generating password: {e}")
            exit(1)

    def generate_and_store_password(self):
        if self.length < 1:
            print("Password length must be greater than 0.")
            exit(1)
        if self.length > self.max_length:
            print(f"Maximum password length is {self.max_length}.")
            exit(1)
        while True:
            self.generate_password()
            if self.check:
                if not self.check_password():
                    continue
            break
        return self.password
    
    def check_password(self, minimum_length=6):
        if minimum_length and self.length < minimum_length:
            print(f"Password length must be at least {minimum_length} characters for unique character checks.")
            return True
        if not any(c in self.password for c in string.ascii_lowercase):
            return False
        if not any(c in self.password for c in string.ascii_uppercase):
            return False
        if not any(c in self.password for c in string.digits):
            return False
        if not any(c in self.password for c in string.punctuation):
            return False
        return True
    

    def calculate_combinations(self):
        return len(self.alphabet) ** self.length

    def estimate_crack_time(self, guesses_per_second):
        combinations = self.calculate_combinations()
        
        if guesses_per_second <= 0:
            return "Infinity (error: Invalid guesses per second)"
        
        try:
            if combinations > 10**18:  # Arbitrary threshold for large numbers
                # Avoid floating-point overflow by using logarithms
                seconds_log = math.log(combinations) - math.log(guesses_per_second)
                seconds = math.exp(seconds_log)
            else:
                seconds = combinations // guesses_per_second  # Integer division
        except Exception as e:
            return f"Infinity (error: {e})"
        
        return self._format_time(seconds)

    def _format_time(self, seconds):
        return seconds_time(seconds)

    def copy_to_clipboard(self):
        if self.password is not None:
            copy_to_clipboard(self.password)
        else:
            print("No password generated to copy.")

    def display_password_info(self, guesses_per_second, size_limit=500):
        try:
            if self.password is not None:   
                print(self.password)
                if self.info:
                    print(f'Length: {bignum(self.length)}')
                    if self.length >= size_limit:
                        print(f'Password length of {self.length} is too large to calculate combinations.')
                    else:
                        print(f'Combinations: {bignum(self.calculate_combinations())}')
                        print(f"Estimated max time to crack: {self.estimate_crack_time(guesses_per_second)}")
                        print(f'Assumes {bignum(guesses_per_second)} guesses per second.')
                    if self.check:
                        print("Password contains special, numeric, lower and upper case characters.")
            else:
                print("No password generated.")
        except Exception as e:
            print(f"Error displaying password info: {e}")

def main():
    
    default_length = 20
    
    parser = argparse.ArgumentParser(description='Generate a password.')
    # Basic password composition options
    parser.add_argument('-l', '--length', type=int, default=default_length, help=f'Length of the password (default: {default_length})')
    parser.add_argument('-a', '--alpha', action='store_true', help='Include alphabetic characters')
    parser.add_argument('-n', '--numeric', action='store_true', help='Include numeric characters')
    parser.add_argument('-s', '--special', action='store_true', help='Include special characters')
    parser.add_argument('-d', '--dashes', action='store_true', help='Include dashes (-_)')
    parser.add_argument('-e', '--everything', action='store_true', help='Include every character type')
    # Password analysis and constraints
    parser.add_argument('-c', '--check', action='store_true', help='If length > 6, check password for required character types')
    parser.add_argument('-g', '--guesses', type=int, default=1e12, help='Guesses per second for crack time estimation')
    parser.add_argument('-m', '--max_length', type=int, default=1e12, help='Set maximum password length')
    # Additional information
    parser.add_argument('-i', '--info', action='store_true', help='Show information about the password')
    args = parser.parse_args()

    if args.everything:
        args.alpha = args.numeric = args.special = args.check = True
        args.dashes = False
    # if no character type options are given, use these defaults
    elif not (args.alpha or args.numeric or args.special or args.dashes):
        args.alpha = args.numeric = args.dashes = args.check = True

    password_generator = PasswordGenerator(
        length=args.length, 
        alpha=args.alpha, 
        numeric=args.numeric, 
        special=args.special,
        dashes=args.dashes,
        check=args.check,
        info=args.info,
        max_length=args.max_length
    )

    password_generator.generate_and_store_password()
    password_generator.display_password_info(args.guesses)
    password_generator.copy_to_clipboard()

if __name__ == "__main__":
    main()
