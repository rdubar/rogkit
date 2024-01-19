import os

# Define the path for your database
script_dir = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(script_dir, 'media_library.db')
db_url = f'sqlite:///{db_path}'

additional_media_csv = os.path.join(script_dir, 'media.csv')