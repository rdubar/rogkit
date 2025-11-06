"""
TMDb (The Movie Database) API integration for movie metadata.

Fetches movie details (cast, crew, synopsis, ratings, poster/backdrop images)
and caches results to pickle file for offline access.
"""
import argparse
import os
import pickle
import requests  # type: ignore
import json
from datetime import datetime
from pprint import pprint

from ..bin.tomlr import load_rogkit_toml
from .media_settings import tmdb_data_file
from .media_records import common_schema


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
        print(key)
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
        for key, value in common_schema.items():
            if key in common_schema.keys():
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

def main():
    """CLI entry point for TMDb data management."""
    parser = argparse.ArgumentParser(description='Get movie details from TMDb')
    parser.add_argument('search_terms', nargs='*', help='Search terms for movies')
    parser.add_argument('-l', '--list', action='store_true', help='List titles')
    parser.add_argument('-d', '--dump', action='store_true', help='Dump title data')
    parser.add_argument('--delete', action='store_true', help='Delete title data')
    parser.add_argument('--reset', action='store_true', help='Reset data file')
    args = parser.parse_args()

    data_list = DataList()
    data_list.load_from_file()

    if args.reset:
        data_list.records = {}
        data_list.save_to_file()
        print(f"Reset data file {data_list.data_file}")
        return
    elif args.list:
        data_list.list_records()
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
        if data_list.get_record(title, year=year, verbose=True):
            data_list.save_to_file()
    else:
        print("No search terms provided")

if __name__ == "__main__":
    main()
