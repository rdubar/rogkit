#!/usr/bin/env python3
"""
Time conversion utilities for seconds to human-readable formats.

Provides functions to convert seconds into readable durations like
"2 hours, 30 minutes" or "02:30:00" format.
"""
import argparse
from datetime import datetime
from .bignum import bignum
from .plural import plural


def hms_string(seconds):
    """Convert seconds into hours, minutes, and seconds."""
    seconds = int(seconds)  # Ensure the input is an integer
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02}:{minutes:02}:{seconds:02}"


def convert_seconds(seconds, long_format=False, show_seconds=True, no_commas=False, bignums=False):
    """Convert seconds into a readable format, with options for long format and showing seconds."""
    if seconds == 0:
        return "0 seconds"

    seconds = abs(int(seconds))

    # Define time units in seconds
    aeon = 31557600000000000  # Assuming an aeon as 1 billion years
    century = 3155760000  # 100 years
    year = 31557600  # 1 year (365.25 days accounting for leap years)
    day = 86400  # 1 day
    hour = 3600  # 1 hour
    minute = 60  # 1 minute

    time_list = []
    if long_format:
        aeons, seconds = divmod(seconds, aeon)
        centuries, seconds = divmod(seconds, century)
        if aeons > 0:
            time_list.append(f"{aeons:,} {plural('aeon', aeons)}")
        if centuries > 0:
            time_list.append(f"{centuries:,} {plural('century', centuries)}")

    years, seconds = divmod(seconds, year)
    days, seconds = divmod(seconds, day)
    hours, seconds = divmod(seconds, hour)
    minutes, seconds = divmod(seconds, minute)

    for unit, name in [(years, 'year'), (days, 'day'), (hours, 'hour'), (minutes, 'minute')]:
        if unit > 0:
            if bignums:
                unit_str = bignum(unit)
            else:
                unit_str = unit if no_commas else f"{unit:,}"
            time_list.append(f"{unit_str} {plural(name, unit)}")
    if show_seconds and seconds > 0:
        time_list.append(f"{seconds} {plural('second', seconds)}")

    if len(time_list) == 0:
        return "0 seconds"
    elif len(time_list) == 1:
        return time_list[0]
    else:
        return ", ".join(time_list[:-1]) + " and " + time_list[-1]

def time_ago_in_words(seconds_ago: int) -> str:
    """
    Convert a time difference in seconds to a human-readable 'time ago' string using existing functionality.

    :param seconds_ago: The time difference in seconds.
    :return: Human-readable string, e.g., '5 minutes ago'.
    """
    if seconds_ago < 0:
        raise ValueError("Time difference cannot be negative.")

    # Use the `convert_seconds` function for conversion
    human_readable = convert_seconds(seconds_ago, long_format=True, show_seconds=True)

    # Append "ago" to the result
    return f"{human_readable} ago"

def main():
    """Main function to parse arguments and print the converted time."""
    parser = argparse.ArgumentParser(description='Convert seconds into more readable formats.')
    parser.add_argument('seconds', type=int, help='Number of seconds to convert')
    parser.add_argument('-c', '--compact', action='store_true', help='Show compact format H:M:S')
    parser.add_argument('-l', '--long', action='store_true', help='Use a long format for time representation')
    parser.add_argument('-n', '--no-commas', action='store_true', help='Do not use commas as a thousands separator')
    parser.add_argument('-b', '--bignum', action='store_true', help='Use a bignum library for large numbers')
    parser.add_argument('-s', '--seconds', action='store_true', help='Show seconds explicitly', dest='show_seconds')
    args = parser.parse_args()

    try:
        if args.compact:
            print(hms_string(args.seconds))
        else:
            print(convert_seconds(
                    args.seconds, 
                    long_format=args.long, 
                    show_seconds=args.show_seconds, 
                    no_commas=args.no_commas,
                    bignums=args.bignum))
    except ValueError as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
