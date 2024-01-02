#!/usr/bin/env python3
import os
import datetime
import requests
import subprocess
import logging
import argparse
from dateutil.parser import parse
from dateutil import tz
from seconds import convert_seconds

script_dir = os.path.dirname(os.path.abspath(__file__))
log_file_path = os.path.join(script_dir, 'time_check.log')
logging.basicConfig(filename=log_file_path, level=logging.DEBUG,
                    format='%(asctime)s %(levelname)s %(name)s %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')
logger=logging.getLogger(__name__) 

def check_time(url='http://worldtimeapi.org/api/timezone/Etc/UTC', threshold=0.4):
    # Get the system time
    system_time = datetime.datetime.now()
    # Get the online time
    print(f"Getting the online time from {url}")
    response = requests.get(url)
    online_time = parse(response.json()['datetime'])
    # Convert both times to UTC
    system_time = system_time.replace(tzinfo=tz.tzutc())
    online_time = online_time.replace(tzinfo=tz.tzutc())
    print('System time:', system_time)
    print('Online time:', online_time)
    # Calculate the difference
    time_difference = online_time - system_time
    # get the time difference in seconds
    time_difference_seconds = time_difference.total_seconds()
    print(f"The difference between the online time and the system time is {convert_seconds(time_difference_seconds)}.") 
    # If the difference is greater than the threshold, indicate a discrepancy
    if abs(time_difference_seconds) > threshold:
        return False
    return True

def set_time(npt_url='pool.ntp.org'):
    # Define the command as a list
    command = ["sudo", "ntpdate", npt_url]
    print(f"Setting the system time: {' '.join(command)}")
    # Run the command and capture the output
    result = subprocess.run(command, capture_output=True, text=True)
    result_text = result.stdout if result.stdout else result.stderr
    result_text = result_text.strip() if result_text else "No output from command."
    logger.info(result_text)
    print(result_text)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check and set system time.")
    parser.add_argument("-s", "--seconds", type=float, default=1, help="Threshold in seconds for time difference")
    parser.add_argument("-f", "--force", action="store_true", help="Force time synchronization")

    args = parser.parse_args()

    print("Rog's time checker...")

    if args.force:
        set_time()
    elif check_time(threshold=args.seconds):
        print("System time OK.")
    else:
        set_time()
        check_time(threshold=args.seconds)
