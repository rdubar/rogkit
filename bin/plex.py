#!/usr/bin/env python3
import dataclasses
import os
import argparse
import time
from plexapi.server import PlexServer as PlexAPIServer
from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, Integer, String, or_
from sqlalchemy.orm import sessionmaker, declarative_base
from tqdm import tqdm

load_dotenv()

Base = declarative_base()

@dataclasses.dataclass
class PlexRecord:
    id: int = None
    plex_guid: str = None  # The unique identifier from Plex
    title: str = None
    year: int = None
    rating: float = None
    duration: int = None
    genres: list = dataclasses.field(default_factory=list)
    actors: list = dataclasses.field(default_factory=list)
    directors: list = dataclasses.field(default_factory=list)
    writers: list = dataclasses.field(default_factory=list)
    thumb: str = None
    art: str = None
    summary: str = None
    library: str = None
    section: str = None
    key: str = None
    rating_key: str = None
    guid: str = None
    media_type: str = None
    added_at: str = None
    updated_at: str = None
    viewed_at: str = None
    last_viewed_at: str = None
    originally_available_at: str = None
    
    def __post_init__(self):
        self.genres = ', '.join(str(genre) for genre in self.genres) if self.genres else ''
        self.actors = ', '.join(str(actor) for actor in self.actors) if self.actors else ''
        self.directors = ', '.join(str(director) for director in self.directors) if self.directors else ''
        self.writers = ', '.join(str(writer) for writer in self.writers) if self.writers else ''

    def __str__(self):
        # Customize the string representation of PlexRecord
         year = f" ({self.year})" if self.year else ""
         return f"{self.title}{year}"

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
    added_at = Column(String)
    updated_at = Column(String)
    viewed_at = Column(String)
    last_viewed_at = Column(String)
    originally_available_at = Column(String)

    def __str__(self):
        # Customize the string representation of PlexRecord
         year = f" ({self.year})" if self.year else ""
         return f"{self.title}{year}"

engine = create_engine('sqlite:///plexlibrary.db')
Session = sessionmaker(bind=engine)
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
    plex_server: PlexServer = None
    libraries: list = dataclasses.field(init=False, default_factory=list)
    sections: list = dataclasses.field(init=False, default_factory=list)

    def __post_init__(self):
        if not self.plex_server:
            self.plex_server = PlexServer()

        if self.is_database_empty():
            print("No data found in the database. Populating...")
            self.populate_database()
        else:
            self.load_data_from_db()

    def is_database_empty(self):
        # Check if the database is empty
        count = self.session.query(PlexRecordORM).count()
        return count == 0

    def load_data_from_db(self):
        self.libraries = self.session.query(PlexRecordORM).all()    

    def reset_database(self):
        # Clear existing data
        self.session.query(PlexRecordORM).delete()
        # Repopulate database
        self.populate_database()

    def update_database(self):
        print('Updating database with Plex library data...')
        clock = time.perf_counter()
        possible_attributes = get_possible_attributes()
        libraries = self.get_libraries()
        for library in tqdm(libraries, desc="Processing libraries"):
            for item in tqdm(library.all(), desc=f"Processing items in {library.title}"):
                attributes = {attr: self.process_list(getattr(item, attr, None)) 
                            for attr in possible_attributes if hasattr(item, attr)}
                self.update_or_create_record(attributes)
        clock = time.perf_counter() - clock
        total_records = self.session.query(PlexRecordORM).count()
        print(f'Found {total_records:,} records in {clock:.2f} seconds.')

    def update_or_create_record(self, attributes):
        # Using 'plex_guid' from Plex as the unique identifier
        record = self.session.query(PlexRecordORM).filter_by(plex_guid=attributes['guid']).first()
        if record:
            # Update existing record
            for attr, value in attributes.items():
                setattr(record, attr, value)
        else:
            # Create new record
            attributes['plex_guid'] = attributes['guid']
            record = PlexRecordORM(**attributes)
            self.session.add(record)
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
            return ', '.join(str(item) for item in value if item is not None)
        elif callable(value):
            # If the value is a method or callable, ignore it or transform it appropriately
            return None
        return value

    def populate_database(self):
        print('Populating database with Plex library data...')
        clock = time.perf_counter()
        possible_attributes = get_possible_attributes()
        libraries = self.get_libraries()
        for library in tqdm(libraries, desc="Processing libraries"):
            for item in tqdm(library.all(), desc=f"Processing items in {library.title}"):
                attributes = {attr: self.process_list(getattr(item, attr, None)) 
                            for attr in possible_attributes if hasattr(item, attr)}
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
    
    def search(self, text):
        search_pattern = f"%{text.lower()}%"
        return self.session.query(PlexRecordORM).filter(
            or_(
                PlexRecordORM.title.ilike(search_pattern),
                PlexRecordORM.genres.ilike(search_pattern),
                PlexRecordORM.actors.ilike(search_pattern),
                PlexRecordORM.directors.ilike(search_pattern),
                PlexRecordORM.summary.ilike(search_pattern),
                # Add other fields as necessary
            )
        ).all()
    
    def latest(self, number=10):
        return self.session.query(PlexRecordORM).order_by(PlexRecordORM.added_at.desc()).limit(number).all()

    
def process_arguments():
    parser = argparse.ArgumentParser(description='Process arguments')
    parser.add_argument('-u', '--update', action='store_true', help='Update database')
    parser.add_argument('-r', '--reset', action='store_true', help='Reset database')
    parser.add_argument('-l', '--latest', action='store_true', help='Latest additions')
    parser.add_argument('-n', '--number', type=int, default=10, help='Number of results to return')
    args, search_terms = parser.parse_known_args()
    return args, ' '.join(search_terms)


def main():
    args, search_text = process_arguments()
    plex_library = PlexLibrary(plex_server=PlexServer())

    if args.reset:
        plex_library.reset_database()
    elif args.update:
        plex_library.update_database()
    elif args.latest:
        results = plex_library.latest(number=args.number)
        print(f"Showing {len(results):,} lasest additions:")
        for result in results:
            print(result)
    elif search_text:
        results = plex_library.search(search_text)
        print(f"Found {len(results):,} results for '{search_text}':" )
        for result in results:
            print(result)  # or print other relevant fields
    else:
        results = plex_library.latest(number=args.number)
        print(f"Showing {len(results):,} lasest additions:")
        for result in results:
            print(result)        


if __name__ == "__main__":
    main()
