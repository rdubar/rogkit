import sh
import platform
import argparse


def basic_info():
    """Display basic system information."""
    print("=== System Information ===")
    print(f"OS: {platform.system()} {platform.release()}")
    print(f"Version: {platform.version()}")
    print(f"Machine: {platform.machine()}")

    # Processor details
    if platform.system() == "Linux" and "raspberrypi" in platform.uname().node.lower():
        try:
            with open("/proc/cpuinfo") as f:
                cpu_info = [line.strip() for line in f if line.startswith("Model")]
                if cpu_info:
                    print(f"Processor: {cpu_info[0].split(':', 1)[1].strip()}")
                else:
                    print("Processor information not found i")
        except FileNotFoundError:
            print("Processor information not available: /proc/cpuinfo not found")
    else:
        print(f"Processor: {platform.processor()}")


def cpu_info():
    """Display CPU information."""
    print("\n=== CPU Information ===")
    try:
        if platform.system() == "Linux":
            print(sh.lscpu())
        elif platform.system() == "Darwin":
            print(sh.sysctl("-n", "machdep.cpu.brand_string").strip())
        else:
            print("CPU information not available for this platform.")
    except Exception as e:
        print(f"Error retrieving CPU info: {e}")


def memory_info():
    """Display memory information."""
    print("\n=== Memory Information ===")
    try:
        if platform.system() == "Linux":
            print(sh.free("-h"))
        elif platform.system() == "Darwin":
            print(sh.vm_stat())
        else:
            print("Memory information not available for this platform.")
    except Exception as e:
        print(f"Error retrieving memory info: {e}")


def disk_usage():
    """Display disk usage."""
    print("\n=== Disk Usage ===")
    try:
        print(sh.df("-h"))
    except Exception as e:
        print(f"Error retrieving disk usage info: {e}")


def network_info():
    """Display network interface information."""
    print("\n=== Network Interfaces ===")
    try:
        if platform.system() == "Linux":
            print(sh.ip("a"))
        elif platform.system() == "Darwin":
            print(sh.ifconfig())
        else:
            print("Network interface information not available for this platform.")
    except Exception as e:
        print(f"Error retrieving network info: {e}")


import argparse

def main():
    parser = argparse.ArgumentParser(description="System Information Tool")
    parser.add_argument("-b", "--basic", action="store_true", help="Show basic system information (default)")
    parser.add_argument("-c", "--cpu", action="store_true", help="Show CPU information")
    parser.add_argument("-m", "--memory", action="store_true", help="Show memory information")
    parser.add_argument("-d", "--disk", action="store_true", help="Show disk usage")
    parser.add_argument("-n", "--network", action="store_true", help="Show network interfaces")
    parser.add_argument("-a", "--all", action="store_true", help="Show all information")

    args = parser.parse_args()
    
    basic_info()
    
    if not any(vars(args).values()):
        print("\nUse -h or --help for usage information.")
        return
    
    # Map flags to their respective functions
    options = [
        (args.all or args.cpu, cpu_info),
        (args.all or args.memory, memory_info),
        (args.all or args.disk, disk_usage),
        (args.all or args.network, network_info),
    ]

    # Execute the appropriate functions based on flags
    for condition, function in options:
        if condition:
            function()
    

if __name__ == "__main__":
    main()
    