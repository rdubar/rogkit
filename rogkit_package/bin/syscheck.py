import os
import re
import platform
import subprocess
import psutil
from datetime import timedelta
import argparse
import shutil


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
    return os.getloadavg()

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
        try:
            # Get `vm_stat` output
            output = subprocess.check_output(['vm_stat'], text=True).strip().splitlines()
            for line in output[:5]:  # Only show the first 5 lines for context
                print(f"  {line}")

            # Extract the page size
            page_size_line = output[0]
            match = re.search(r'page size of (\d+) bytes', page_size_line)
            if not match:
                raise ValueError(f"Unable to parse page size from vm_stat output: {page_size_line}")
            page_size = int(match.group(1))

            # Parse memory stats from the rest of the output
            stats = {}
            for line in output[1:]:
                key, value = line.split(':')
                stats[key.strip()] = int(value.strip().replace('.', ''))

            # Calculate memory usage
            total_mem = (stats["Pages free"] + stats["Pages active"] +
                         stats["Pages inactive"] + stats["Pages speculative"]) * page_size
            used_mem = (stats["Pages active"] + stats["Pages speculative"]) * page_size
            free_mem = stats["Pages free"] * page_size

            # Get swap memory from psutil
            swap = psutil.swap_memory()

            return {
                "total_mem": total_mem,
                "used_mem": used_mem,
                "free_mem": free_mem,
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

def calculate_reboot_need(uptime, load_avg, memory_info):
    """Calculate the percentage need for a reboot."""
    reboot_score = 0

    # Uptime contribution
    if uptime > 60 * 60 * 24 * 7:  # More than 7 days
        reboot_score += 20
    if uptime > 60 * 60 * 24 * 30:  # More than 30 days
        reboot_score += 30

    # Load average contribution
    cores = os.cpu_count()
    load_1, load_5, load_15 = load_avg
    if load_1 > cores * 0.75:
        reboot_score += 20
    if load_5 > cores:
        reboot_score += 20

    # Memory contribution
    free_mem = memory_info["free_mem"] / memory_info["total_mem"]
    if free_mem < 0.2:  # Less than 20% free memory
        reboot_score += 20

    # Swap usage contribution
    swap_used = memory_info["used_swap"] / memory_info["total_swap"] if memory_info["total_swap"] > 0 else 0
    if swap_used > 0.5:  # More than 50% swap usage
        reboot_score += 10

    return min(reboot_score, 100)

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
            print("Clearing swap...")
            subprocess.run(["sudo", "swapoff", "-a"], check=True)
            subprocess.run(["sudo", "swapon", "-a"], check=True)
            print("Swap reset complete.")

            print("Dropping caches...")
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
                print("The 'purge' command is not available. You may need to install Xcode command line tools.")
        else:
            print("Freeing resources is not supported on this platform.")
    except Exception as e:
        print(f"Error while freeing resources: {e}")

def main():
    parser = argparse.ArgumentParser(description="System Reboot Advisor")
    parser.add_argument("-f", "--free", action="store_true", help="Free swap and caches if possible")
    args = parser.parse_args()
    
    print("Rog's System Reboot Advisor")
    
    platform_type = get_platform()
    if platform_type == "unknown":
        print("Unsupported platform.")
        return
    
    if args.free:
        print("\nAttempting to free memory and swap...\n")
        free_system_resources(platform_type)

    # Get system info
    uptime_seconds = get_uptime(platform_type)
    load_avg = get_load_averages(platform_type)
    memory_info = get_memory_info(platform_type)

    # Calculate reboot need
    reboot_need = calculate_reboot_need(uptime_seconds, load_avg, memory_info)

    # Format and display system info
    print("\n--- System Reboot Advisor ---")
    print(f"Platform: {platform_type.capitalize()}")
    print(f"Uptime: {timedelta(seconds=int(uptime_seconds))}")
    print(f"Load Averages (1, 5, 15 min): {load_avg[0]:.2f}, {load_avg[1]:.2f}, {load_avg[2]:.2f}")
    print(f"Memory: {format_memory(memory_info['used_mem'])} used / {format_memory(memory_info['total_mem'])} total")
    print(f"Swap: {format_memory(memory_info['used_swap'])} used / {format_memory(memory_info['total_swap'])} total")
    print(f"Reboot Need: {reboot_need}%")
    
    # Fun message
    if reboot_need < 30:
        print("Your system is running smoothly. No need for a reboot!")
    elif reboot_need < 70:
        print("Your system is under some load. Consider a reboot if performance is sluggish.")
    else:
        print("Your system might need a reboot soon. Performance could improve!")

if __name__ == "__main__":
    main()