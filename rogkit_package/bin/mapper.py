"""
Address geocoding and mapping utility.

Reads addresses from CSV file, geocodes them using Nominatim (OpenStreetMap),
and creates an interactive Folium map with markers. Experimental.
"""
import os
import argparse

import pandas as pd  # type: ignore
from geopy.geocoders import Nominatim  # type: ignore
from geopy.extra.rate_limiter import RateLimiter  # type: ignore
import folium  # type: ignore

from ..settings import data_dir

DEFAULT_DATA_FILE = os.path.join(data_dir, 'homes_map_data.csv')


def map_from_file(path):
    """
    Maps addresses from a CSV file and saves the map as an HTML file.
    The CSV file should have a column named 'Address' with the addresses to geocode.
    """
    print("Starting mapping process...")
    
    if not path:
        path = DEFAULT_DATA_FILE
        print("No file path provided, using default data: ", path)
        
    # Load the CSV file
    df = pd.read_csv(path)
    
    # Combine address fields into a single string
    address_components = ["Street", "District", "City", "Post Code"]  # Adjust based on your actual column names
    for col in address_components:
        if col not in df.columns:
            raise ValueError(f"Missing expected column: {col}")
    df["Address"] = df[address_components].astype(str).agg(', '.join, axis=1)

    # Initialize geolocator
    print("Initializing geolocator...")
    geolocator = Nominatim(user_agent="geo_map_script")
    geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1)

    # Add lat/lon columns using geocoding
    df["location"] = df["Address"].apply(geocode)
    df["latitude"] = df["location"].apply(lambda loc: loc.latitude if loc else None)
    df["longitude"] = df["location"].apply(lambda loc: loc.longitude if loc else None)
    
    # print rows where geolocating failed
    failed_geocoding = df[df["location"].isnull()]
    print("Geocoding failed for the following addresses:")
    print(failed_geocoding[["Address"]])

    # Drop rows where geocoding failed
    df = df.dropna(subset=["latitude", "longitude"])

    # Create a map centered on the average location
    map_center = [df["latitude"].mean(), df["longitude"].mean()]
    mymap = folium.Map(location=map_center, zoom_start=6)

    # Add markers
    for idx, row in df.iterrows():
        info_html = "<br>".join([f"<b>{col}</b>: {row[col]}" for col in df.columns if col not in ["latitude", "longitude", "location"]])
        folium.Marker(
            location=[row["latitude"], row["longitude"]],
            popup=folium.Popup(info_html, max_width=300),
            tooltip=row.get("Name", "Address")  # Adjust this as needed
        ).add_to(mymap)

    # Save the map to HTML
    mymap.save("mapped_addresses.html")
    print("Map saved as 'mapped_addresses.html'")
    
def main():
    """CLI entry point for address geocoding and mapping."""
    parser = argparse.ArgumentParser(description="Map addresses from a CSV file.")
    parser.add_argument("file_path", nargs='?', default=None, help="Path to the CSV file with addresses.")
    args = parser.parse_args()

    map_from_file(args.file_path)

if __name__ == "__main__":
    main()
    
    