# -*- coding: utf-8 -*-
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
import shutil
import glob
import re
from pathlib import Path
from datetime import datetime


PROJECT_ROOT = Path(__file__).resolve().parents[2]

if __package__:
    from ..settings import ensure_package_data_dir, package_data_dir
else:
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    from rogkit_package.settings import ensure_package_data_dir, package_data_dir  # type: ignore[import]


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
            f"Install {missing or 'pandas and matplotlib'} in the rogkit uv environment "
            "(for example `uv sync --group data`)."
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
        _ = 3.1415 * 2 ** 8 / 100.0

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
    tests = [numerical_operations, string_manipulations, list_operations]
    start_time = timeit.default_timer()
    for _ in range(n):
        for test in tests:
            test()
    end_time = timeit.default_timer()
    total_time = end_time - start_time
    print("{} {}".format(arch, total_time))

_PYTHON_EXECUTABLE_PATTERN = re.compile(r"^python(?:(\d+(?:\.\d+)*))?$", re.IGNORECASE)
_PYTHON_VERSION_PATTERN = re.compile(r"Python\s+(\d+(?:\.\d+)*)")
_DEFAULT_CANDIDATE_NAMES = [
    "python",
    "python3",
    "python2",
    "python2.7",
    *[f"python3.{minor}" for minor in range(14, 4, -1)],
]
_COMMON_DIRECTORIES = [
    "/usr/bin",
    "/usr/local/bin",
    "/opt/homebrew/bin",
    "/opt/local/bin",
    "/usr/local/opt/python/bin",
    os.path.expanduser("~/.local/bin"),
]


def _is_python_executable(path, strict_name=True):
    """Return True if path looks like a valid python executable."""
    if not path:
        return False
    expanded = os.path.expanduser(path)
    if not os.path.isfile(expanded):
        return False
    if not os.access(expanded, os.X_OK):
        return False
    if not strict_name:
        return True
    basename = os.path.basename(expanded)
    return bool(_PYTHON_EXECUTABLE_PATTERN.match(basename))


def _collect_from_directory(directory, register):
    try:
        entries = os.listdir(directory)
    except (FileNotFoundError, NotADirectoryError, PermissionError):
        return
    for entry in entries:
        candidate = os.path.join(directory, entry)
        register(candidate, strict_name=True)


def _pyenv_directories():
    pyenv_root = os.getenv("PYENV_ROOT", os.path.expanduser("~/.pyenv"))
    if not os.path.isdir(pyenv_root):
        return []
    dirs = [os.path.join(pyenv_root, "shims")]
    dirs.extend(glob.glob(os.path.join(pyenv_root, "versions", "*", "bin")))
    return dirs


def _asdf_directories():
    asdf_root = os.getenv("ASDF_DATA_DIR", os.path.expanduser("~/.asdf"))
    if not os.path.isdir(asdf_root):
        return []
    return glob.glob(os.path.join(asdf_root, "installs", "python", "*", "bin"))


def find_python_interpreters(all_interpreters=False, extra_paths=None):
    """
    Discover available Python interpreters.

    Args:
        all_interpreters: expand search to every PATH entry in addition to the curated list.
        extra_paths: iterable of interpreter paths or directories to include.
    """

    extra_paths = extra_paths or []
    discovered = []
    seen = set()

    def register(path, strict_name=True):
        expanded = os.path.expanduser(path)
        if os.path.isdir(expanded):
            _collect_from_directory(expanded, register)
            return
        if not _is_python_executable(expanded, strict_name=strict_name):
            return
        normalized = os.path.realpath(expanded)
        if normalized in seen:
            return
        seen.add(normalized)
        discovered.append(normalized)

    # Current interpreter first for determinism
    register(sys.executable, strict_name=False)

    # User-provided paths (allow non-standard names)
    for path in extra_paths:
        register(path, strict_name=False)

    # Known interpreter names resolved via PATH
    for candidate in _DEFAULT_CANDIDATE_NAMES:
        resolved = shutil.which(candidate)
        if resolved:
            register(resolved)

    directories = set(_COMMON_DIRECTORIES)
    directories.add(os.path.dirname(sys.executable))
    directories.update(_pyenv_directories())
    directories.update(_asdf_directories())

    if all_interpreters:
        directories.update(filter(None, os.getenv("PATH", "").split(os.pathsep)))

    for directory in directories:
        register(directory)

    def sort_key(path):
        name = os.path.basename(path)
        match = _PYTHON_EXECUTABLE_PATTERN.match(name)
        version = ()
        if match and match.group(1):
            try:
                version = tuple(int(part) for part in match.group(1).split("."))
            except ValueError:
                version = ()
        return (version, path)

    return sorted(discovered, key=sort_key, reverse=True)


