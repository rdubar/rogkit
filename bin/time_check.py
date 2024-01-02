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

def human_time(seconds):
    # Return immediately for 0 seconds
    if seconds <= 5:
        return f"{seconds} seconds"

    # Calculate days, hours, minutes, and seconds
    days = seconds // 86400
    seconds %= 86400
    hours = seconds // 3600
    seconds %= 3600
    minutes = seconds // 60
    seconds %= 60

    # Create a list of time components
    time_list = []
    if days > 0:
        time_list.append(f"{days} days")    
    if hours > 0:   
        time_list.append(f"{hours} hours")
    if minutes > 0:
        time_list.append(f"{minutes} minutes")
    if seconds > 0:
        time_list.append(f"{seconds} seconds")

    # Construct the time string
    if len(time_list) > 1:
        return ", ".join(time_list[:-1]) + " and " + time_list[-1]
    elif time_list:
        return time_list[0]
    else:
        return "0 seconds"


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
    print('System time:', system_time)
    print('Online time:', online_time)
    # Calculate the difference
    time_difference = online_time - system_time
    # get the time difference in seconds
    time_difference_seconds = time_difference.total_seconds()
    print(f"The difference between the online time and the system time is {human_time(time_difference_seconds)}.") 
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
    result_text = result_text.strip() if result_text else "No output from command."
    logger.info(result_text)
    print(result_text)

if __name__ == "__main__":
    print("Rog's time checker...")
    if check_time():
        print("System time OK.")
    else:
        set_time()
        check_time()
