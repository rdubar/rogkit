#!/usr/bin/env python3
import requests
import datetime
import os
import pytz
from dataclasses import dataclass
import argparse
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Dataclass to structure the weather data
@dataclass
class WeatherData:
    location: str
    time: str
    timezone: str
    weather: str
    air_pressure: float

def fetch_location_data(api_key):
    """Fetches location data using IPinfo or similar service."""
    try:
        response = requests.get("http://ipinfo.io/json?token=" + api_key)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Error fetching location data: {e}")
        return None

def fetch_weather_data(city, api_key):
    """Fetches weather data using OpenWeatherMap or similar service."""
    try:
        response = requests.get(f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}")
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Error fetching weather data: {e}")
        return None

def get_weather_data(api_key='', options=['weather', 'pressure']):
    location_api_key = os.getenv('IPINFO_API_KEY', api_key)
    location_data = fetch_location_data(location_api_key)
    
    if not location_data:
        return None

    city = location_data['city']
    weather_api_key = os.getenv('OPENWEATHER_API_KEY', api_key)
    weather_data = fetch_weather_data(city, weather_api_key)

    if not weather_data:
        return None

    timezone = pytz.timezone(location_data['timezone'])
    local_time = datetime.datetime.now(timezone).strftime("%Y-%m-%d %H:%M:%S")

    weather_info = WeatherData(
        location=city,
        time=local_time,
        timezone=str(timezone),
        weather=weather_data['weather'][0]['main'] if 'weather' in options else 'N/A',
        air_pressure=weather_data['main']['pressure'] if 'pressure' in options else 'N/A'
    )

    return weather_info

def main():
    parser = argparse.ArgumentParser(description="Get current weather data")
    # optional text argument which is location to show info for
    parser.add_argument('--location', type=str, required=False, help='Location to get weather data for')
    parser.add_argument('--api_key', type=str, required=False, help='API Key for the weather service')
    parser.add_argument('--options', nargs='+', help='Data options: weather pressure', default=['weather', 'pressure'])
    args = parser.parse_args()

    weather_info = get_weather_data(args.api_key, args.options)
    if weather_info:
        print(weather_info)
    else:
        print("Failed to retrieve weather data.")

if __name__ == "__main__":
    main()
