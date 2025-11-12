"""
TMDb (The Movie Database) API integration for movie metadata.

Fetches movie details (cast, crew, synopsis, ratings, poster/backdrop images)
and caches results to pickle file for offline access.
"""
import argparse
import csv
import os
import pickle
import warnings
from datetime import datetime, UTC
from pathlib import Path
from pprint import pprint
from typing import Dict, Iterable, List, Optional, Tuple, Any

import requests  # type: ignore

from rogkit_package.bin.tomlr import load_rogkit_toml
from .media_settings import tmdb_data_file
from .media_records import common_schema
from rogkit_package.media.extra_sources.cache import EXTRAS_CACHE_PATH, write_extras_cache


def get_api_key():
    """Load TMDb API key from rogkit TOML configuration."""
    toml = load_rogkit_toml().get('tmdb', {})
    return toml.get('tmdb_api_key')

class DataList:
    """TMDb data cache manager for movie records with pickle persistence."""
    
    def __init__(self):
        self.records = {}
        self.data_file = tmdb_data_file
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

            new_title = tmdb_data.get('title') or title
            new_year = (tmdb_data.get('release_date') or '')[:4]
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
        if os.path.exists(self.data_file):
            with open(self.data_file, 'rb') as f:
                self.records = pickle.load(f)
                print(f"Loaded {len(self.records)} titles from {self.data_file}")
        else:
            print(f"Data file {self.data_file} not found")

    def save_to_file(self):
        """Save movie records to pickle file."""
        with open(self.data_file, 'wb') as f:
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
            title = tmdb_data.get('title')
            year = tmdb_data.get('release_date')[:4]
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
        response = requests.get(url, timeout=10)
        
        if response.status_code != 200:
            print(f"Failed TMDB search for {title} ({year}): Status {response.status_code}")
            return None
        
        results = response.json().get('results', [])
        
        if not results:
            print(f"No TMDB search results found for {title} ({year})")
            return None

        # If year is provided, try filtering results by year first
        filtered_results = results
        if year:
            filtered_results = [
                result for result in results
                if result.get('release_date') and result['release_date'][:4] == str(year)
            ]
            
            if not filtered_results:
                print(f"No exact year match for {title} ({year}). Retrying without year filter...")
                filtered_results = results  # fallback to all results

        if len(filtered_results) > 1:
            print(f"⚠️ Multiple TMDB matches found for {title} ({year if year else ''}) - using first match.")

        # Pick first match safely
        movie_id = filtered_results[0]['id']
        detailed_url = f"https://api.themoviedb.org/3/movie/{movie_id}?api_key={self.api_key}&append_to_response=credits"
        detailed_response = requests.get(detailed_url, timeout=10)
        
        if detailed_response.status_code == 200:
            return detailed_response.json()
        
        print(f"Failed TMDB detail fetch for movie ID {movie_id}")
        return None
    
    def delete_record(self, title, year=None):
        """Remove movie record from cache."""
        key = (str(title), str(year))
        if key in self.records.keys():
            del self.records[key]
            print(f"Deleted {title} ({year})")
            self.save_to_file()
        else:
            print(f"No record found for {title} ({year})")

    def dump_records(self):
        """Pretty-print all cached movie records."""
        pprint(self.records)
    
    def list_records(self):
        """List all cached movie titles and years."""
        for key in sorted(self.records.keys()):
            print(f"{key[0]} ({key[1]})")  
    
    def get_media_record(self, title, year=None):
        """Get movie record in common schema format for database insertion."""
        tmdb_info = self.get_movie_details(title, year)
        if not tmdb_info:
            return None
        record = {}
        for key in common_schema.keys():
            record[key] = tmdb_info.get(key)
        record['duration'] = int(tmdb_info.get('runtime') * 60 * 1000)
        record['summary'] = tmdb_info.get('overview')
        record['rating'] = int(tmdb_info.get('vote_average'))
        record['year'] = int(tmdb_info.get('release_date')[:4])
        record['thumb'] = f"https://image.tmdb.org/t/p/original{tmdb_info.get('poster_path')}"
        record['art'] = f"https://image.tmdb.org/t/p/original{tmdb_info.get('backdrop_path')}"  
        record['genres'] = ', '.join(genre.get('name') for genre in tmdb_info.get('genres', []))
        record['actors'] = ', '.join(actor.get('name') for actor in tmdb_info.get('credits', {}).get('cast', []))
        record['directors'] = ', '.join(director.get('name') for director in tmdb_info.get('credits', {}).get('crew', []) if director.get('job') == 'Director')
        record['writers'] = ', '.join(writer.get('name') for writer in tmdb_info.get('credits', {}).get('crew', []) if writer.get('job') == 'Writer')
        return record
    
    
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

    with csv_path.open('r', encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or not any(name.lower() == 'title' for name in reader.fieldnames):
            print("CSV must contain a 'title' column.")
            return [], 0

        for row in reader:
            title = extract_row_value(row, ('title', 'Title'))
            if not title:
                continue
            year_str = extract_row_value(row, ('year', 'Year'))
            year = int(year_str) if year_str and year_str.isdigit() else None

            record, added = data_list.ensure_record(title, year, verbose=verbose, force=force)
            if added:
                new_fetches += 1

            if not record:
                continue

            tmdb_id = record.get('id')
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


def build_extra_record(tmdb_data: Dict[str, Any], csv_row: Dict[str, Any], provider: str) -> Dict[str, Any]:
    """Convert TMDb payload into a compact extras record for the Plex cache."""

    release_date = tmdb_data.get('release_date') or ''
    year = int(release_date[:4]) if len(release_date) >= 4 and release_date[:4].isdigit() else None
    runtime = tmdb_data.get('runtime')
    runtime_minutes = int(runtime) if isinstance(runtime, (int, float)) else None
    vote_average = tmdb_data.get('vote_average')
    rating = float(vote_average) if isinstance(vote_average, (int, float)) else None

    raw_provider = extract_row_value(csv_row, ('platform', 'Platform', 'source', 'Source', 'provider', 'Provider'))
    resolved_provider = (raw_provider or provider or 'extras').strip().lower()

    timestamp = datetime.now(UTC).isoformat().replace("+00:00", "Z")

    extras: Dict[str, Any] = {
        "title": tmdb_data.get('title') or tmdb_data.get('original_title'),
        "original_title": tmdb_data.get('original_title'),
        "year": year,
        "tmdb_id": tmdb_data.get('id'),
        "runtime_minutes": runtime_minutes,
        "summary": tmdb_data.get('overview'),
        "rating": rating,
        "genres": [genre.get('name') for genre in tmdb_data.get('genres', []) if genre.get('name')],
        "actors": [actor.get('name') for actor in tmdb_data.get('credits', {}).get('cast', []) if actor.get('name')][:10],
        "directors": [
            crew.get('name')
            for crew in tmdb_data.get('credits', {}).get('crew', [])
            if crew.get('job') == 'Director' and crew.get('name')
        ],
        "writers": [
            crew.get('name')
            for crew in tmdb_data.get('credits', {}).get('crew', [])
            if crew.get('job') in {"Writer", "Screenplay"} and crew.get('name')
        ],
        "poster": f"https://image.tmdb.org/t/p/original{tmdb_data.get('poster_path')}" if tmdb_data.get('poster_path') else None,
        "backdrop": f"https://image.tmdb.org/t/p/original{tmdb_data.get('backdrop_path')}" if tmdb_data.get('backdrop_path') else None,
        "provider": resolved_provider,
        "csv": {key: value for key, value in csv_row.items() if value},
        "updated_at": timestamp,
    }

    return extras


def main():
    """CLI entry point for TMDb data management."""
    parser = argparse.ArgumentParser(description='Get movie details from TMDb')
    parser.add_argument('search_terms', nargs='*', help='Search terms for movies')
    parser.add_argument('-l', '--list', action='store_true', help='List titles')
    parser.add_argument('-d', '--dump', action='store_true', help='Dump title data')
    parser.add_argument('--delete', action='store_true', help='Delete title data')
    parser.add_argument('--reset', action='store_true', help='Reset data file')
    parser.add_argument('--csv', nargs='?', const='media.csv', help='Process titles from CSV (default: media.csv)')
    parser.add_argument('--output', help='Path to extras cache JSON (default: extras_tmdb.json)')
    parser.add_argument('--provider', default='csv', help='Source label for CSV imported titles')
    parser.add_argument('--dry-run', action='store_true', help='Preview results without writing cache')
    parser.add_argument('--refresh', action='store_true', help='Force refresh of TMDb data when processing CSV')
    parser.add_argument('--verbose', action='store_true', help='Verbose logging for CSV processing')
    args = parser.parse_args()

    warnings.simplefilter('default', DeprecationWarning)

    data_list = DataList()
    data_list.load_from_file()

    # Emit deprecation warnings for legacy commands
    def warn_legacy(flag: str) -> None:
        warnings.warn(
            f"Option {flag} is deprecated and will be removed in a future release.",
            DeprecationWarning,
            stacklevel=2,
        )

    if args.reset:
        warn_legacy("--reset")
    if args.list:
        warn_legacy("--list")
    if args.dump:
        warn_legacy("--dump")
    if args.delete:
        warn_legacy("--delete")
    if args.search_terms:
        warn_legacy("positional search arguments")

    if args.reset:
        data_list.records = {}
        data_list.save_to_file()
        print(f"Reset data file {data_list.data_file}")
        return
    elif args.list:
        data_list.list_records()
    elif args.csv:
        csv_path = Path(args.csv)
        output_path = Path(args.output) if args.output else EXTRAS_CACHE_PATH
        extras, added = process_csv_file(
            data_list,
            csv_path,
            provider=args.provider,
            verbose=args.verbose,
            force=args.refresh,
        )
        if added:
            data_list.save_to_file()
        if not extras:
            print("No records generated from CSV.")
            return
        if args.dry_run:
            print(f"Prepared {len(extras)} records (dry run, not written).")
        else:
            path = write_extras_cache(extras, output_path)
            print(f"Wrote {len(extras)} records to {path}")
    elif args.dump:
        data_list.dump_records()
    elif args.delete:
        search = ' '.join(args.search_terms)
        title, year = (search[:-5].strip(), int(search[-4:])) if search[-4:].isdigit() else (search, None)
        print(f"Deleting {title} {year}")
        data_list.delete_record(title, year=year)
    elif args.search_terms:
        search = ' '.join(args.search_terms)
        title, year = (search[:-5].strip(), int(search[-4:])) if search[-4:].isdigit() else (search, None)
        print(f"Searching for {title} {year}")
        record, added = data_list.ensure_record(title, year=year, verbose=True, force=args.refresh)
        if record and added:
            data_list.save_to_file()
    else:
        print("No search terms provided")

if __name__ == "__main__":
    main()


