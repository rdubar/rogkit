#!/usr/bin/env python3
"""
Clothes drying weather advisor.

Fun utility to decide if it's a good time to dry clothes outside based on
weather conditions (temperature, humidity, precipitation). Uses Open-Meteo
API for weather data and supports location detection/geocoding.
"""
import argparse
import requests
from datetime import datetime

# -------------------------
# Location helpers
# -------------------------

def get_location():
    """Get approximate location from IP address"""
    r = requests.get("https://ipapi.co/json/")
    r.raise_for_status()
    data = r.json()
    return data["latitude"], data["longitude"], data["city"]

def geocode_location(query):
    """Geocode a place name to lat/lon using OpenStreetMap Nominatim"""
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": query, "format": "json", "limit": 1}
    headers = {"User-Agent": "washing-cli/1.0"}
    r = requests.get(url, params=params, headers=headers)
    r.raise_for_status()
    results = r.json()
    if not results:
        raise ValueError(f"Location not found: {query}")
    lat, lon = float(results[0]["lat"]), float(results[0]["lon"])
    return lat, lon, results[0]["display_name"]

# -------------------------
# Weather helpers
# -------------------------

def get_weather(lat=55.8642, lon=-4.2518):
    """Fetch weather forecast from Open-Meteo API (defaults to Glasgow)."""
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "temperature_2m,relative_humidity_2m,precipitation_probability",
        "current_weather": True,
        "forecast_days": 1
    }
    r = requests.get(url, params=params)
    r.raise_for_status()
    return r.json()

def find_nearest_hour_index(weather):
    """Find the index in hourly.time closest to current_weather.time"""
    current_time = datetime.fromisoformat(weather["current_weather"]["time"])
    times = [datetime.fromisoformat(t) for t in weather["hourly"]["time"]]
    return min(range(len(times)), key=lambda i: abs(times[i] - current_time))

# -------------------------
# Logic
# -------------------------

def decide_washing(weather):
    """Analyze weather data and provide drying verdict with emoji."""
    current = weather["current_weather"]
    now_index = find_nearest_hour_index(weather)

    temp = current["temperature"]
    humidity = weather["hourly"]["relative_humidity_2m"][now_index]
    next_hours_rain = weather["hourly"]["precipitation_probability"][now_index:now_index+3]

    rain_risk = max(next_hours_rain)

    if rain_risk > 50:
        return f"☔ Nope! {rain_risk}% chance of rain soon — unless you like soggy socks."
    elif humidity > 85:
        return f"💨 Meh. {humidity}% humidity means it’ll take ages… maybe just use the radiator."
    elif temp < 12:
        return f"🥶 It’s only {temp}°C. Your clothes will be colder than your heart — skip it."
    else:
        return f"🌞 Go for it! {temp}°C and {humidity}% humidity, looks decent for drying."

# -------------------------
# CLI
# -------------------------

def main():
    """CLI entry point for clothes drying advisor."""
    parser = argparse.ArgumentParser(
        description="Decide if it's a good time to dry clothes outside 🧺"
    )
    parser.add_argument("--location", help="Location name (e.g. 'Glasgow' or 'London')")
    parser.add_argument("--coords", help="Coordinates in 'lat,lon' format")
    parser.add_argument("--default", action="store_true", help="Use default location (Glasgow)")

    args = parser.parse_args()
    
    lat, lon, place = None, None, None
    default_location = 55.8642, -4.2518, "Glasgow (default)"

    if args.default:
        lat, lon, place = default_location
    elif args.location:
        try:
            lat, lon, place = geocode_location(args.location)
            print(f"📍 Location set to: {place}")
        except Exception as e:
            print(f"Unable to geocode location: {e}")
    elif args.coords:
        lat_str, lon_str = args.coords.split(",")
        lat, lon = float(lat_str), float(lon_str)
        place = f"coords: {lat}, {lon}"
        print(f"📍 Location set to coordinates: {place}")
        
    if not lat:  # Try to auto-detect location
        try:
            lat, lon, place = get_location()
            print(f"📍 Location auto-set to: {place}")
        except Exception as e:
            print(f"Unable to detect location: {e}")
            
    if not lat:
        lat, lon, place = default_location
        print(f"📍 Falling back to default location: {place}")
        
    try:
        weather = get_weather(lat, lon)
        verdict = decide_washing(weather)
        print(verdict)
    except Exception as e:
        print(f"Unable to fetch weather: {e}")


if __name__ == "__main__":
    main()