#!/usr/bin/env python3
import datetime
import requests
import subprocess
import logging
from dateutil import parser, tz

logging.basicConfig(filename='time_check.log', level=logging.DEBUG,
                    format='%(asctime)s %(levelname)s %(name)s %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')
logger=logging.getLogger(__name__) 

def check_time(url='http://worldtimeapi.org/api/timezone/Etc/UTC', threshold=0.4):
    # Get the system time
    system_time = datetime.datetime.now()
    # Get the online time
    print(f"Getting the online time from {url}")
    response = requests.get(url)
    online_time = parser.parse(response.json()['datetime'])
    # Convert both times to UTC
    system_time = system_time.replace(tzinfo=tz.tzutc())
    online_time = online_time.replace(tzinfo=tz.tzutc())
    # Calculate the difference
    time_difference = online_time - system_time
    print(f"The difference between the online time and the system time is {time_difference}.")
    # get the time difference in seconds
    time_difference_seconds = time_difference.total_seconds()
    # If the difference is greater than 10 seconds, set the system time
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
    result_text = result_text.strip()
    logger.info(result_text)
    print(result_text)

if __name__ == "__main__":
    print("Rog's time checker...")
    if check_time():
        print("System time OK.")
    else:
        set_time()
        check_time()
