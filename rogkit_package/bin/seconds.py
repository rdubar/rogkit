#!/usr/bin/env python3
import sys
from .bignum import bignum

def pluralize(word, count):
    if count == 1:
        return word
    else:
        return word + 's'

def convert_seconds(seconds, long=False, end='', show_seconds=True):
    # Return immediately for 0 seconds
    if seconds == 0:
        return "0 seconds" + end

    seconds = int(seconds)

    # Define time units in seconds
    aeon = 31557600000000000  # Assuming an aeon as 1 billion years
    century = 3155760000  # 100 years
    year = 31557600  # 1 year (365.25 days accounting for leap years)
    day = 86400  # 1 day
    hour = 3600  # 1 hour
    minute = 60  # 1 minute

    # Calculate aeons, centuries, years, days, hours, minutes, and seconds
    time_list = []
    if long:
        aeons = seconds // aeon
        seconds %= aeon
        centuries = seconds // century
        seconds %= century
        if aeons > 0:
            time_list.append(f"{aeons:,} {pluralize('aeon', aeons)}")
        if centuries > 0:
            time_list.append(f"{centuries:,} {pluralize('century', centuries)}")
    
    years = seconds // year
    seconds %= year
    if years > 0:
        time_list.append(f"{years:,} {pluralize('year', years)}")

    days = seconds // day
    seconds %= day
    if days > 0:
        time_list.append(f"{days:,} {pluralize('day', days)}")

    hours = seconds // hour
    seconds %= hour
    if hours > 0:
        time_list.append(f"{hours} {pluralize('hour', hours)}")

    minutes = seconds // minute
    seconds %= minute
    if minutes > 0:
        time_list.append(f"{minutes} {pluralize('minute', minutes)}")

    if show_seconds and seconds > 0:
        time_list.append(f"{seconds} {pluralize('second', seconds)}")

    # Construct the time string
    if len(time_list) > 1:
        return ", ".join(time_list[:-1]) + " and " + time_list[-1] + end
    elif time_list:
        return time_list[0] + end
    else:
        return "0 seconds" + end


def hours_minutes_seconds(seconds):
    # return H:M:S for seconds
    seconds = int(seconds)
    hours = seconds // 3600
    seconds %= 3600
    minutes = seconds // 60
    seconds %= 60
    return f"{hours}:{minutes:02}:{seconds:02}"

if __name__ == "__main__":
    if len(sys.argv) > 1:
        try:
            input_seconds = int(sys.argv[1])
            print(convert_seconds(input_seconds))
        except ValueError:
            print("Please provide a valid number of seconds.")
    else:
        print("Convert seconds into years, days, minutes etc.\nUsage: seconds.py [number of seconds]")
