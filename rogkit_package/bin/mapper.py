"""
Address geocoding and mapping utility.

Reads addresses from CSV file, geocodes them using Nominatim (OpenStreetMap),
and creates an interactive Folium map with markers. Experimental.
"""
import argparse
import os
import sys
from typing import List, Optional

import folium  # type: ignore
import pandas as pd  # type: ignore
from geopy.exc import (  # type: ignore
    GeocoderServiceError,
    GeocoderTimedOut,
    GeocoderUnavailable,
    GeopyError,
)
from geopy.extra.rate_limiter import RateLimiter  # type: ignore
from geopy.geocoders import Nominatim  # type: ignore

from ..settings import data_dir

DEFAULT_DATA_FILE = os.path.join(data_dir, "homes_map_data.csv")
USER_AGENT = "rogkit-mapper (contact: rdubar@gmail.com)"
REQUEST_TIMEOUT_SECONDS = 5


def _build_addresses(df: pd.DataFrame, components: List[str]) -> pd.Series:
    missing = [col for col in components if col not in df.columns]
    if missing:
        raise ValueError(f"Missing expected column(s): {', '.join(missing)}")

    df[components] = df[components].fillna("")
    return df[components].agg(", ".join, axis=1).str.strip(", ")


def _geocode_rows(addresses: pd.Series, geocode) -> List[Optional[object]]:
    results: List[Optional[object]] = []

    for address in addresses:
        try:
            result = geocode(address, timeout=REQUEST_TIMEOUT_SECONDS)
        except (GeocoderTimedOut, GeocoderUnavailable) as exc:
            print(
                "\nGeocoding timed out or the service became unavailable. "
                "Stopping early to avoid repeated requests."
            )
            print(f"Last address attempted: {address!r}")
            raise RuntimeError(
                "Nominatim did not respond in time. Please retry later or provide a smaller batch."
            ) from exc
        except GeocoderServiceError as exc:
            print(f"Geocoding failed for {address!r}: {exc}")
            result = None
        results.append(result)

    return results


def map_from_file(path: Optional[str]) -> None:
    """
    Maps addresses from a CSV file and saves the map as an HTML file.
    The CSV file should have columns 'Street', 'District', 'City', and 'Post Code'.
    """
    print("Starting mapping process...")

    if not path:
        path = DEFAULT_DATA_FILE
        print("No file path provided, using default data:", path)

    df = pd.read_csv(path)

    address_components = ["Street", "District", "City", "Post Code"]
    df["Address"] = _build_addresses(df.copy(), address_components)

    print("Initializing geolocator...")
    geolocator = Nominatim(user_agent=USER_AGENT)
    geocode = RateLimiter(
        geolocator.geocode,
        min_delay_seconds=1,
        max_retries=0,
        swallow_exceptions=False,
    )

    try:
        df["location"] = _geocode_rows(df["Address"], geocode)
    except RuntimeError as exc:
        print(exc)
        return

    df["latitude"] = df["location"].apply(lambda loc: loc.latitude if loc else None)
    df["longitude"] = df["location"].apply(lambda loc: loc.longitude if loc else None)

    failed_geocoding = df[df["location"].isnull()]
    if not failed_geocoding.empty:
        print("\nGeocoding failed for the following addresses:")
        print(failed_geocoding[["Address"]])

    successful_locations = df.dropna(subset=["latitude", "longitude"])
    if successful_locations.empty:
        print("\nNo locations were successfully geocoded. Map not created.")
        return

    map_center = [
        successful_locations["latitude"].mean(),
        successful_locations["longitude"].mean(),
    ]
    mymap = folium.Map(location=map_center, zoom_start=6)

    for _, row in successful_locations.iterrows():
        info_html = "<br>".join(
            [
                f"<b>{col}</b>: {row[col]}"
                for col in df.columns
                if col not in ["latitude", "longitude", "location"]
            ]
        )
        folium.Marker(
            location=[row["latitude"], row["longitude"]],
            popup=folium.Popup(info_html, max_width=300),
            tooltip=row.get("Name", "Address"),
        ).add_to(mymap)

    mymap.save("mapped_addresses.html")
    print("Map saved as 'mapped_addresses.html'")


def main() -> None:
    """CLI entry point for address geocoding and mapping."""
    parser = argparse.ArgumentParser(description="Map addresses from a CSV file.")
    parser.add_argument(
        "file_path",
        nargs="?",
        default=None,
        help="Path to the CSV file with addresses.",
    )
    args = parser.parse_args()

    try:
        map_from_file(args.file_path)
    except FileNotFoundError as exc:
        print(f"Could not open CSV file: {exc.filename or exc}")
        sys.exit(1)
    except GeopyError as exc:
        print(f"Geocoding error: {exc}")
        sys.exit(1)
    except pd.errors.ParserError as exc:
        print(f"CSV parsing error: {exc}")
        sys.exit(1)
    except RuntimeError as exc:
        print(str(exc))
        sys.exit(1)
    except ValueError as exc:
        print(f"Input error: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()