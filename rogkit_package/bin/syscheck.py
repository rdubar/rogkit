"""
System reboot advisor and resource management utility.

Analyzes system metrics (uptime, load, memory, swap) to calculate a reboot score
and provide recommendations. Can optionally free system resources on Linux/macOS.
"""
import argparse
import json
import os
import platform
import re
import shutil
import subprocess
from datetime import timedelta

import psutil
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()


def get_platform():
    """Detect the platform: mac, pi, or linux."""
    system = platform.system().lower()
    if system == "darwin":
        return "mac"
    elif system == "linux":
        return "pi" if "raspberrypi" in platform.uname().release else "linux"
    else:
        return "unknown"

def get_uptime(platform_type):
    """Get system uptime in seconds."""
    if platform_type == "pi" or platform_type == "linux":
        with open('/proc/uptime', 'r') as f:
            return float(f.readline().split()[0])

    elif platform_type == "mac":
        # Run the `uptime` command and get the output
        output = subprocess.check_output(['uptime'], text=True).strip()

        # Regex to extract the uptime part
        # Example input: "14:05  up 3 days,  1:45, 2 users, load averages: 4.41 3.77 3.32"
        match = re.search(r'up\s+(?:(\d+)\s+days?,\s+)?(\d+):(\d+)', output)

        if match:
            # Extract days, hours, and minutes from the regex groups
            days = int(match.group(1)) if match.group(1) else 0
            hours = int(match.group(2))
            minutes = int(match.group(3))

            # Calculate total uptime in seconds
            return days * 86400 + hours * 3600 + minutes * 60

    print(f"Error parsing uptime from `uptime` output: {output}")
    return 0


def get_load_averages(platform_type):
    """Get system load averages."""
    try:
        return os.getloadavg()
    except (AttributeError, OSError):
        return (0.0, 0.0, 0.0)

def get_memory_info(platform_type):
    """Get memory usage information."""
    if platform_type == "pi" or platform_type == "linux":
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()
        return {
            "total_mem": mem.total,
            "used_mem": mem.used,
            "free_mem": mem.available,
            "total_swap": swap.total,
            "used_swap": swap.used,
        }
    elif platform_type == "mac":
        # Prefer psutil on macOS for simplicity and reliability
        try:
            mem = psutil.virtual_memory()
            swap = psutil.swap_memory()
            return {
                "total_mem": mem.total,
                "used_mem": mem.used,
                "free_mem": mem.available,
                "total_swap": swap.total,
                "used_swap": swap.used,
            }
        except Exception as e:
            print(f"Error fetching memory info on macOS: {e}")
            return {
                "total_mem": 0,
                "used_mem": 0,
                "free_mem": 0,
                "total_swap": 0,
                "used_swap": 0,
            }

    print("Unsupported platform for memory info: {platform_type}")
    return {}

def uptime_score(uptime_seconds):
    """
    Calculate scaled uptime score.
    
    Returns up to 25 points based on uptime (maxes out at 30 days).
    """
    days = uptime_seconds / 86400.0
    return min(days, 30.0) / 30.0 * 25.0

def calculate_reboot_need(uptime, load_avg, memory_info, mem_pressure_pct=None):
    """Calculate the percentage need for a reboot (0-100)."""
    score = 0.0

    # Uptime (0–25)
    score += uptime_score(uptime)

    # Load (0–25)
    cores = os.cpu_count() or 1
    load_1, load_5, load_15 = load_avg
    if load_1 > cores:
        score += 15
    elif load_1 > 0.75 * cores:
        score += 10
    if load_5 > cores:
        score += 10

    # Memory (0–30)
    total_mem = max(memory_info.get("total_mem") or 0, 1)
    free_ratio = float(memory_info.get("free_mem", 0)) / total_mem
    if free_ratio < 0.10:
        score += 20
    elif free_ratio < 0.20:
        score += 10

    swap_total = memory_info.get("total_swap", 0)
    swap_used = memory_info.get("used_swap", 0)
    swap_ratio = (float(swap_used) / swap_total) if swap_total else 0.0
    if swap_ratio > 0.25:
        score += 10

    # macOS memory pressure bonus (0–20)
    if mem_pressure_pct is not None:
        if mem_pressure_pct < 10:
            score += 20
        elif mem_pressure_pct < 20:
            score += 10

    return min(int(round(score)), 100)

def verdict_from_score(score):
    """Convert reboot score to verdict message."""
    if score < 30:
        return "\u2705 Optimal"
    if score < 70:
        return "\u26a0\ufe0f Moderate"
    return "\ud83d\udd34 Reboot advised"

def mac_memory_pressure():
    """Return system-wide free memory percentage from memory_pressure -Q on macOS, or None."""
    try:
        out = subprocess.check_output(["memory_pressure", "-Q"], text=True)
        m = re.search(r"free percentage:\s*(\d+)%", out)
        return int(m.group(1)) if m else None
    except Exception:
        return None

def last_boot():
    """Return last boot information string if available."""
    try:
        out = subprocess.check_output(["who", "-b"], text=True).strip()
        return out
    except Exception:
        return None

