import requests
import argparse
import pickle
import dataclasses
import os
import time
import hashlib
import json
from typing import List
from pprint import pprint
from datetime import datetime
from ..bin.tomlr import load_rogkit_toml
from .plex_library import get_media_list
from .media_settings import tmdb_data_file
from .media_records import common_schema
from ..bin.seconds import convert_seconds

def get_tbdm_toml():
    toml = load_rogkit_toml()
    return toml.get('tmdb', {})

def get_api_key():
    toml = get_tbdm_toml()
    return toml.get('tmdb_api_key', None)

def generate_hash(data):
    data_string = json.dumps(data, sort_keys=True)
    hash_object = hashlib.sha256()
    hash_object.update(data_string.encode())
    return hash_object.hexdigest()

def _log(self, level, msg_format, *args, **kwargs):
    """ Outputs an formated string in log

        :param level (int): 1=> debug, 2=> info, 3=> warning, 4=> error
        :param message (basestring): name of the message
    """

    methods = ['debug', 'info', 'warning', 'error']
    log = getattr(_logger, methods[level])

    msg = msg_format.format(*args, **kwargs)
    log(msg)

@dataclasses.dataclass
class MediaRecord:
    title: str = None
    year: int = None
    tmdb: dict = None
    entry: str = None
    entry_hash: str = None
    media_hash: str = None

    def __post_init__(self):
        year = f' ({self.year})' if self.year else ''
        self.entry = f'{self.title}{year}'
        self.entry_hash = generate_hash(self.entry)

        def set_tmdb(self, tmdb_dict):
            self.tmdb = tmdb_dict
            self.media_hash = generate_hash(tmdb_dict)

@dataclasses.dataclass
class DataList:
    records: List[MediaRecord] = dataclasses.field(default_factory=list)
    info_dict: dict = dataclasses.field(default_factory=dict)
    data_file: str = tmdb_data_file
    api_key: str = None

    def __post_init__(self):
        self.api_key = get_api_key()

    def load_from_file(self):
        if not os.path.exists(self.data_file):
            print(f"Data file {self.data_file} not found")
            self.records = []  # Initialize with an empty list if file doesn't exist
            return
        try:
            with open(self.data_file, 'rb') as f:  # Open in binary read mode
                self.records = pickle.load(f)
                print(f"Loaded {len(self.records)} titles from {self.data_file}")
        except Exception as e:
            print(f"Error loading data from {self.data_file}: {e}")

    def save_to_file(self):
        print(f"Saving {len(self.records)} titles to {self.data_file}")
        try:
            with open(self.data_file, 'wb') as f:  # Open in binary write mode
                pickle.dump(self.records, f)
        except Exception as e:
            print(f"Error saving data to {self.data_file}: {e}")

    def reset_records(self):
        self.records = []
        self.info_dict = {}

    def add_record(self, new_record):
        if not any(record == new_record for record in self.records):
            self.records.append(new_record)
            self.info_dict[new_record.entry_hash] = new_record.tmdb
            return True
        return False

    def delete_record(self, title, year):
        record_to_delete = next((record for record in self.records if record.title == title and record.year == year), None)
        if record_to_delete:
            self.records.remove(record_to_delete)
            del self.info_dict[record_to_delete.entry_hash]
    
    def add_list(self, title_list):
        clock = time.perf_counter()
        if isinstance(title_list, str):
            title_list = [title_list]
        added, skipped, not_found = 0, 0, 0
        for number, (title, year) in enumerate(title_list):
            progress_info = f'[{number+1}/{len(title_list)}]'
            existing_record = next((record for record in self.records if record.title == title and record.year == year), None)
            if existing_record:
                print(f'{progress_info} Skipped existing record for {title} ({year})')
                skipped += 1
            else:
                details = self.get_movie_details(title)
                if details in ["No results found", "Error fetching detailed movie information", "Error searching for movie"]:
                    print(f'{progress_info} {details}: {title}')
                    not_found += 1
                else:
                    new_record = self.tmdb_to_media_record(details)
                    new_record.title, new_record.year = title, year  # Set title and year from the input list
                    self.add_record(new_record)  # Using the add_record method to handle adding
                    print(f'{progress_info} Added {title} ({year})')
                    added += 1
        print(f"Skipped {skipped} movies, could not find {not_found} movies, added {added} movies")
        self.save_to_file()
        elapsed = time.perf_counter() - clock
        print(f"Elapsed time: {elapsed} seconds")

    def get_movie_details(self, title):
        if not self.api_key:
            self.load_api_key()
            if not self.api_key:
                return "No TMDb API key found"

        # Replace spaces with '+' for URL encoding
        title_encoded = title.replace(' ', '+')
        url = f"https://api.themoviedb.org/3/search/movie?api_key={self.api_key}&query={title_encoded}"

        response = requests.get(url)
        if response.status_code == 200:
            results = response.json().get('results', [])
            if results:
                movie_id = results[0]['id']
                detailed_url = f"https://api.themoviedb.org/3/movie/{movie_id}?api_key={self.api_key}"
                detailed_response = requests.get(detailed_url)
                if detailed_response.status_code == 200:
                    return detailed_response.json()
                else:
                    return "Error fetching detailed movie information"
            else:
                return "No results found"
        else:
            return "Error searching for movie"

    @staticmethod
    def tmdb_to_media_record(tmdb_dict):
        # Extract year from release_date
        year = None
        if 'release_date' in tmdb_dict and tmdb_dict['release_date']:
            year = int(tmdb_dict['release_date'].split('-')[0])

        # Create a MediaRecord instance
        media_record = MediaRecord(
            title=tmdb_dict.get('title'),
            year=year,
            tmdb=tmdb_dict,
            # entry, entry_hash, and media_hash can be set here if needed,
            # or they can be calculated later based on application logic
        )

        return media_record

    def list_records(self):
        for record in self.records:
            print(record)



