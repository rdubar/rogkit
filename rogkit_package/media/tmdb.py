import requests
import argparse
import json
import dataclasses
import os
import time
from ..bin.tomlr import load_rogkit_toml
from .plex_library import get_media_list
from .media_settings import tmdb_data_file
from ..bin.seconds import convert_seconds

def get_tbdm_toml():
    toml = load_rogkit_toml()
    return toml.get('tmdb', {})

@dataclasses.dataclass
class DataList:
    info_dict: dict = dataclasses.field(default_factory=dict)
    data_file: str = tmdb_data_file

    def save_to_file(self):
        # Convert the dataclass to a dictionary before saving
        with open(self.data_file, 'w') as f:
            json.dump(dataclasses.asdict(self), f) 
        print(f"Saved {len(self.info_dict)} titles to {self.data_file}")
    
    def load_from_file(self):
        if not os.path.exists(self.data_file):
            return
        try:
            with open(self.data_file, 'r') as f:
                # Load the data and update the dataclass instance
                loaded_data = json.load(f)
                self.info_dict = loaded_data.get('info_dict', {})
            print(f"Loaded {len(self.info_dict)} titles from {self.data_file}")
        except:
            print(f"Error loading data from {self.data_file}")
    
    def add_list(self, title_list):
        clock = time.perf_counter()
        if isinstance(title_list, str):
            title_list = [title_list]
        added = 0
        skipped = 0
        not_found = 0
        for number, title in enumerate(title_list):
            info = f'[{number+1}/{len(title_list)}]'
            if title in self.info_dict:
                print(f'{info} Skipped {title}')
                skipped += 1
            else:
                details = get_movie_details(title)
                if details == "No results found":
                    print(f'{info} Could not find {title}')
                    not_found += 1
                else:
                    print(f'{info} Added {title}')
                    self.info_dict[title] = details
                    added += 1
        if skipped:
            print(f"Skipped {skipped} movies")
        if not_found:
            print(f"Could not find {not_found} movies")
        if added:
            print(f"Added {added} movies")       
            self.save_to_file()
        elapsed = convert_seconds(time.perf_counter() - clock)
        print(f"Elapsed time: {elapsed}")

def get_movie_details(title, api_key=None):

    if not api_key:
        api_key = get_tbdm_toml().get('tmdb_api_key')
    if not api_key:
        return "No TMDb API key found"

    # Replace spaces with '+' for URL encoding
    title = title.replace(' ', '+')

    # TMDb API endpoint for searching movies
    url = f"https://api.themoviedb.org/3/search/movie?api_key={api_key}&query={title}"

    response = requests.get(url)
    if response.status_code == 200:
        results = response.json().get('results', [])
        if results:
            # Assuming the first result is the most relevant one
            movie_id = results[0]['id']
            # Fetch detailed information about the movie
            detailed_url = f"https://api.themoviedb.org/3/movie/{movie_id}?api_key={api_key}"
            detailed_response = requests.get(detailed_url)
            if detailed_response.status_code == 200:
                return detailed_response.json()
            else:
                return "Error fetching detailed movie information"
        else:
            return "No results found"
    else:
        return "Error searching for movie"

def get_args():
    parser = argparse.ArgumentParser(description='Get movie details from TMDb')
    parser.add_argument('-m', '--media', help='Process the media list', action='store_true')
    parser.add_argument('-d', '--delete', help='Delete the matching media', action='store_true')
    parser.add_argument('--api_key', help='TMDb API key', default=None)
    args, search_terms = parser.parse_known_args()
    return args, ' '.join(search_terms)

def main():
    print("Rogkit TMDB tool")
    args, search_terms = get_args()

    data_list = DataList()
    data_list.load_from_file()

    if args.delete:
        if search_terms in data_list.info_dict:
            del data_list.info_dict[search_terms]
            data_list.save_to_file()
            print(f"Deleted {search_terms}")
        else:
            print(f"{search_terms} not found")
        return

    if args.media:
        media_list = get_media_list()
        print(f'Found {len(media_list):,} titles in Plex library')
        data_list.add_list(media_list)
        data_list.save_to_file()
        return


    if search_terms:
        if search_terms in data_list.info_dict:
            print(data_list.info_dict[search_terms])
        else:
            result = get_movie_details(search_terms, args.api_key)
            data_list.info_dict[search_terms] = result
            data_list.save_to_file()
            print(result)
    else:
        print("No search terms provided")


if __name__ == "__main__":
    main()
