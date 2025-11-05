# System Info.py
from __future__ import print_function
import sys
import platform
import subprocess
import argparse
import time
import math

"""
Device/Platform	    Python Version	Architecture	        Execution Mode	    Approx iters/sec
MacBook Pro (M3)	3.12.11	        ARM64 (Apple Silicon)	Native	            6,863,741
MacBook Pro (M3)	2.7.18	        x86_64 (Intel)	        Rosetta (Emulated)	2,749,383
Raspberry Pi 5	    3.13.0	        aarch64 (Arm64)	        Native	            2,081,838
"""

def get_arch_cmd():
    try:
        process = subprocess.Popen(['arch'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, _ = process.communicate()
        if sys.version_info[0] >= 3 and isinstance(stdout, bytes):
            return stdout.strip().decode('utf-8')
        return stdout.strip()
    except Exception:
        return "Unknown"

def main():
    args = parse_args()
    print("="*40)
    print("  Python System Information Report")
    print("="*40)
    print("Python Version      :", platform.python_version())
    print("Python Executable   :", sys.executable)
    print("Implementation      :", platform.python_implementation())
    print("Operating System    :", platform.system(), platform.release())
    print("Platform            :", sys.platform)
    print("Machine             :", platform.machine())
    print("Processor           :", platform.processor())
    arch_bits, arch_link = platform.architecture()
    print("Platform Architecture:", arch_bits, "-", arch_link)
    arch_cmd = get_arch_cmd()
    print("System Architecture via 'arch':", arch_cmd)
    if arch_cmd == 'i386':
        friendly_arch = "Intel 32-bit (possibly under Rosetta 2)"
    elif arch_cmd == 'x86_64':
        friendly_arch = "Intel 64-bit"
    elif arch_cmd == 'arm64':
        friendly_arch = "Apple Silicon (ARM 64-bit)"
    else:
        friendly_arch = "Unknown Architecture"
    print("Human-Friendly Architecture:", friendly_arch)
    print("="*40)

    if args.bench:
        print("Simple CPU Benchmark")
        print("-"*40)
        run_benchmark(args.bench_seconds)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Python system info and simple CPU benchmark"
    )
    parser.add_argument(
        "--bench",
        action="store_true",
        help="Run a CPU-bound benchmark after printing system info",
    )
    parser.add_argument(
        "--bench-seconds",
        type=float,
        default=3.0,
        help="Duration in seconds for the benchmark (default: 3.0)",
    )
    return parser.parse_args()


def run_benchmark(duration_seconds):
    # Time-based CPU-bound loop using math operations.
    # Keeps work in Python space to compare interpreters fairly.
    start_time = time.time()
    iterations = 0
    accumulator = 0.0
    block_size = 10000

    # Ensure positive duration; run at least one block
    target = start_time + (duration_seconds if duration_seconds and duration_seconds > 0 else 0.001)

    while True:
        # Execute a block of work to reduce timer overhead
        local_acc = 0.0
        base = iterations
        for i in range(block_size):
            x = float((i + base) % 1000 + 1)
            local_acc += math.sin(x) * math.cos(x) + math.sqrt(x) * math.log(x)
        accumulator += local_acc
        iterations += block_size

        now = time.time()
        if now >= target:
            elapsed = now - start_time
            break

    # Report
    print("Benchmark duration   : {0:.3f} s".format(elapsed))
    print("Iterations           : {0}".format(iterations))
    print("Accumulated result   : {0:.6f}".format(accumulator))
    print("Approx iters/sec     : {0:.0f}".format(iterations / elapsed if elapsed > 0 else 0))
    return iterations, elapsed, accumulator

if __name__ == "__main__":
    main()
