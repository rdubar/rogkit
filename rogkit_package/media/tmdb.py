import requests
import argparse

from ..bin.tomlr import load_rogkit_toml

def get_tbdm_toml():
    toml = load_rogkit_toml()
    return toml.get('tmdb', {})

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
    parser.add_argument('--api_key', help='TMDb API key', default=None)
    args, search_terms = parser.parse_known_args()
    return args, ' '.join(search_terms)

def main():
    args, search_terms = get_args()
    print(get_movie_details(search_terms, args.api_key))

if __name__ == "__main__":
    main()
