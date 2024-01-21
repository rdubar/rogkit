#!/usr/bin/env python3
import dataclasses
import os
import time
import csv

from tqdm import tqdm
from sqlalchemy import func, text, or_

from .plex_server import PlexServer
from .media_records import PlexRecordORM, PlexRecord, common_schema, get_possible_attributes 
from .database_utils import Base, engine, Session, update_database_schema
from .media_settings import additional_media_csv


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
        try:
            self.session.execute(text("SELECT 1 FROM plex_records LIMIT 1"))
        except Exception as e:
            print(f"Database error encountered: {e}")
            print("Reinitializing database schema...")
            update_database_schema(engine)

    def load_data_from_db(self):
        try:
            self.libraries = self.session.query(PlexRecordORM).all()
        except Exception as e:
            print(f"Error loading data from database: {e}")
            print("Attempting to reset and populate the database...")
            self.reset_database()

    def reset_database(self):
        try:
            # Close the current session to clear any existing session state
            self.session.close()
            # Drop all existing data
            Base.metadata.drop_all(engine)
            # Recreate the tables
            Base.metadata.create_all(engine)
            # Create a new session for the next operations
            self.session = Session()
            # Repopulate the database
            self.populate_database()
        except Exception as e:
            print(f"Critical error resetting the database: {e}")
            raise

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
    
    def test_connection(self):
        self.connect_to_plex()
        libraries = self.get_libraries()
        for library in libraries:
            print(f"Library: {library.title}")
            for item in library.all():
                if hasattr(item, 'media'):
                    media = item.media[0]
                    if hasattr(media, 'parts'):
                        part = media.parts[0]
                        print(f"  {item.title} - {part.file} - {part.size}")
                        size = getattr(part, 'size', None) 
                        print(size)
        return libraries
    
    def _process_attributes(self, item, possible_attributes, library):
        attributes = {attr: self.process_list(getattr(item, attr, None)) 
                    for attr in possible_attributes if hasattr(item, attr)}
        for key in common_schema.keys():
            attributes.setdefault(key, None)
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

            if hasattr(media, 'parts'):
                part = media.parts[0]
                attributes['size'] = getattr(part, 'size', None)   

        # get the file size from parts
        if hasattr(item, 'parts'):
            part = item.parts[0]  # Assuming we take the first part
            attributes['size'] = getattr(part, 'size', None)
            
        return attributes

    def populate_database(self):
        self.connect_to_plex()
        self.load_additional_media()
        if not self.plex_server or not self.plex_server.connection:
            raise Exception("Plex server is not connected. Cannot populate database.")
        print('Populating database with Plex library data...')
        possible_attributes = get_possible_attributes()
        clock = time.perf_counter()
        libraries = self.get_libraries()
        print(f"Retrieved {len(libraries):,} libraries in {time.perf_counter() - clock:.2f} seconds.")
        clock = time.perf_counter()
        for library in libraries:  # Loop over each library
            for item in tqdm(library.all(), desc=f"Processing items in {library.title}"):
                attributes = self._process_attributes(item, possible_attributes, library)
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
        # Find duplicates based on 'plex_guid' but ignore records with no plex_guid
        duplicates = self.session.query(PlexRecordORM.plex_guid).filter(PlexRecordORM.plex_guid != None).group_by(PlexRecordORM.plex_guid).having(func.count() > 1).all()
        removed = 0
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
                PlexRecordORM.writers.ilike(search_pattern),
                PlexRecordORM.summary.ilike(search_pattern),
                PlexRecordORM.full_title.ilike(search_pattern),
                PlexRecordORM.platform.ilike(search_pattern),
                PlexRecordORM.library.ilike(search_pattern),
                PlexRecordORM.section.ilike(search_pattern),
                PlexRecordORM.resolution.ilike(search_pattern),
                # Add other fields as necessary
            )
        ).all()

    
    @staticmethod
    def _load_csv_to_dict(file_path):
        with open(file_path, mode='r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            return [row for row in reader]  # This creates a list of dictionaries

    def load_additional_media(self):
        try:
            media = self._load_csv_to_dict(additional_media_csv)
        except Exception as e:
            print(f"Error loading additional media: {e}")
            return
        updated = 0
        loaded = 0

        for item in media:
            # Ensure all required fields are present, set to None if missing
            for field in PlexRecord.__annotations__.keys():
                item.setdefault(field, None)

            existing = self.session.query(PlexRecordORM).filter_by(platform=item['platform'], title=item['title']).first()
            if existing:
                # Update existing record
                for key, value in item.items():
                    if key in PlexRecord.__annotations__:  # Update only if the key is a valid field
                        setattr(existing, key, value)
                self.session.commit()
                updated += 1
            else:
                # Create and add new record
                item['extras'] = item.get('extras', 'False').lower() == 'true'
                record = PlexRecord(**item)
                self.save_record_to_db(record)
                loaded += 1

        print(f'Updated {updated} existing items and loaded {loaded} new items from {additional_media_csv}')
