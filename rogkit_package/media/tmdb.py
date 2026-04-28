#!/usr/bin/env python3
"""
Build TMDb-powered extras JSON for the media cache.

Given a CSV of titles, this script looks up each entry at TMDb, caches the raw
payloads locally, and writes a compact extras JSON file that
`rogkit_package.media.extra_sources.integrate` can merge into the Plex cache.
"""

import argparse
import csv
import pickle
from datetime import datetime, UTC
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests  # type: ignore

from rogkit_package.bin.tomlr import load_rogkit_toml
from rogkit_package.media.extra_sources.cache import (
    EXTRAS_CACHE_PATH,
    write_extras_cache,
)
from rogkit_package.settings import data_dir


DATA_DIR = Path(data_dir)
DEFAULT_CSV_PATH = DATA_DIR / "media.csv"
DEFAULT_TMDB_PICKLE = DATA_DIR / "tmdb_cache.pkl"
TMDB_TIMEOUT_SECONDS = 10


def ensure_data_dir() -> None:
    """Ensure the shared media data directory exists."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def get_api_key():
    """Load TMDb API key from rogkit TOML configuration."""
    toml = load_rogkit_toml().get("tmdb", {})
    return toml.get("tmdb_api_key")


class DataList:
    """TMDb data cache manager for movie records with pickle persistence."""

    def __init__(self):
        ensure_data_dir()
        self.records: Dict[Tuple[str, str], Dict[str, Any]] = {}
        self.data_file = DEFAULT_TMDB_PICKLE
        self.api_key = get_api_key()

    def lookup_record(self, title: str, year: Optional[int] = None):
        """Return a cached TMDb payload matching the given title/year."""

        if not title:
            return None
        title_normalized = title.strip().lower()
        if year is not None:
            year_str = str(year)
            for (cached_title, cached_year), payload in self.records.items():
                if cached_title.lower() == title_normalized and cached_year == year_str:
                    return payload
        for (cached_title, _cached_year), payload in self.records.items():
            if cached_title.lower() == title_normalized:
                return payload
        return None

    def ensure_record(
        self,
        title: str,
        year: Optional[int] = None,
        verbose: bool = False,
        force: bool = False,
    ):
        """Ensure a TMDb payload exists for a title/year and return it with an add flag."""

        if force:
            tmdb_data = self.get_movie_details(title, year)
            if not tmdb_data:
                if verbose:
                    print(f"No match found for {title} ({year}) during refresh")
                return None, False

            new_title = tmdb_data.get("title") or title
            new_year = (tmdb_data.get("release_date") or "")[:4]
            key = (new_title, new_year)
            self.records[key] = tmdb_data
            if verbose:
                print(f"Refreshed TMDb data for {new_title} ({new_year or 'n/a'})")
            return tmdb_data, True

        existing = self.lookup_record(title, year)
        if existing:
            if verbose:
                print(f"Record already cached for {title} ({year or 'n/a'})")
            return existing, False

        fetched = self.get_record(title, year=year, verbose=verbose)
        if fetched:
            return fetched, True

        # Attempt to fall back to any cached payload that may now exist
        return self.lookup_record(title, year), False

    def load_from_file(self):
        """Load cached movie records from pickle file."""
        if self.data_file.exists():
            with self.data_file.open("rb") as f:
                self.records = pickle.load(f)
                print(f"Loaded {len(self.records)} titles from {self.data_file}")
        else:
            print(f"No existing TMDb cache found at {self.data_file}. Starting fresh.")

    def save_to_file(self):
        """Save movie records to pickle file."""
        ensure_data_dir()
        with self.data_file.open("wb") as f:
            pickle.dump(self.records, f)
            print(f"Saved {len(self.records)} titles to {self.data_file}")

    def get_record(self, title, year=None, verbose=False):
        """Fetch movie record from TMDb API if not already cached."""
        key = (str(title), str(year))
        if key in self.records.keys():
            if verbose:
                print(f"Record found for {title} ({year})")
            return False
        tmdb_data = self.get_movie_details(title, year)
        if tmdb_data:
            title = tmdb_data.get("title")
            year = tmdb_data.get("release_date")[:4]
            if tmdb_data in self.records.values():
                if verbose:
                    print(f"Duplicate found for {title} ({year})")
                return False
            new_key = (title, year)
            self.records[new_key] = tmdb_data
            print(f"Added {title} ({year or ''}) to records")
            return tmdb_data
        else:
            print(f"No match found for {title} ({year})")
            return False

    def get_movie_details(self, title, year=None):
        """Search TMDb API for movie and return detailed metadata including credits."""
        url = f"https://api.themoviedb.org/3/search/movie?api_key={self.api_key}&query={title}"
        response = self._get_tmdb_response(url, f"TMDB search for {title} ({year})")
        if response is None:
            return None

        if response.status_code != 200:
            print(f"Failed TMDB search for {title} ({year}): Status {response.status_code}")
            return None

        try:
            results = response.json().get("results", [])
        except ValueError as exc:
            print(f"Failed TMDB search for {title} ({year}): Invalid JSON ({exc})")
            return None

        if not results:
            print(f"No TMDB search results found for {title} ({year})")
            return None

        # If year is provided, try filtering results by year first
        filtered_results = results
        if year:
            filtered_results = [
                result
                for result in results
                if result.get("release_date") and result["release_date"][:4] == str(year)
            ]

            if not filtered_results:
                print(
                    f"No exact year match for {title} ({year}). Retrying without year filter..."
                )
                filtered_results = results  # fallback to all results

        if len(filtered_results) > 1:
            print(
                f"⚠️ Multiple TMDB matches found for {title} ({year if year else ''}) - using first match."
            )

        # Pick first match safely
        movie_id = filtered_results[0]["id"]
        detailed_url = (
            f"https://api.themoviedb.org/3/movie/{movie_id}"
            f"?api_key={self.api_key}&append_to_response=credits"
        )
        detailed_response = self._get_tmdb_response(
            detailed_url,
            f"TMDB detail fetch for movie ID {movie_id}",
        )
        if detailed_response is None:
            return None

        if detailed_response.status_code == 200:
            try:
                return detailed_response.json()
            except ValueError as exc:
                print(
                    f"Failed TMDB detail fetch for movie ID {movie_id}: "
                    f"Invalid JSON ({exc})"
                )
                return None

        print(f"Failed TMDB detail fetch for movie ID {movie_id}")
        return None

    def _get_tmdb_response(self, url: str, context: str) -> Optional[requests.Response]:
        """Return a TMDb response, treating network failures as a cache miss."""
        try:
            return requests.get(url, timeout=TMDB_TIMEOUT_SECONDS)
        except requests.RequestException as exc:
            print(f"{context} failed: {exc}")
            return None


def process_csv_file(
    data_list: DataList,
    csv_path: Path,
    provider: str = "csv",
    verbose: bool = False,
    force: bool = False,
) -> Tuple[List[Dict[str, Any]], int]:
    """Process a CSV file of titles, returning extras records and the count of new TMDb fetches."""

    if not csv_path.exists():
        print(f"CSV file {csv_path} not found")
        return [], 0

    extras: List[Dict[str, Any]] = []
    new_fetches = 0
    seen_ids = set()

    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or not any(
            name.lower() == "title" for name in reader.fieldnames
        ):
            print("CSV must contain a 'title' column.")
            return [], 0

        for row in reader:
            title = extract_row_value(row, ("title", "Title"))
            if not title:
                continue
            year_str = extract_row_value(row, ("year", "Year"))
            year = int(year_str) if year_str and year_str.isdigit() else None

            record, added = data_list.ensure_record(
                title, year, verbose=verbose, force=force
            )
            if added:
                new_fetches += 1

            if not record:
                continue

            tmdb_id = record.get("id")
            if tmdb_id in seen_ids:
                continue
            seen_ids.add(tmdb_id)

            extras.append(build_extra_record(record, row, provider))

    return extras, new_fetches


def extract_row_value(row: Dict[str, Any], keys: Iterable[str]) -> Optional[str]:
    """Return the first matching value for any key in keys from the CSV row."""

    for key in keys:
        if key in row and row[key]:
            return row[key].strip()
    return None


def build_extra_record(
    tmdb_data: Dict[str, Any], csv_row: Dict[str, Any], provider: str
) -> Dict[str, Any]:
    """Convert TMDb payload into a compact extras record for the Plex cache."""

    release_date = tmdb_data.get("release_date") or ""
    year = (
        int(release_date[:4])
        if len(release_date) >= 4 and release_date[:4].isdigit()
        else None
    )
    runtime = tmdb_data.get("runtime")
    runtime_minutes = int(runtime) if isinstance(runtime, (int, float)) else None
    vote_average = tmdb_data.get("vote_average")
    rating = float(vote_average) if isinstance(vote_average, (int, float)) else None

    raw_provider = extract_row_value(
        csv_row,
        ("platform", "Platform", "source", "Source", "provider", "Provider"),
    )
    resolved_provider = (raw_provider or provider or "extras").strip().lower()

    timestamp = datetime.now(UTC).isoformat().replace("+00:00", "Z")

    extras: Dict[str, Any] = {
        "title": tmdb_data.get("title") or tmdb_data.get("original_title"),
        "original_title": tmdb_data.get("original_title"),
        "year": year,
        "tmdb_id": tmdb_data.get("id"),
        "runtime_minutes": runtime_minutes,
        "summary": tmdb_data.get("overview"),
        "rating": rating,
        "genres": [
            genre.get("name")
            for genre in tmdb_data.get("genres", [])
            if genre.get("name")
        ],
        "actors": [
            actor.get("name")
            for actor in tmdb_data.get("credits", {}).get("cast", [])
            if actor.get("name")
        ][:10],
        "directors": [
            crew.get("name")
            for crew in tmdb_data.get("credits", {}).get("crew", [])
            if crew.get("job") == "Director" and crew.get("name")
        ],
        "writers": [
            crew.get("name")
            for crew in tmdb_data.get("credits", {}).get("crew", [])
            if crew.get("job") in {"Writer", "Screenplay"} and crew.get("name")
        ],
        "poster": f"https://image.tmdb.org/t/p/original{tmdb_data.get('poster_path')}"
        if tmdb_data.get("poster_path")
        else None,
        "backdrop": f"https://image.tmdb.org/t/p/original{tmdb_data.get('backdrop_path')}"
        if tmdb_data.get("backdrop_path")
        else None,
        "provider": resolved_provider,
        "csv": {key: value for key, value in csv_row.items() if value},
        "updated_at": timestamp,
    }

    return extras


def main():
    """CLI entry point for building extras JSON from TMDb."""
    parser = argparse.ArgumentParser(
        description="Fetch TMDb metadata for a CSV of titles and write extras JSON for integrate."
    )
    parser.add_argument(
        "--csv",
        default=str(DEFAULT_CSV_PATH),
        help=f"Path to the titles CSV (default: {DEFAULT_CSV_PATH})",
    )
    parser.add_argument(
        "--output",
        default=str(EXTRAS_CACHE_PATH),
        help=f"Destination for the extras JSON (default: {EXTRAS_CACHE_PATH})",
    )
    parser.add_argument(
        "--provider",
        default="csv",
        help="Provider label stored with each extras record (default: %(default)s).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch metadata and show a summary without writing the extras file.",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Force new TMDb lookups even if a title is already cached.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print per-title progress while processing the CSV.",
    )
    args = parser.parse_args()

    data_list = DataList()
    data_list.load_from_file()

    csv_path = Path(args.csv)
    output_path = Path(args.output)

    extras, new_fetches = process_csv_file(
        data_list,
        csv_path,
        provider=args.provider,
        verbose=args.verbose,
        force=args.refresh,
    )

    if new_fetches:
        data_list.save_to_file()

    total = len(extras)
    print(
        f"Prepared {total} extras record(s) from {csv_path} "
        f"with {new_fetches} TMDb fetch(es)."
    )

    if not extras:
        return

    if args.dry_run:
        print("Dry run: extras JSON was not written.")
        return

    path = write_extras_cache(extras, output_path)
    print(f"Wrote {total} record(s) to {path}")


if __name__ == "__main__":
    main()
