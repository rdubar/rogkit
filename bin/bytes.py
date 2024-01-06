#!/usr/bin/env python3
import sys

def byte_size(size, base=1024):
    if base not in [1000, 1024]:
        raise ValueError("Base must be 1000 or 1024")

    units = ["bytes", "KB", "MB", "GB", "TB", "PB"]
    for unit in units:
        if size < base or unit == units[-1]:  # Stop at the last unit (PB)
            return f"{size:,.2f} {unit}"
        size /= base

if __name__ == "__main__":
    if len(sys.argv) > 1:
        try:
            input_bytes = int(sys.argv[1])
            base = 1024
            if len(sys.argv) > 2:
                base = int(sys.argv[2])
            print(byte_size(input_bytes, base=base))
        except ValueError as e:
            print(e)
    else:
        print("Usage: bytes.py [number of bytes] [base (optional, 1000 or 1024)]")