def get_args():
    parser = argparse.ArgumentParser(description='Get movie details from TMDb')
    parser.add_argument('-m', '--media', help='Process the media list', action='store_true')
    parser.add_argument('-d', '--delete', help='Delete the matching media', action='store_true')
    parser.add_argument('-p', '--pretty', help='Pretty print the output', action='store_true')
    parser.add_argument('-l', '--list', help='List titles', action='store_true')
    parser.add_argument('--api_key', help='TMDb API key', default=None)
    parser.add_argument('search_terms', nargs='*', help='Search terms for movies')
    return parser.parse_args()

def main():
    print("Rogkit TMDB tool")
    args = get_args()

    data_list = DataList()
    data_list.load_from_file()

    if args.list:
        data_list.list_records()
        return

    if args.delete and args.search_terms:
        process_deletion(data_list, ' '.join(args.search_terms))

    elif args.media:
        process_media_list(data_list)

    elif args.search_terms:
        process_search(data_list, ' '.join(args.search_terms), args.pretty)

    else:
        print("No search terms provided")

def process_deletion(data_list, search_terms):
    search_hash = generate_hash(search_terms)
    if search_hash in data_list.info_dict:
        del data_list.info_dict[search_hash]
        data_list.save_to_file()
        print(f"Deleted {search_terms}")
    else:
        print(f"{search_terms} not found")

def process_media_list(data_list):
    media_list = get_media_list()
    print(f'Found {len(media_list):,} titles in Plex library')
    data_list.add_list(media_list)

def process_search(data_list, search_terms, pretty_print):
    # Check if a year is given in search_terms
    if search_terms[-4:].isdigit():
        year = int(search_terms[-4:])
        title = search_terms[:-5].strip()
    else:
        year = None
        title = search_terms.strip()

    # Ensure data_list.records is initialized
    if data_list.records is None:
        data_list.load_from_file()

    # If records are still None after attempting to load, inform the user
    if data_list.records is None:
        print("No data found. Unable to load records.")
        return

    # Check if the movie already exists in the records
    existing_record = next((record for record in data_list.records if record.title == title and (record.year == year if year else True)), None)

    if existing_record:
        result = existing_record
    else:
        # Fetch movie details from TMDB
        result = data_list.get_movie_details(title)
        if result not in ["No results found", "Error fetching detailed movie information", "Error searching for movie"]:
            # Convert TMDB data to MediaRecord and add to data_list
            media_record = data_list.tmdb_to_media_record(result)
            data_list.add_record(media_record)  # Add the new record
            data_list.save_to_file()

    # Pretty print or regular print the result
    if pretty_print:
        pprint(result)
    else:
        print(result)

if __name__ == "__main__":
    main()
