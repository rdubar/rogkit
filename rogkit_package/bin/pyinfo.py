"""
Python system information and CPU benchmark utility.

Displays detailed Python and system information including version, architecture,
and platform details. Optionally runs a CPU benchmark to measure performance
across different Python implementations and architectures.

Device/Platform	    Python Version	Architecture	        Execution Mode	    Approx iters/sec
MacBook Pro (M3)	3.12.11	        ARM64 (Apple Silicon)	Native	            6,863,741
MacBook Pro (M3)	2.7.18	        x86_64 (Intel)	        Rosetta (Emulated)	2,749,383
Raspberry Pi 5	    3.13.0	        aarch64 (Arm64)	        Native	            2,081,838
"""
from __future__ import print_function
import argparse
import math
import platform
import subprocess
import sys
import time

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text

    console = Console()
    RICH_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    console = None
    RICH_AVAILABLE = False


def get_arch_cmd():
    """Get system architecture from 'arch' command."""
    try:
        process = subprocess.Popen(['arch'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, _ = process.communicate()
        if sys.version_info[0] >= 3 and isinstance(stdout, bytes):
            return stdout.strip().decode('utf-8')
        return stdout.strip()
    except Exception:
        return "Unknown"

def main():
    """CLI entry point for Python system information tool."""
    args = parse_args()
    info_rows = gather_system_info()
    render_info(info_rows)

    if args.bench:
        iterations, elapsed, accumulator = run_benchmark(args.bench_seconds)
        render_benchmark(iterations, elapsed, accumulator)


def gather_system_info():
    """Collect system info rows."""
    arch_bits, arch_link = platform.architecture()
    arch_cmd = get_arch_cmd()
    friendly_arch = {
        "i386": "Intel 32-bit (possibly under Rosetta 2)",
        "x86_64": "Intel 64-bit",
        "arm64": "Apple Silicon (ARM 64-bit)",
    }.get(arch_cmd, "Unknown Architecture")
    return [
        ("Python Version", platform.python_version()),
        ("Executable", sys.executable),
        ("Implementation", platform.python_implementation()),
        ("Compiler", platform.python_compiler()),
        ("Operating System", f"{platform.system()} {platform.release()}"),
        ("Platform", sys.platform),
        ("Machine", platform.machine()),
        ("Processor", platform.processor()),
        ("Platform Architecture", f"{arch_bits} ({arch_link})"),
        ("System Architecture", arch_cmd),
        ("Human-Friendly Architecture", friendly_arch),
    ]


def render_info(rows):
    """Render system info either via Rich or plain text."""
    if not RICH_AVAILABLE:
        print("=" * 40)
        print("Python System Information Report")
        print("=" * 40)
        for label, value in rows:
            print(f"{label:25}: {value}")
        print("=" * 40)
        return

    header = Text("Python System Information", style="bold cyan")
    console.print(Panel.fit(header, border_style="cyan"))
    table = Table(show_header=False, box=None, pad_edge=False, padding=(0, 1))
    table.add_column(justify="right", style="bold magenta")
    table.add_column(style="white", overflow="fold")
    for label, value in rows:
        table.add_row(f"{label}:", str(value))
    console.print(Panel.fit(table, border_style="blue"))


def render_benchmark(iterations, elapsed, accumulator):
    """Render benchmark results."""
    iters_per_sec = iterations / elapsed if elapsed > 0 else 0
    rows = [
        ("Duration", f"{elapsed:.3f} s"),
        ("Iterations", f"{iterations:,}"),
        ("Accumulated result", f"{accumulator:.6f}"),
        ("Approx iters/sec", f"{iters_per_sec:,.0f}"),
    ]
    if not RICH_AVAILABLE:
        print("Simple CPU Benchmark")
        print("-" * 40)
        for label, value in rows:
            print(f"{label:20}: {value}")
        return

    table = Table(show_header=False, box=None, pad_edge=False)
    table.add_column(justify="right", style="bold yellow")
    table.add_column(style="white")
    for label, value in rows:
        table.add_row(f"{label}:", value)
    console.print(Panel.fit(table, title="CPU Benchmark", border_style="green"))


def parse_args():
    """Parse command-line arguments."""
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
    """
    Run CPU benchmark for specified duration.
    
    Time-based CPU-bound loop using math operations.
    Keeps work in Python space to compare interpreters fairly.
    """
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

    return iterations, elapsed, accumulator

if __name__ == "__main__":
    main()
