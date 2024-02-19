#!/usr/bin/env python3
import argparse
import sys

def byte_size(size: int, base: int = 1000) -> str:
    if base not in [1000, 1024]:
        raise ValueError("Base must be 1000 or 1024")

    if base == 1024:
        units = ["bytes", "KiB", "MiB", "GiB", "TiB", "PiB", "EiB", "ZiB", "YiB"]
    else:
        units = ["bytes", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB"]

    for i, unit in enumerate(units):
        if size < base or unit == units[-1]:
            if unit == "bytes":
                return f"{size} {unit}" if size != 1 else "1 byte"
            else:
                return f"{size:,.2f} {unit}"
        size /= base

    return f"{size:,.2f} {unit}"  # Fallback for very large numbers

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Convert bytes to human-readable format.')
    parser.add_argument('bytes', type=int, nargs='?', help='Number of bytes to convert')  # Use nargs='?' for optional positional argument
    parser.add_argument('-b', '--base', type=int, default=1024, choices=[1000, 1024], help='Base to use (1000 or 1024)')

    args = parser.parse_args()

    # Check if the bytes argument was not provided
    if args.bytes is None:
        print('Convert bytes to MB, GB, TB, etc.\nUsage: bytes.py [number of bytes] [-b 1000|1024]')
        sys.exit(1)

    try:
        print(byte_size(args.bytes, base=args.base))
    except ValueError as e:
        print(e)