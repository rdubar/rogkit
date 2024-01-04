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
logging.getLogger("urllib3").setLevel(logging.WARNING)
logger=logging.getLogger(__name__) 

def check_time(url='http://worldtimeapi.org/api/timezone/Etc/UTC', threshold=1):
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
    print(f"The difference between the online time and the system time is {convert_seconds(time_difference_seconds)}") 
    # If the difference is greater than the threshold, indicate a discrepancy
    if abs(time_difference_seconds) > threshold:
        return False
    return True

def set_time(ntp_url='pool.ntp.org'):
    command = ["sudo", "ntpdate", ntp_url]
    print(f"Setting the system time: {' '.join(command)}")
    start_time = datetime.datetime.now()
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        end_time = datetime.datetime.now()
        time_difference = (end_time - start_time).total_seconds()
        result_text = f"{ntp_url} : {time_difference} : {convert_seconds(time_difference)}"
        logger.info(result_text)
    except subprocess.CalledProcessError as e:
        end_time = datetime.datetime.now()
        time_difference = (end_time - start_time).total_seconds()
        result_text = f"{ntp_url} {e.stderr.strip()} {time_difference}."
        logger.warning(result_text)
    print(result_text)

def show_log_file():
    with open(log_file_path, 'r') as f:
        print(f.read())

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check and set system time.")
    parser.add_argument("-s", "--seconds", type=float, default=5, help="Threshold in seconds for time difference")
    parser.add_argument("-f", "--force", action="store_true", help="Force time synchronization")
    parser.add_argument("-l", "--log", action="store_true", help="Show the log file")

    args = parser.parse_args()

    print("Rog's time checker...")

    if args.force:
        set_time()
    elif check_time(threshold=args.seconds):
        print("System time OK.")
    else:
        set_time()
        check_time(threshold=args.seconds)

    if args.log:
        show_log_file()
