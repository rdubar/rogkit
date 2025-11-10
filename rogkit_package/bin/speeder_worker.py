# -*- coding: utf-8 -*-
"""Legacy benchmark worker for `speeder.py`.

This module contains a minimal copy of the benchmark routines so that older
Python interpreters (e.g. Python 2.7) can execute the performance tests even
when the main `speeder.py` script requires newer syntax.
"""
from __future__ import print_function

import argparse
import platform
import timeit


def numerical_operations():
    """Perform numerical operations."""
    for _ in range(10000):
        _ = 3.1415 * 2 ** 8 / 100.0


def string_manipulations():
    """Perform string manipulations."""
    for _ in range(5000):
        sentence = "The quick brown fox jumps over the lazy dog"
        _ = sentence.replace("fox", "cat").upper().split()


def list_operations():
    """Perform list operations."""
    for _ in range(5000):
        numbers = list(range(100))
        numbers.append(200)
        numbers.pop(0)
        numbers.sort(reverse=True)


def run_benchmark(iterations):
    """Run all tests `iterations` times and print the total execution time."""
    arch = platform.machine()
    tests = [numerical_operations, string_manipulations, list_operations]
    start_time = timeit.default_timer()
    for _ in range(iterations):
        for test in tests:
            test()
    total_time = timeit.default_timer() - start_time
    print("{} {}".format(arch, total_time))


def main():
    parser = argparse.ArgumentParser(description="Legacy benchmark worker for speeder.")
    parser.add_argument(
        "--mode",
        help='Mode in which to run the script. Use "test" to run the benchmark.',
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run the benchmark (alias for --mode test).",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=500,
        help="Number of iterations to execute per benchmark.",
    )
    args = parser.parse_args()

    if args.test or args.mode == "test":
        run_benchmark(args.iterations)
        return

    print(
        "Legacy speeder worker ready. Use --test or --mode test to run benchmarks.",
    )


if __name__ == "__main__":
    main()

