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
    if platform.system() == "Linux" and "raspberrypi" in platform.uname().nodename.lower():
        try:
            with open("/proc/cpuinfo") as f:
                cpu_info = [line.strip() for line in f if line.startswith("Model")]
                if cpu_info:
                    print(f"Processor: {cpu_info[0].split(':', 1)[1].strip()}")
                else:
                    print("Processor information not found in /proc/cpuinfo")
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


def main():
    parser = argparse.ArgumentParser(description="System Information Tool")
    parser.add_argument(
        "-b", "--basic", action="store_true", help="Show basic system information (default)"
    )
    parser.add_argument(
        "-c", "--cpu", action="store_true", help="Show CPU information"
    )
    parser.add_argument(
        "-m", "--memory", action="store_true", help="Show memory information"
    )
    parser.add_argument(
        "-d", "--disk", action="store_true", help="Show disk usage"
    )
    parser.add_argument(
        "-n", "--network", action="store_true", help="Show network interfaces"
    )
    
    args = parser.parse_args()

    # Default behavior: Show basic info if no options are provided
    if not any(vars(args).values()):
        basic_info()
        print("\nUse -h or --help for usage information.")
    else:
        if args.basic:
            basic_info()
        if args.cpu:
            cpu_info()
        if args.memory:
            memory_info()
        if args.disk:
            disk_usage()
        if args.network:
            network_info()


if __name__ == "__main__":
    main()