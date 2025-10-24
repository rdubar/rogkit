import os
import re
import platform
import subprocess
import psutil
from datetime import timedelta
import argparse
import shutil
import json


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
    """Scaled uptime score: up to 25 points over 30 days."""
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
    """Format memory size in bytes to a human-readable string."""
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
                print("Detected zram. Restarting zramswap service...")
                subprocess.run(["sudo", "systemctl", "restart", "zramswap.service"], check=True)
                print("ZRAM swap cleared.")
            else:
                print("Clearing standard swap...")
                subprocess.run(["sudo", "swapoff", "-a"], check=True)
                subprocess.run(["sudo", "swapon", "-a"], check=True)
                print("Swap reset complete.")

            print("Dropping disk caches...")
            subprocess.run(["sudo", "sync"])
            subprocess.run(["sudo", "sysctl", "-w", "vm.drop_caches=3"], check=True)
            print("Disk caches cleared.")

        elif platform_type == "mac":
            print("macOS manages swap dynamically. Attempting to purge inactive memory...")
            purge_path = shutil.which("purge")
            if purge_path:
                subprocess.run(["sudo", purge_path], check=True)
                print("Memory purge requested.")
            else:
                print("The 'purge' command is not available. Try installing Xcode CLI tools.")
        else:
            print("Freeing resources is not supported on this platform.")
    except Exception as e:
        print(f"Error while freeing resources: {e}")

def main():
    parser = argparse.ArgumentParser(description="System Reboot Advisor")
    parser.add_argument("-f", "--free", action="store_true", help="Free swap and caches if possible")
    parser.add_argument("--confirm", action="store_true", help="Confirm execution of --free actions")
    parser.add_argument("--json", action="store_true", help="Output JSON for automation")
    args = parser.parse_args()

    print("Rog's System Reboot Advisor")

    platform_type = get_platform()
    if platform_type == "unknown":
        print("Unsupported platform.")
        return

    if args.free:
        if not args.confirm:
            print("Dry run: --free requested. Re-run with --confirm to execute freeing actions.")
        else:
            print("\nAttempting to free memory and swap...\n")
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
        print(json.dumps(data, indent=2))
        return

    # Format and display system info
    print("\n--- System Reboot Advisor ---")
    print(f"Platform: {platform_type.capitalize()}")
    print(f"Uptime: {timedelta(seconds=int(uptime_seconds))}")
    print(f"Load Averages (1, 5, 15 min): {load_avg[0]:.2f}, {load_avg[1]:.2f}, {load_avg[2]:.2f}")
    print(f"Memory: {format_memory(memory_info['used_mem'])} used / {format_memory(memory_info['total_mem'])} total")
    print(f"Swap: {format_memory(memory_info['used_swap'])} used / {format_memory(memory_info['total_swap'])} total")
    if mem_pressure_pct is not None:
        print(f"Memory pressure free %: {mem_pressure_pct}%")
    lb = data.get("last_boot")
    if lb:
        print(lb)
    print(f"Reboot Need: {reboot_need}%")
    print(f"Verdict: {data['verdict']}")

    # Fun message
    if reboot_need < 30:
        print("Your system is running smoothly. No need for a reboot!")
    elif reboot_need < 70:
        print("Your system is under some load. Consider a reboot if performance is sluggish.")
    else:
        print("Your system might need a reboot soon. Performance could improve!")

if __name__ == "__main__":
    main()
