"""
Decimal rounding utility that minimizes trailing zeros.

Rounds numbers to a maximum number of decimal places while
removing unnecessary trailing zeros.
"""
import sys


def round_decimals(value, max_decimals):
    """
    Round a number to max decimals, removing trailing zeros.
    
    Args:
        value: Number to round
        max_decimals: Maximum decimal places
        
    Returns:
        String representation with minimal decimals
    """
    if value == int(value):
        return str(int(value))
    else:
        format_string = "{:." + str(max_decimals) + "f}"
        formatted_value = format_string.format(value)
        while formatted_value[-1] == "0":
            formatted_value = formatted_value[:-1]
        return formatted_value


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: minidec <value> <max_decimals>\nMinimize the number of decimals in a number.")
        sys.exit(1)
    
    value = float(sys.argv[1])
    max_decimals = int(sys.argv[2]) if len(sys.argv) > 2 else 2

    print(round_decimals(value, max_decimals))