#!/usr/bin/env python3
import dataclasses
import os
import argparse
import time
import datetime
import csv

from plexapi.server import PlexServer as PlexAPIServer
from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, Integer, Boolean, String, or_, func, DateTime, Integer
from sqlalchemy import text
from sqlalchemy_utils import database_exists, create_database

from sqlalchemy.orm import sessionmaker, declarative_base
from tqdm import tqdm
from ..bin.seconds import convert_seconds

load_dotenv()

Base = declarative_base()

script_dir = os.path.dirname(os.path.abspath(__file__))  # Get the directory of the current script
db_path = os.path.join(script_dir, 'plexlibrary.db')  # Construct the path to the database file
engine = create_engine(f'sqlite:///{db_path}')  # Use the full path for the database
Session = sessionmaker(bind=engine)
Base.metadata.create_all(engine)

def initialize_database(engine, Base):
    """
    Initialize the database: create the database and tables if they don't exist.
    """
    if not database_exists(engine.url):
        create_database(engine.url)
    Base.metadata.create_all(engine)

@dataclasses.dataclass
class PlexRecord:
    id: int = None
    plex_guid: str = None  # The unique identifier from Plex
    title: str = None
    year: int = None
    rating: float = None
    duration: int = None
    genres: str = None
    actors: str = None
    directors: str = None
    writers: str = None
    thumb: str = None
    art: str = None
    summary: str = None
    library: str = None
    section: str = None
    key: str = None
    rating_key: str = None
    guid: str = None
    media_type: str = None
    added_at: datetime.datetime = None
    updated_at: datetime.datetime = None
    viewed_at: datetime.datetime = None
    last_viewed_at: datetime.datetime = None
    originally_available_at: str = None
    platform: str = None
    full_title: str = None
    extras: bool = None
    resolution: str = None
    bitrate: int = None
    codec: str = None

    def __post_init__(self):
        # Set full_title to 'title (year)' if year is present, otherwise just 'title'
        if self.year:
            self.full_title = f"{self.title} ({self.year})"
        else:
            self.full_title = self.title

def get_possible_attributes():
    return [f.name for f in dataclasses.fields(PlexRecord)]

@dataclasses.dataclass
class PlexRecordORM(Base):
    __tablename__ = 'plex_records'
    id = Column(Integer, primary_key=True)
    plex_guid = Column(String, unique=True)  # Unique identifier from Plex
    title = Column(String)
    year = Column(Integer)
    rating = Column(Integer)
    duration = Column(Integer)
    genres = Column(String)
    actors = Column(String)
    directors = Column(String)
    writers = Column(String)
    summary = Column(String)
    library = Column(String)
    thumb = Column(String)
    art = Column(String)
    section = Column(String)
    key = Column(String)
    rating_key = Column(String)
    guid = Column(String)
    media_type = Column(String)
    added_at = Column(DateTime)
    updated_at = Column(DateTime)
    viewed_at = Column(DateTime)
    last_viewed_at = Column(DateTime)
    originally_available_at = Column(String)
    platform = Column(String)
    full_title = Column(String)
    extras = Column(Boolean)
    resolution = Column(String)
    bitrate = Column(Integer)
    codec = Column(String)

    def __str__(self):
        # Customize the string representation of PlexRecord
         year = f" ({self.year})" if self.year else ""
         resolution = f" {self.resolution}" if self.resolution else ""
         return f"{self.platform:7}  {resolution:<6}    {self.title}{year}"


def update_database_schema(engine=engine, Base=Base):
    print("Updating database schema...")
    # Drop all tables
    Base.metadata.drop_all(engine)
    # Create all tables
    Base.metadata.create_all(engine)


@dataclasses.dataclass
class PlexServer:
    url: str = None
    token: str = None
    port: int = None
    connection: PlexAPIServer = dataclasses.field(init=False, default=None)

    def __post_init__(self):
        self.url = self.url or os.environ.get("PLEX_SERVER_URL", "localhost")
        self.token = self.token or os.environ.get("PLEX_SERVER_TOKEN")
        self.port = int(self.port or os.environ.get("PLEX_SERVER_PORT", 32400))
        if not self.url.startswith("http"):
            self.url = f"http://{self.url}"
        self.full_url = f"{self.url}:{self.port}"
        # Establish connection to the Plex server
        self.get_connection()

    def get_connection(self):
        # Ensure the connection is established and return it
        if not self.connection:
            print(f"Connecting to Plex server: {self.url}:{self.port}")
            try:
                self.connection = PlexAPIServer(self.full_url, self.token)
            except Exception as e:
                print(f"Error connecting to Plex server: {e}")
        return self.connection

