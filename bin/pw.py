#!/usr/bin/env python3
import argparse
import secrets
import string
from dataclasses import dataclass
from bignum import bignum, seconds_time
import pyperclip

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

    def __post_init__(self):
        self.alphabet = self._create_alphabet()

    def _create_alphabet(self):
        alphabet = []
        if self.alpha:
            alphabet.append(string.ascii_letters)
        if self.numeric:
            alphabet.append(string.digits)
        if self.special:
            alphabet.append(string.punctuation)
        if self.dashes:
            alphabet.append('-_')
        return ''.join(set(''.join(alphabet)))

    def generate_and_store_password(self):
        if self.length < 1:
            print("Password length must be greater than 0.")
            exit(1)
        if self.length > 1000:
            print("Maxium password length is 1000.")
            exit(1)
        while True:
            self.password = ''.join(secrets.choice(self.alphabet) for _ in range(self.length))
            if self.check:
                if not self.check_password():
                    continue
            break
        return self.password
    
    def check_password(self):
        if self.length < 6:
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
        try:
            seconds = combinations / guesses_per_second
        except:
            return "Infinity"
        return self._format_time(seconds)

    def _format_time(self, seconds):
        # Assuming this function formats the time in a human-readable way
        # Placeholder implementation here

        return seconds_time(seconds)

    def copy_to_clipboard(self):
        if self.password is not None:
            try:
                pyperclip.copy(self.password)
                print("Password copied to clipboard.")
            except Exception as e:
                print(f"Error copying to clipboard: {e}")
        else:
            print("No password generated to copy.")

    def display_password_info(self, guesses_per_second):
        try:
            if self.password is not None:   
                print(self.password)
                if self.info:
                    print(f'Length: {bignum(self.length)}')
                    if self.length < 200:
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
    parser = argparse.ArgumentParser(description='Generate a password.')
    parser.add_argument('-l', '--length', type=int, default=20, help='Length of the password')
    parser.add_argument('-a', '--alpha', action='store_true', help='Include alphabetic characters')
    parser.add_argument('-n', '--numeric', action='store_true', help='Include numeric characters')
    parser.add_argument('-s', '--special', action='store_true', help='Include special characters')
    parser.add_argument('-d', '--dashes', action='store_true', help='Include dashes')
    parser.add_argument('-i', '--info', action='store_true', help='Show information about the password')
    parser.add_argument('-g', '--guesses', type=int, default=1e12, help='Guesses per second for crack time estimation')
    parser.add_argument('-c', '--check', action='store_true', help='If length > 6, check password for required character types')
    args = parser.parse_args()

    # if no character type options are given, include all
    if not (args.alpha or args.numeric or args.special or args.dashes):
        args.alpha = args.numeric = args.dashes = args.check = True

    password_generator = PasswordGenerator(
        length=args.length, 
        alpha=args.alpha, 
        numeric=args.numeric, 
        special=args.special,
        dashes=args.dashes,
        check=args.check,
        info=args.info
    )

    password_generator.generate_and_store_password()
    password_generator.display_password_info(args.guesses)
    password_generator.copy_to_clipboard()

if __name__ == "__main__":
    main()
