#!/usr/bin/env python3
import argparse
from .bignum import bignum
from .plural import plural



def convert_seconds(seconds, long_format=False, show_seconds=True):
    """Convert seconds into a readable format, with options for long format and showing seconds."""
    if seconds == 0:
        return "0 seconds"

    seconds = int(seconds)

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
            time_list.append(f"{unit:,} {plural(name, unit)}")
    if show_seconds and seconds > 0:
        time_list.append(f"{seconds} {plural('second', seconds)}")

    return ", ".join(time_list[:-1]) + " and " + time_list[-1] if time_list else "0 seconds"

def main():
    """Main function to parse arguments and print the converted time."""
    parser = argparse.ArgumentParser(description='Convert seconds into more readable formats.')
    parser.add_argument('seconds', type=int, help='Number of seconds to convert')
    parser.add_argument('-l', '--long', action='store_true', help='Use a long format for time representation')
    parser.add_argument('-s', '--seconds', action='store_true', help='Show seconds explicitly', dest='show_seconds')
    args = parser.parse_args()

    try:
        print(convert_seconds(args.seconds, long_format=args.long, show_seconds=args.show_seconds))
    except ValueError as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
