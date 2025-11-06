"""
Media list utilities for loading additional media and TMDB data.

Note: Not currently used in main application.
"""
import json
import csv
from .media_settings import additional_media_csv, tmdb_data_file


def get_tmdb_data():
    """Load TMDB data from JSON file."""
    with open(tmdb_data_file) as f:
        return json.load(f)

def get_additional_media():
    """Load additional media list from CSV file."""
    with open(additional_media_csv, encoding='utf-8') as f:
        return f.read().splitlines()
    
def load_csv_to_dict(file_path):
    """Load CSV file into list of dictionaries."""
    with open(file_path, mode='r', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        return [row for row in reader]  # This creates a list of dictionaries

def process():
    """Test function to process and display additional media and TMDB data."""
    additional_media = load_csv_to_dict(additional_media_csv)
    tmdb_data = get_tmdb_data()['info_dict']
    print(additional_media[0])
    for item in tmdb_data.values():
        print(item)
        break

    
if __name__ == "__main__":
    process()