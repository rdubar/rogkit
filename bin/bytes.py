#!/usr/bin/env python3
import argparse

def byte_size(size, base=1024):
    if base not in [1000, 1024]:
        raise ValueError("Base must be 1000 or 1024")

    units = ["bytes", "KB", "MB", "GB", "TB", "PB"]
    for unit in units:
        if size < base or unit == units[-1]:  # Stop at the last unit (PB)
            return f"{size:,.2f} {unit}"
        size /= base

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Convert bytes to human-readable format.')
    parser.add_argument('bytes', type=int, help='Number of bytes to convert')
    parser.add_argument('-b', '--base', type=int, default=1024, choices=[1000, 1024], help='Base to use (1000 or 1024)')

    args = parser.parse_args()

    try:
        print(byte_size(args.bytes, base=args.base))
    except ValueError as e:
        print(e)