@dataclasses.dataclass
class PlexLibrary:
    plex_server: PlexServer = None
    session: Session = Session()
    libraries: list = dataclasses.field(init=False, default_factory=list)
    sections: list = dataclasses.field(init=False, default_factory=list)

    def __post_init__(self):
        self.ensure_database_ready()
        self.load_data_from_db()

    def ensure_database_ready(self):
        # Check if the database is properly initialized
        if not self.database_initialized():
            print("Initializing database...")
            initialize_database(engine, Base)  # Function to create and initialize the database
        self.load_data_from_db()

    def database_initialized(self):
        try:
            # Use text() for the raw SQL query
            return self.session.execute(text("SELECT 1 FROM plex_records LIMIT 1")).scalar() is not None
        except Exception as e:
            print(f"Error checking if database is initialized: {e}")
            return False

    def connect_to_plex(self):
        if not self.plex_server:
            self.plex_server = PlexServer()
        if not self.plex_server.connection:
            self.plex_server.get_connection()

    def is_database_empty(self):
        try:
            # Use text() for the raw SQL query
            count = self.session.execute(text("SELECT COUNT(*) FROM plex_records")).scalar()
            return count == 0
        except Exception as e:
            print(f"Error checking if database is empty: {e}")
            return True

    def database_exists(self):
        try:
            # Check if any table exists in the database
            return self.session.execute(text("SELECT 1")).scalar() is not None
        except Exception as e:
            print(f"Error checking if database exists: {e}")
            return False

    def load_data_from_db(self):
        if self.database_exists():
            try:
                self.libraries = self.session.query(PlexRecordORM).all()
            except Exception as e:
                print(f"Error loading data from database: {e}. Resetting database with new schema.")
                update_database_schema()
                self.populate_database()

    def reset_database(self):
        self.session.query(PlexRecordORM).delete()
        self.populate_database()

    def update_database(self):
        if not self.plex_server or not self.plex_server.connection:
            raise Exception("Plex server is not connected. Cannot populate database.")
        print('Updating database with Plex library data...')
        clock = time.perf_counter()
        possible_attributes = get_possible_attributes()
        libraries = self.get_libraries()
        for library in tqdm(libraries, desc="Processing libraries"):
            for item in tqdm(library.all(), desc=f"Processing items in {library.title}"):
                attributes = {attr: self.process_list(getattr(item, attr, None)) 
                            for attr in possible_attributes if hasattr(item, attr)}
                attributes['added_at'] = item.addedAt if hasattr(item, 'addedAt') else None
                attributes['updated_at'] = item.updatedAt if hasattr(item, 'updatedAt') else None
                self.update_or_create_record(attributes)
        clock = time.perf_counter() - clock
        total_records = self.session.query(PlexRecordORM).count()
        print(f'Found {total_records:,} records in {clock:.2f} seconds.')

    def update_or_create_record(self, attributes):
        # Extract plex_guid from attributes, assuming it's always present
        plex_guid = attributes['plex_guid']
        
        # Check for an existing record with the same plex_guid
        record = self.session.query(PlexRecordORM).filter_by(plex_guid=plex_guid).first()
        
        if record:
            # Update existing record
            for attr, value in attributes.items():
                setattr(record, attr, value)
        else:
            # Create a new record
            new_record = PlexRecordORM(**attributes)
            self.session.add(new_record)
        
        # Commit the changes
        self.session.commit()

    def get_libraries(self):
        try:
            self.libraries = self.plex_server.connection.library.sections()
            return self.libraries
        except Exception as e:
            print(f"Error in get_libraries: {e}")
            return None

    def get_sections(self):
        self.sections = []
        for library in self.libraries:
            self.sections.append(library.title)
        return self.sections

    def save_library_to_db(self):
        try:
            for library in self.libraries:
                record = PlexRecordORM(id=library.id, title=library.title)
                self.session.add(record)
            self.session.commit()
        except Exception as e:
            print(f"Error saving to database: {e}")
            self.session.rollback()

    @staticmethod
    def process_list(value):
        if isinstance(value, list):
            return ', '.join(item.tag if hasattr(item, 'tag') else item.role for item in value)
        return value

    def populate_database(self):
        self.connect_to_plex()
        self.load_additional_media()
        if not self.plex_server or not self.plex_server.connection:
            raise Exception("Plex server is not connected. Cannot populate database.")
        clock = time.perf_counter()
        print('Populating database with Plex library data...')
        possible_attributes = get_possible_attributes()
        libraries = self.get_libraries()
        for library in libraries:  # Loop over each library
            for item in tqdm(library.all(), desc=f"Processing items in {library.title}"):
                attributes = {attr: self.process_list(getattr(item, attr, None)) 
                            for attr in possible_attributes if hasattr(item, attr)}
                attributes['library'] = library.title
                attributes['section'] = library.title 
                attributes['plex_guid'] = getattr(item, 'guid', None)
                attributes['platform'] = 'plex'
                attributes['added_at'] = item.addedAt if hasattr(item, 'addedAt') else None
                attributes['updated_at'] = item.updatedAt if hasattr(item, 'updatedAt') else None
                attributes['extras'] = hasattr(item, 'extras')
                
                # Extract video media information
                if hasattr(item, 'media'):
                    media = item.media[0]  # Assuming we take the first media object
                    attributes['resolution'] = f"{media.videoResolution}"  
                    attributes['bitrate'] = media.bitrate
                    attributes['codec'] = media.videoCodec
                    if attributes['codec'] == 'mpeg2video':
                        attributes['resolution'] += '*'

                record = PlexRecord(**attributes)
                self.save_record_to_db(record)
        
        clock = time.perf_counter() - clock
        total_records = self.session.query(PlexRecordORM).count()
        print(f'Found {total_records:,} records in {clock:.2f} seconds.')

    def save_record_to_db(self, record: PlexRecord):
        try:
            orm_record = PlexRecordORM(**dataclasses.asdict(record))
            self.session.add(orm_record)
            self.session.commit()
        except Exception as e:
            print(f"Error saving record to database: {e}")
            self.session.rollback()

    def remove_duplicates(self):
        # Find duplicates based on 'plex_guid'
        removed = 0
        duplicates = self.session.query(PlexRecordORM.plex_guid).group_by(PlexRecordORM.plex_guid).having(func.count() > 1).all()
        for dup in duplicates:
            # Keep only the first record and remove others
            dup_records = self.session.query(PlexRecordORM).filter_by(plex_guid=dup.plex_guid).all()
            for record in dup_records[1:]:
                self.session.delete(record)
                removed += 1
        self.session.commit()
        return removed

    
    def search(self, text):
        search_pattern = f"%{text.lower()}%"
        return self.session.query(PlexRecordORM).filter(
            or_(
                PlexRecordORM.title.ilike(search_pattern),
                PlexRecordORM.year.ilike(search_pattern),
                PlexRecordORM.genres.ilike(search_pattern),
                PlexRecordORM.actors.ilike(search_pattern),
                PlexRecordORM.directors.ilike(search_pattern),
                PlexRecordORM.summary.ilike(search_pattern),
                PlexRecordORM.full_title.ilike(search_pattern),
                # Add other fields as necessary
            )
        ).all()
    
    def latest(self, number=10):
        return self.session.query(PlexRecordORM).order_by(PlexRecordORM.added_at.desc()).limit(number).all()
    
    def sort_by_video_resolution(self, number=10, reverse=True):
        return sorted(self.libraries, key=lambda x: x.resolution, reverse=reverse)[:number]
    
    @staticmethod
    def _load_csv_to_dict(file_path):
        with open(file_path, mode='r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            return [row for row in reader]  # This creates a list of dictionaries

    def load_additional_media(self):
        data_file = os.path.join(script_dir, 'data/media.csv')
        try:
            media = self._load_csv_to_dict(data_file)
        except Exception as e:
            print(f"Error loading additional media: {e}")
            return
        updated = 0
        loaded = 0

        for item in media:
            existing = self.session.query(PlexRecordORM).filter_by(platform=item['platform'], title=item['title']).first()
            if existing:
                # Update existing record
                for key, value in item.items():
                    if key in ['extras']:  # Add other fields as needed
                        setattr(existing, key, value)
                self.session.commit()
                updated += 1
            else:
                # Create and add new record
                item['extras'] = True if item.get('extras', 'False').lower() == 'true' else False
                record = PlexRecord(**item)
                self.save_record_to_db(record)
                loaded += 1

        print(f'Updated {updated} existing items and loaded {loaded} new items from {data_file}')



def process_arguments():
    parser = argparse.ArgumentParser(description='Process arguments')

    # Database management options
    parser.add_argument('--update', action='store_true', help='Update database')
    parser.add_argument('-R', '--reset', action='store_true', help='Reset database')
    parser.add_argument('-D', '--duplicates', action='store_true', help='Remove duplicates')

    # Display options
    parser.add_argument('-a', '--all', action='store_true', help='Show all records')
    parser.add_argument('-d', '--dvd', action='store_true', help='Show uncompressed DVDs')
    parser.add_argument('-l', '--latest', action='store_true', help='Show latest additions')
    parser.add_argument('-s', '--summary', action='store_true', help='Show a summary for each title')
    parser.add_argument('-n', '--number', type=int, default=10, help='Number of results to return')
    parser.add_argument('-r', '--resolution', action='store_true', help='Sort by resolution')
    parser.add_argument('-y', '--year', action='store_true', help='Sort by year of release') 

    # Mode options
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose mode')
    parser.add_argument('--debug', action='store_true', help='Debug mode')
    parser.add_argument('--schema', action='store_true', help='Update database schema')

    args, search_terms = parser.parse_known_args()
    return args, ' '.join(search_terms)

def main():
    print("Rog's Plex Library Utility")
    args, search_text = process_arguments()

    plex_library = PlexLibrary()

    if args.reset or args.update:
        plex_library.connect_to_plex()

    if args.reset:
        confirm = input("Resetting the database will delete all records. Are you sure? (y/n)")
        if not confirm.lower() in ['y', 'yes']:
            print("Aborting reset.")
            return
        update_database_schema()
        plex_library.reset_database()
    elif args.update:
        plex_library.update_database()

    if args.duplicates: 
        removed = plex_library.remove_duplicates()
        print(f"Removed {removed:,} duplicates.") 

    total_records = plex_library.session.query(PlexRecordORM).count()

    if args.all:
        results = plex_library.libraries
    elif search_text:
        results = plex_library.search(search_text)
        print(f"Found {len(results):,} results in {total_records:,} total records for '{search_text}':" )
    else:
        results = plex_library.latest(number=args.number)
        print(f"Showing {len(results):,} latest updates from {total_records:,} total records:")
    if results:

        if args.dvd:
            print("Filtering for uncompressed DVDs...")
            results = [result for result in results if result.codec == 'mpeg2video']

        if args.year:
            print("Sort by year...")
            results = sorted(results, key=lambda x: x.year, reverse=True)
        

        def sort_by_resolution(results):
            resolutions = {'4k': 2160, '1080p': 1080, '720p': 720, 'hd': 1080, '480p': 480, 'sd': 480}

            def resolution_to_int(result):
                res_string = result.resolution.lower() if result.resolution else ''
                res_string = res_string.replace('*', '')  # Remove star marker
                # Extract resolution from the string (e.g., "1080p" -> "1080")
                numeric_res = ''.join(filter(str.isdigit, res_string))
                # Check if resolution is directly in the dictionary
                if res_string in resolutions:
                    return resolutions[res_string]
                # Check if numeric resolution is in the dictionary
                elif numeric_res in resolutions:
                    return resolutions[numeric_res]
                # Handle cases like "576" which are not in the dictionary but are numeric
                elif numeric_res.isdigit():
                    return int(numeric_res)
                # Default case
                else:
                    return 0

            return sorted(results, key=resolution_to_int, reverse=True)

        # In your main function or wherever you process the search results:
        if args.resolution:
            print("Sorting by video resolution...")
            results = sort_by_resolution(results)

        for result in results:
            print(result)  
            if args.summary:
                print(result.summary)
            if args.verbose:
                print(vars(result))      
        # get the total duration of all results
        total_duration = convert_seconds((sum([result.duration for result in results if result.duration]) or 0) / 1000)
        print(f"{len(results):,} items, {total_duration}")

    if args.debug and results:
        print(f"First result: {results[0]}")
        print(vars(results[0]))

    if args.debug and results:
        print(f"First result: {results[0]}")
        print(vars(results[0]))
        print(results[0].codec)


if __name__ == "__main__":
    main()