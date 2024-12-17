from __future__ import print_function
import timeit
import sys

def numerical_operations():
    """Perform numerical operations."""
    for _ in range(10000):
        x = 3.1415 * 2 ** 8 / 100.0

def string_manipulations():
    """Perform string manipulations."""
    for _ in range(5000):
        s = "The quick brown fox jumps over the lazy dog"
        s = s.replace("fox", "cat").upper().split()

def list_operations():
    """Perform list operations."""
    for _ in range(5000):
        l = [i for i in range(100)]
        l.append(200)
        l.pop(0)
        l.sort(reverse=True)

def run_benchmark(n):
    """Run all tests n times and print the total execution time."""
    tests = [numerical_operations, string_manipulations, list_operations]
    start_time = timeit.default_timer()
    for _ in range(n):
        for test in tests:
            test()
    end_time = timeit.default_timer()
    total_time = end_time - start_time
    print("Total execution time for {} iterations: {:.4f} seconds".format(n, total_time))

if __name__ == "__main__":
    n = 1000
    if len(sys.argv) > 1:
        try:
            n = int(sys.argv[1])
        except ValueError:
            print("Usage: python script.py [n]")
            sys.exit(1)
            
    # print the current version of Python
    print("Python version: ", sys.version)        
    run_benchmark(n)
