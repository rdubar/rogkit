#!/usr/bin/env python3
"""
Clothes drying weather advisor.

Fun utility to decide if it's a good time to dry clothes outside based on
weather conditions (temperature, humidity, precipitation). Uses Open-Meteo
API for weather data and supports location detection/geocoding.
"""
import argparse
from datetime import datetime

import requests
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

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

def analyze_drying_weather(weather):
    """Analyze weather data and provide drying verdict plus metrics."""
    current = weather["current_weather"]
    now_index = find_nearest_hour_index(weather)

    temp = current["temperature"]
    humidity = weather["hourly"]["relative_humidity_2m"][now_index]
    next_hours_rain = weather["hourly"]["precipitation_probability"][now_index : now_index + 3]
    rain_risk = max(next_hours_rain)

    if rain_risk > 50:
        verdict = f"☔ Nope! {rain_risk}% chance of rain soon — unless you like soggy socks."
        style = "red"
    elif humidity > 85:
        verdict = f"💨 Meh. {humidity}% humidity means it’ll take ages… maybe just use the radiator."
        style = "yellow"
    elif temp < 12:
        verdict = f"🥶 It’s only {temp}°C. Your clothes will be colder than your heart — skip it."
        style = "yellow"
    else:
        verdict = f"🌞 Go for it! {temp}°C and {humidity}% humidity, looks decent for drying."
        style = "green"

    return {
        "temperature": temp,
        "humidity": humidity,
        "rain_risk": rain_risk,
        "wind": current.get("windspeed"),
        "verdict": verdict,
        "style": style,
        "time": current["time"],
    }


def render_report(place, analysis):
    """Render a colorful drying advisory."""
    metrics = Table(
        title=f"Weather snapshot for {place}",
        header_style="bold blue",
        box=box.SIMPLE_HEAVY,
        expand=False,
    )
    metrics.add_column("Metric", style="cyan", no_wrap=True)
    metrics.add_column("Value", style="white")

    metrics.add_row("Temperature", f"{analysis['temperature']}°C")
    metrics.add_row("Humidity", f"{analysis['humidity']}%")
    metrics.add_row("Rain risk (next 3h)", f"{analysis['rain_risk']}%")
    wind = analysis.get("wind")
    if wind is not None:
        metrics.add_row("Wind", f"{wind} km/h")
    metrics.add_row("Updated", analysis["time"].replace("T", " "))

    console.print(metrics)
    console.print()
    console.print(
        Panel.fit(
            analysis["verdict"],
            title="Drying verdict",
            border_style=analysis["style"],
            padding=(1, 2),
        )
    )

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
            console.print(f"📍 Location set to: {place}", style="cyan")
        except Exception as e:
            console.print(f"[red]Unable to geocode location:[/] {e}")
    elif args.coords:
        lat_str, lon_str = args.coords.split(",")
        lat, lon = float(lat_str), float(lon_str)
        place = f"coords: {lat}, {lon}"
        console.print(f"📍 Location set to coordinates: {place}", style="cyan")
        
    if not lat:  # Try to auto-detect location
        try:
            lat, lon, place = get_location()
            console.print(f"📍 Location auto-set to: {place}", style="cyan")
        except Exception as e:
            console.print(f"[red]Unable to detect location:[/] {e}")
            
    if not lat:
        lat, lon, place = default_location
        console.print(f"📍 Falling back to default location: {place}", style="yellow")
        
    try:
        weather = get_weather(lat, lon)
        analysis = analyze_drying_weather(weather)
        render_report(place, analysis)
    except Exception as e:
        console.print(f"[red]Unable to fetch weather:[/] {e}")


if __name__ == "__main__":
    main()
