#!/usr/bin/env python3
"""
Secure password generator with strength analysis.

Generates cryptographically secure passwords with customizable character sets,
checks password strength, estimates crack time, and copies to clipboard.
"""
import argparse
import secrets
import string
import math
from dataclasses import dataclass

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .bignum import bignum, seconds_time
from .clipboard import copy_to_clipboard

console = Console()


@dataclass
class PasswordGenerator:
    """
    Password generator with strength analysis and crack time estimation.
    
    Attributes:
        length: Password length (default: 16)
        alpha: Include alphabetic characters
        numeric: Include numeric characters
        special: Include special/punctuation characters
        dashes: Include dashes and underscores
        password: Generated password
        check: Enforce character type requirements
        info: Display detailed password information
        max_length: Maximum allowed password length
    """
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
        """Build character alphabet from selected character type options."""
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
        """Generate a random password using cryptographically secure random choices."""
        try:
            self.password = ''.join(secrets.choice(self.alphabet) for _ in range(self.length))
        except Exception as e:
            console.print(f"[bold red]Error generating password:[/] {e}")
            raise SystemExit(1)

    def generate_and_store_password(self):
        """
        Generate password and regenerate if it fails validation checks.
        
        Returns:
            The generated password string
        """
        if self.length < 1:
            console.print("[bold red]Password length must be greater than 0.[/]")
            raise SystemExit(1)
        if self.length > self.max_length:
            console.print(f"[bold red]Maximum password length is {self.max_length}.[/]")
            raise SystemExit(1)
        while True:
            self.generate_password()
            if self.check:
                if not self.check_password():
                    continue
            break
        return self.password
    
    def check_password(self, minimum_length=6):
        """
        Validate password contains all required character types.
        
        Args:
            minimum_length: Minimum length for validation (default: 6)
            
        Returns:
            True if password contains lowercase, uppercase, digit, and punctuation
        """
        if minimum_length and self.length < minimum_length:
            console.print(
                f"[yellow]Password length must be at least {minimum_length} characters for unique character checks.[/]"
            )
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
        """Calculate total possible password combinations."""
        return len(self.alphabet) ** self.length

    def estimate_crack_time(self, guesses_per_second):
        """
        Estimate maximum time to crack password via brute force.
        
        Args:
            guesses_per_second: Assumed attack speed
            
        Returns:
            Human-readable time estimate
        """
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
        """Format seconds into human-readable time string."""
        return seconds_time(seconds)

    def copy_to_clipboard(self):
        """Copy generated password to system clipboard."""
        if self.password is not None:
            copy_to_clipboard(self.password, verbose=False)
            console.print("[green]Password copied to clipboard.[/]")
        else:
            console.print("[yellow]No password generated to copy.[/]")

    def display_password_info(self, guesses_per_second, size_limit=500):
        """
        Display password and optional strength analysis information.
        
        Args:
            guesses_per_second: Attack speed for crack time estimation
            size_limit: Skip calculations for passwords longer than this
        """
        try:
            if self.password is not None:
                console.print(
                    Panel.fit(
                        f"[bold yellow]{self.password}[/]",
                        title="Generated Password",
                        border_style="green",
                    )
                )
                if self.info:
                    table = Table(show_header=False, box=box.MINIMAL_DOUBLE_HEAD)
                    table.add_column("Metric", style="cyan")
                    table.add_column("Value", style="bold white")
                    table.add_row("Length", str(bignum(self.length)))
                    if self.length >= size_limit:
                        table.add_row(
                            "Combinations",
                            f"[yellow]Password length of {self.length} too large to calculate.[/]",
                        )
                    else:
                        table.add_row("Combinations", str(bignum(self.calculate_combinations())))
                        table.add_row(
                            "Crack time",
                            self.estimate_crack_time(guesses_per_second) or "instant",
                        )
                        table.add_row("Assumes", f"{bignum(guesses_per_second)} guesses/sec")
                    console.print(table)
                    if self.check:
                        console.print(
                            "[green]✔ Password includes lower, upper, digit, and punctuation characters.[/]"
                        )
            else:
                console.print("[yellow]No password generated.[/]")
        except Exception as e:
            console.print(f"[bold red]Error displaying password info:[/] {e}")

def main():
    """CLI entry point for password generator."""
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
