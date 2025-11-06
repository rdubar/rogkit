#!/usr/bin/env python3
import argparse
import sys
from typing import Optional

def byte_size(size: int, base: int = 1000, unit: Optional[str] = None) -> str:
    """
    Convert a file size in bytes to a human-readable string.
    
    Args:
        size: The size in bytes (integer)
        base: The base to use for conversion (1000 for SI units, 1024 for binary units)
        unit: Optional. Force a specific unit (e.g., "GB", "MB", "KB", "GiB", "MiB").
              If None, automatically selects the most appropriate unit.
    
    Returns:
        A formatted string with the size and unit (e.g., "4.13 GB", "801.60 MB")
    
    Examples:
        >>> byte_size(1234567890)
        '1.23 GB'
        >>> byte_size(1234567890, unit="MB")
        '1,234.57 MB'
        >>> byte_size(1234567890, base=1024, unit="GiB")
        '1.15 GiB'
    """
    if base not in [1000, 1024]:
        raise ValueError("Base must be 1000 or 1024")

    if base == 1024:
        units = ["bytes", "KiB", "MiB", "GiB", "TiB", "PiB", "EiB", "ZiB", "YiB"]
    else:
        units = ["bytes", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB"]

    try:
        size_int = abs(int(size))  
    except Exception as e:
        raise ValueError(f"Invalid size: {e}") from e

    # If a specific unit is requested, force that unit
    if unit:
        # Normalize the unit name
        unit_upper = unit.upper()
        
        # Map unit names to their power
        unit_map = {
            "BYTES": 0, "B": 0,
            "KB": 1, "KIB": 1,
            "MB": 2, "MIB": 2,
            "GB": 3, "GIB": 3,
            "TB": 4, "TIB": 4,
            "PB": 5, "PIB": 5,
            "EB": 6, "EIB": 6,
            "ZB": 7, "ZIB": 7,
            "YB": 8, "YIB": 8,
        }

        if unit_upper not in unit_map:
            raise ValueError(f"Unknown unit: {unit}. Valid units: {', '.join(unit_map.keys())}")
        power = unit_map[unit_upper]
        divisor = base ** power
        # Use the appropriate unit name based on the base
        if power == 0:
            return f"{size_int} {unit}" if size_int != 1 else "1 byte"

        # Determine proper unit name (KB vs KiB, etc.)
        result_unit = units[power]
        return f"{size_int / divisor:,.2f} {result_unit}"

    # Use float for calculations to avoid type issues
    size_float = float(size_int)
    for unit in units:
        if size_float < base or unit == units[-1]:
            if unit == "bytes":
                return f"{size_int} {unit}" if size_int != 1 else "1 byte"
            else:
                return f"{size_float:,.2f} {unit}"
        size_float /= base

    return f"{size_float:,.2f} {unit}"  # Fallback for very large numbers

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Convert bytes to human-readable format.')
    parser.add_argument('bytes', type=int, nargs='?', help='Number of bytes to convert')
    parser.add_argument('-b', '--base', 
                        type=int, default=1024, choices=[1000, 1024],
                        help='Base to use (1000 or 1024)')

    args = parser.parse_args()

    # Check if the bytes argument was not provided
    if args.bytes is None:
        print('Convert bytes to MB, GB, TB, etc.\nUsage: bytes.py [number of bytes] [-b 1000|1024]')
        sys.exit(1)

    try:
        print(byte_size(args.bytes, base=args.base))
    except ValueError as e:
        print(e)