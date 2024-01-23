import requests
import argparse
import json
import dataclasses
import os
import time
import hashlib
from pprint import pprint
from ..bin.tomlr import load_rogkit_toml
from .plex_library import get_media_list
from .media_settings import tmdb_data_file
from .media_records import common_schema
from ..bin.seconds import convert_seconds

def get_tbdm_toml():
    toml = load_rogkit_toml()
    return toml.get('tmdb', {})

def generate_hash(data):
    data_string = json.dumps(data, sort_keys=True)
    hash_object = hashlib.sha256()
    hash_object.update(data_string.encode())
    return hash_object.hexdigest()

@dataclasses.dataclass
class DataList:
    info_dict: dict = dataclasses.field(default_factory=dict)
    data_file: str = tmdb_data_file
    api_key: str = None

    def __post_init__(self):
        self.api_key = get_tbdm_toml().get('tmdb_api_key', None)

    def save_to_file(self):
        with open(self.data_file, 'w') as f:
            json.dump(dataclasses.asdict(self), f) 
        print(f"Saved {len(self.info_dict)} titles to {self.data_file}")
    
    def load_from_file(self):
        if not os.path.exists(self.data_file):
            return
        try:
            with open(self.data_file, 'r') as f:
                loaded_data = json.load(f)
                self.info_dict = loaded_data.get('info_dict', {})
            print(f"Loaded {len(self.info_dict)} titles from {self.data_file}")
        except Exception as e:
            print(f"Error loading data from {self.data_file}: {e}")
    
    def add_list(self, title_list):
        clock = time.perf_counter()
        if isinstance(title_list, str):
            title_list = [title_list]
        added, skipped, not_found = 0, 0, 0
        for number, title in enumerate(title_list):
            info = f'[{number+1}/{len(title_list)}]'
            title_hash = generate_hash(title)
            if title_hash in self.info_dict:
                print(f'{info} Skipped {title}')
                skipped += 1
            else:
                details = self.get_movie_details(title)  
                if details == "No results found":
                    print(f'{info} Could not find {title}')
                    not_found += 1
                else:
                    print(f'{info} Added {title}')
                    self.info_dict[title_hash] = details
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
        
    def tmdb_to_media_record(tmdb_dict):
        record = []
        for value in common_schema.values():
            if value in tmdb_dict:
                record.append(tmdb_dict[value]) 
        record['summary'] = tmdb_dict['overview']
        record['genres'] = ', '.join([genre['name'] for genre in tmdb_dict['genres']])
        record['actors'] = ', '.join([actor['name'] for actor in tmdb_dict['actors']])
        record['directors'] = ', '.join([director['name'] for director in tmdb_dict['directors']])
        record['writers'] = ', '.join([writer['name'] for writer in tmdb_dict['writers']])
        record['duration'] = tmdb_dict['runtime'] * 60
        record['resolution'] = tmdb_dict['resolution']
        record['thumb'] = tmdb_dict['poster_path']
        record['art'] = tmdb_dict['backdrop_path']
        record['originally_available_at'] = tmdb_dict['release_date']
        record['rating_key'] = tmdb_dict['vote_average']
        return record

def get_args():
    parser = argparse.ArgumentParser(description='Get movie details from TMDb')
    parser.add_argument('-m', '--media', help='Process the media list', action='store_true')
    parser.add_argument('-d', '--delete', help='Delete the matching media', action='store_true')
    parser.add_argument('-p', '--pretty', help='Pretty print the output', action='store_true')
    parser.add_argument('--api_key', help='TMDb API key', default=None)
    args, search_terms = parser.parse_known_args()
    return args, ' '.join(search_terms)

def main():
    print("Rogkit TMDB tool")
    args, search_terms = get_args()

    data_list = DataList()
    data_list.load_from_file()

    if args.delete:
        # Use hash of search_terms to check for existence and deletion
        search_hash = generate_hash(search_terms)
        if search_hash in data_list.info_dict:
            del data_list.info_dict[search_hash]
            data_list.save_to_file()
            print(f"Deleted {search_terms}")
        else:
            print(f"{search_terms} not found")
        return

    if args.media:
        media_list = get_media_list()
        print(f'Found {len(media_list):,} titles in Plex library')
        data_list.add_list(media_list)
        return

    if search_terms:
        search_hash = generate_hash(search_terms)
        if search_hash in data_list.info_dict:
            print(data_list.info_dict[search_hash])
        else:
            result = data_list.get_movie_details(search_terms)
            if result not in ["No results found", "Error fetching detailed movie information", "Error searching for movie"]:
                data_list.info_dict[search_hash] = result
                data_list.save_to_file()
            if args.pretty:
                pprint(result)
            else:
                print(result)
    else:
        print("No search terms provided")

if __name__ == "__main__":
    main()