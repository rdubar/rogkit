"""
Python interpreter performance benchmarking tool.

Runs numerical, string, and list operations across different Python versions
and generates performance comparison graphs.
"""
from __future__ import print_function
import timeit
import argparse

import subprocess
import platform
import sys
import os
from datetime import datetime
from ..settings import ensure_package_data_dir, package_data_dir


DATA_DIR = package_data_dir


def make_graph():
    """Generate bar graph comparing execution times across platforms and Python versions."""
    try:
        import pandas as pd  # type: ignore
        import matplotlib.pyplot as plt  # type: ignore
    except ImportError as exc:  # pragma: no cover - runtime dep
        missing = " and ".join(module for module in ["pandas", "matplotlib"] if module in str(exc))
        print(
            "❌ Unable to generate graph: optional dependency missing. "
            f"Install {missing or 'pandas and matplotlib'} (e.g. `pip install pandas matplotlib`)."
        )
        return

    # Read the CSV file into a DataFrame
    path = ensure_package_data_dir() / 'speeder.csv'
    df = pd.read_csv(path)

    # Set the figure size
    plt.figure(figsize=(10, 6))

    # Group by platform and Python version, then calculate the mean execution time
    grouped_data = df.groupby(['Platform', 'Python Version'])['Execution Time'].mean().unstack()

    # Plot the grouped data as a bar graph
    grouped_data.plot(kind='bar', ax=plt.gca())

    # Set the title and labels
    plt.title('Execution Time Comparison Across Platforms and Python Versions')
    plt.xlabel('Platform')
    plt.ylabel('Execution Time (seconds)')
    plt.xticks(rotation=45, ha='right')

    # Show the plot
    plt.tight_layout()
    plt.legend(title='Python Version')
    plt.show()


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

def run_benchmark(n=500):
    """Run all tests n times and print the total execution time."""
    arch = platform.machine()
    interpreter = sys.version
    tests = [numerical_operations, string_manipulations, list_operations]
    start_time = timeit.default_timer()
    for _ in range(n):
        for test in tests:
            test()
    end_time = timeit.default_timer()
    total_time = end_time - start_time
    print("{} {}".format(arch, total_time))

def find_python_interpreters(all_interpreters=False):
    """
    Find Python interpreters available in the system PATH.

    Args:
        all_interpreters: If True, search all Python executables in PATH.
                         If False, return predefined list.

    Returns:
        list of str: Paths to the found Python interpreter executables.
    """
    if not all_interpreters:
        return [ 'python2.7', 'python3.11', 'python3.12'][::-1]
    # else find all python executables in the PATH
    python_executables = []

    # Split the PATH environment variable to get a list of directories to search
    path_dirs = os.getenv('PATH').split(os.pathsep)

    for dir_path in path_dirs:
        # Ensure the directory exists and is accessible
        if os.path.exists(dir_path) and os.path.isdir(dir_path):
            # List all files in the directory
            for item in os.listdir(dir_path):
                item_path = os.path.join(dir_path, item)
                # Check if the item is a Python executable
                if 'python' in item.lower() and os.access(item_path, os.X_OK):
                    python_executables.append(item_path)

    return python_executables

def run_speed_test(interpreter, test_script='run_benchmark'):
    """
    Run speed test on specified Python interpreter.
    
    Args:
        interpreter: Path to Python interpreter
        test_script: Name of test script to run
        
    Returns:
        Tuple of (success: bool, result: bytes or None)
    """
    # Example test script execution
    command = [interpreter, __file__, '--mode', 'test']
    start_time = datetime.now()
    try:
        result = subprocess.check_output(command)
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        return True, result
    except subprocess.CalledProcessError as e:
        print("Error running test on {}: {}".format(interpreter, str(e)))
        return False, None
    except FileNotFoundError:
        print("Interpreter not found: {}".format(interpreter))
        return False, None
    

def main():
    """CLI entry point for Python interpreter benchmarking."""
    parser = argparse.ArgumentParser(description='Run speed tests on Python interpreters.')
    parser.add_argument('--test', '-t', action='store_true', help='Run the speed tests.')
    parser.add_argument('--output', '-o', type=str, default='results.txt', help='Output file for test results.')
    parser.add_argument('--mode', help='Mode in which to run the script. Use "test" to run in test mode.')
    parser.add_argument('--graph', '-g', action='store_true', help='Generate a graph from the results.')
    args = parser.parse_args()
    
    if args.mode == 'test':
        run_benchmark()
        exit(0)
        
    if args.graph:
        make_graph()
        exit(0)

    if args.test:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        arch = platform.machine()
        sys_interpreter = sys.executable
        print("Python version: ", sys.version)
        print("System architecture: ", arch)
        
        interpreters = ['python2.7', 'python3.11', 'python3.12']
        for interpreter in interpreters:
            success, result = run_speed_test(interpreter)
            if result:
                arch, time = result.decode('utf-8').strip().split(' ')
                print('{:<20} {:<10} {}'.format(interpreter, arch, time))
            else:
                print("Speed test on {} failed.".format(interpreter))
    else:
        print("This program runs speed tests on Python interpreters. Use --help for more options.")

if __name__ == '__main__':
    main()