def _build_subprocess_env():
    env = os.environ.copy()
    project_path = str(PROJECT_ROOT)
    existing = env.get("PYTHONPATH", "")
    paths = existing.split(os.pathsep) if existing else []
    if project_path not in paths:
        env["PYTHONPATH"] = project_path if not existing else project_path + os.pathsep + existing
    return env


def run_speed_test(interpreter, use_worker=False):
    """
    Run speed test on specified Python interpreter.
    
    Args:
        interpreter: Path to Python interpreter
        use_worker: Whether to run the legacy worker module.
        
    Returns:
        Tuple of (success: bool, result: bytes or None)
    """
    if use_worker:
        command = [interpreter, '-m', 'rogkit_package.bin.speeder_worker', '--mode', 'test']
    else:
        command = [interpreter, __file__, '--mode', 'test']
    env = _build_subprocess_env()
    try:
        result = subprocess.check_output(command, env=env)
        return True, result
    except subprocess.CalledProcessError as e:
        print("Error running test on {}: {}".format(interpreter, str(e)))
        return False, None
    except FileNotFoundError:
        print("Interpreter not found: {}".format(interpreter))
        return False, None


def probe_interpreter(interpreter):
    """
    Return (version_tuple, description) for an interpreter.

    version_tuple is a tuple of ints (major, minor, micro, ...) or None if parsing fails.
    description is the stdout/stderr from `python --version` (or 'unknown version').
    """
    try:
        output = subprocess.check_output(
            [interpreter, "--version"], stderr=subprocess.STDOUT, text=True
        )
    except (subprocess.SubprocessError, OSError):
        return None, "unknown version"

    description = output.strip()
    match = _PYTHON_VERSION_PATTERN.search(description)
    if not match:
        return None, description

    try:
        version_tuple = tuple(int(part) for part in match.group(1).split("."))
    except ValueError:
        version_tuple = None
    return version_tuple, description
    

def main():
    """CLI entry point for Python interpreter benchmarking."""
    parser = argparse.ArgumentParser(description='Run speed tests on Python interpreters.')
    parser.add_argument('--test', '-t', action='store_true', help='Run the speed tests.')
    parser.add_argument('--output', '-o', type=str, default='results.txt', help='Output file for test results.')
    parser.add_argument('--mode', help='Mode in which to run the script. Use "test" to run in test mode.')
    parser.add_argument('--graph', '-g', action='store_true', help='Generate a graph from the results.')
    parser.add_argument(
        '--all-interpreters',
        action='store_true',
        help='Scan every PATH entry for python executables in addition to common locations.',
    )
    parser.add_argument(
        '--interpreter',
        '-i',
        action='append',
        dest='interpreters',
        default=[],
        help='Add an interpreter executable or directory to include in the test run. Can be specified multiple times.',
    )
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
        print("Benchmark timestamp:", timestamp)
        print("Primary interpreter:", sys_interpreter)
        
        interpreters = find_python_interpreters(args.all_interpreters, args.interpreters)

        if not interpreters:
            print("No Python interpreters discovered. Provide a path with --interpreter.")
            exit(1)

        print("Discovered interpreters:")
        usable = []
        for interpreter in interpreters:
            version_info, description = probe_interpreter(interpreter)
            print("  {:<40} {}".format(interpreter, description))
            if version_info is None:
                print("    Skipping: unable to determine version.")
                continue
            if version_info < (2, 7):
                print("    Skipping: requires Python 2.7+.")
                continue
            use_worker = version_info < (3, 6)
            if use_worker:
                print("    Using legacy worker.")
            usable.append((interpreter, use_worker))

        if not usable:
            print("No compatible interpreters (requires Python 2.7+ with legacy worker support).")
            exit(1)

        for interpreter, use_worker in usable:
            _, result = run_speed_test(interpreter, use_worker=use_worker)
            if result:
                decoded = result.decode('utf-8').strip()
                parts = decoded.split(None, 1)
                if len(parts) == 2:
                    arch, time = parts
                else:
                    arch, time = "unknown", decoded
                label = " (worker)" if use_worker else ""
                print('{:<20} {:<10} {}{}'.format(interpreter, arch, time, label))
            else:
                print("Speed test on {} failed.".format(interpreter))
    else:
        print("This program runs speed tests on Python interpreters. Use --help for more options.")

if __name__ == '__main__':
    main()