def format_memory(size_in_bytes):
    """
    Format memory size in bytes to human-readable string.
    
    Returns formatted string with appropriate unit (B, KB, MB, GB, TB).
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_in_bytes < 1024:
            return f"{size_in_bytes:.2f} {unit}"
        size_in_bytes /= 1024

def free_system_resources(platform_type):
    """Attempt to free swap and caches depending on platform."""
    try:
        if platform_type in ["pi", "linux"]:
            # If using zramswap, restart the service instead of generic swapoff
            if os.path.exists("/etc/default/zramswap"):
                console.print("Detected zram. Restarting zramswap service...", style="yellow")
                subprocess.run(["sudo", "systemctl", "restart", "zramswap.service"], check=True)
                console.print("ZRAM swap cleared.", style="green")
            else:
                console.print("Clearing standard swap...", style="yellow")
                subprocess.run(["sudo", "swapoff", "-a"], check=True)
                subprocess.run(["sudo", "swapon", "-a"], check=True)
                console.print("Swap reset complete.", style="green")

            console.print("Dropping disk caches...", style="yellow")
            subprocess.run(["sudo", "sync"])
            subprocess.run(["sudo", "sysctl", "-w", "vm.drop_caches=3"], check=True)
            console.print("Disk caches cleared.", style="green")

        elif platform_type == "mac":
            console.print(
                "macOS manages swap dynamically. Attempting to purge inactive memory...", style="yellow"
            )
            purge_path = shutil.which("purge")
            if purge_path:
                subprocess.run(["sudo", purge_path], check=True)
                console.print("Memory purge requested.", style="green")
            else:
                console.print("The 'purge' command is not available. Try installing Xcode CLI tools.", style="red")
        else:
            console.print("Freeing resources is not supported on this platform.", style="red")
    except Exception as e:
        console.print(f"[red]Error while freeing resources:[/] {e}")


def _verdict_style(score: int) -> str:
    if score < 30:
        return "green"
    if score < 70:
        return "yellow"
    return "red"


def render_report(data: dict) -> None:
    """Pretty-print the system report using Rich."""
    score = data["score"]
    verdict_text = data["verdict"]
    style = _verdict_style(score)

    header = Table.grid(expand=True, padding=(0, 1))
    header.add_column(justify="left", ratio=3)
    header.add_column(justify="right")
    header.add_row(
        Text("Rog's System Reboot Advisor", style="bold cyan"),
        Text(f"Score: {score}%", style=f"bold {style}"),
    )

    console.print(Panel.fit(header, border_style="cyan", padding=(1, 2)))
    console.print()

    metrics = Table(header_style="bold blue", box=box.SIMPLE_HEAVY, expand=False)
    metrics.add_column("Metric", style="bold")
    metrics.add_column("Value", style="white")

    metrics.add_row("Platform", data["platform"].capitalize())
    metrics.add_row("Uptime", str(timedelta(seconds=int(data["uptime_seconds"]))))
    load = data["load"]
    metrics.add_row("Load (1/5/15)", f"{load['1']:.2f} / {load['5']:.2f} / {load['15']:.2f}")

    mem = data["memory"]
    metrics.add_row(
        "Memory",
        f"{format_memory(mem['used_mem'])} used / {format_memory(mem['total_mem'])} total",
    )
    metrics.add_row(
        "Swap",
        f"{format_memory(mem['used_swap'])} used / {format_memory(mem['total_swap'])} total",
    )
    mp = data.get("memory_pressure_free_pct")
    if mp is not None:
        metrics.add_row("Memory pressure (free)", f"{mp}%")

    last_boot_info = data.get("last_boot")
    if last_boot_info:
        metrics.add_row("Last Boot", last_boot_info)

    console.print(metrics)

    subtitle = (
        "Smooth sailing" if score < 30 else "Monitor performance" if score < 70 else "Restart recommended"
    )
    verdict_panel = Panel(
        Text(verdict_text, style=f"bold {style}"),
        title="Verdict",
        border_style=style,
        subtitle=subtitle,
        width=max(len(verdict_text), len(subtitle)) + 10,
    )
    console.print(verdict_panel)

    if score < 30:
        console.print("[green]Your system is running smoothly. No need for a reboot![/]")
    elif score < 70:
        console.print("[yellow]System under some load. Reboot if you notice sluggishness.[/]")
    else:
        console.print("[red]System likely needs a reboot soon for best performance.[/]")

def main():
    """CLI entry point for system reboot advisor."""
    parser = argparse.ArgumentParser(description="System Reboot Advisor")
    parser.add_argument("-f", "--free", action="store_true", help="Free swap and caches if possible")
    parser.add_argument("--confirm", action="store_true", help="Confirm execution of --free actions")
    parser.add_argument("--json", action="store_true", help="Output JSON for automation")
    args = parser.parse_args()

    console.print("[bold cyan]Rog's System Reboot Advisor[/bold cyan]")

    platform_type = get_platform()
    if platform_type == "unknown":
        print("Unsupported platform.")
        return

    if args.free:
        if not args.confirm:
            console.print("Dry run: --free requested. Re-run with --confirm to execute freeing actions.", style="yellow")
        else:
            console.print("\nAttempting to free memory and swap...\n", style="yellow")
            free_system_resources(platform_type)

    # Get system info
    uptime_seconds = get_uptime(platform_type)
    load_avg = get_load_averages(platform_type)
    memory_info = get_memory_info(platform_type)
    mem_pressure_pct = mac_memory_pressure() if platform_type == "mac" else None

    # Calculate reboot need
    reboot_need = calculate_reboot_need(uptime_seconds, load_avg, memory_info, mem_pressure_pct)

    data = {
        "platform": platform_type,
        "uptime_seconds": int(uptime_seconds),
        "load": {"1": load_avg[0], "5": load_avg[1], "15": load_avg[2]},
        "memory": memory_info,
        "memory_pressure_free_pct": mem_pressure_pct,
        "score": reboot_need,
        "verdict": verdict_from_score(reboot_need),
        "last_boot": last_boot(),
    }

    if args.json:
        console.print(json.dumps(data, indent=2))
        return

    render_report(data)

if __name__ == "__main__":
    main()
