#!/usr/bin/env python3
import dataclasses
import os
import time
import csv
from typing import List

from tqdm import tqdm
from sqlalchemy import func, text, or_

from .plex_server import PlexServer
from .media_records import PlexRecordORM, PlexRecord, common_schema, get_possible_attributes 
from .database_utils import Base, engine, Session, update_database_schema
from .media_settings import additional_media_csv
from .tmdb import DataList
from ..bin.seconds import convert_seconds


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
        attributes['thumb'] = item.thumb if hasattr(item, 'thumb') else None
        attributes['art'] = item.art if hasattr(item, 'art') else None
        
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
    
    def populate_database(self, update_changed_only=False):
        self.connect_to_plex()
        if not self.plex_server or not self.plex_server.connection:
            raise Exception("Plex server is not connected. Cannot populate database.")
        self.load_additional_media()
        print('Populating database with Plex library data...')
        clock = time.perf_counter()
        possible_attributes = get_possible_attributes()
        libraries = self.get_libraries()

        record_batch = []
        for library in libraries:
            for item in tqdm(library.all(), desc=f"Processing items in {library.title}"):
                attributes = self._process_attributes(item, possible_attributes, library)
                if update_changed_only:
                    existing_record = self.session.query(PlexRecordORM).filter_by(plex_guid=attributes['plex_guid']).first()
                    # Compare video resolution to determine if the record has changed
                    if existing_record and existing_record.resolution == attributes['resolution']:
                        continue  # Skip this record as its resolution hasn't changed
                record = PlexRecord(**attributes)
                record_batch.append(record)

        if record_batch:
            try:
                self.save_record_batch_to_db(record_batch)
            except Exception as e:
                print(f"Error saving record batch to database: {e}")

        total_records = self.session.query(PlexRecordORM).count()
        print(f'Found {total_records:,} records in {time.perf_counter() - clock:.2f} seconds.') 

    def save_record_batch_to_db(self, records: List[PlexRecord]):
        try:
            # Convert each PlexRecord in the list to a PlexRecordORM object
            orm_records = [PlexRecordORM(**dataclasses.asdict(record)) for record in records]
            
            # Add all ORM records to the session
            self.session.add_all(orm_records)
            
            # Commit the session once after adding all records
            self.session.commit()
        except Exception as e:
            print(f"Error saving record batch to database: {e}")
            # Roll back the session if an error occurs
            self.session.rollback()

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

    def load_additional_media(self, tmdb=True):
        try:
            media = self._load_csv_to_dict(additional_media_csv)
        except Exception as e:
            print(f"Error loading additional media: {e}")
            return
        
        if tmdb:
            tmdb_object = DataList()
            tmdb_object.load_from_file()
            print(f"Loaded {len(tmdb_object.records)} records from {tmdb_object.data_file}")
            possible_attributes = get_possible_attributes()

        updated = 0
        loaded = 0

        for item in media:
            # Ensure all required fields are present, set to None if missing
            for field in PlexRecord.__annotations__.keys():
                item.setdefault(field, None)

            # Convert 'extras' to boolean
            item['extras'] = item.get('extras', 'False').lower() == 'true'

            # Fetch TMDB data if needed
            tmdb_data = tmdb_object.get_media_record(item['title'], item['year']) if tmdb else None
            if tmdb_data:
                print(f"Found TMDB data for {item['title']} ({item['year']})")

            # Check for existing record
            existing = self.session.query(PlexRecordORM).filter_by(platform=item['platform'], title=item['title']).first()
            if existing:
                # Update existing record
                for key in PlexRecord.__annotations__:
                    if key in ['platform', 'resolution']:
                        # Prioritize CSV data for platform and resolution
                        value = item.get(key)
                    else:
                        # Use TMDB data if available, otherwise use CSV data
                        value = tmdb_data.get(key) if tmdb_data and key in tmdb_data else item.get(key)
                    if value is not None:
                        setattr(existing, key, value)
                updated += 1
            else:
                # Prepare new record
                new_record_data = {key: item[key] for key in PlexRecordORM.__table__.columns.keys()}
                if tmdb_data:
                    for key, value in tmdb_data.items():
                        if key in possible_attributes and hasattr(PlexRecordORM, key) and key not in ['platform', 'resolution', 'extras']:
                            new_record_data[key] = value

                new_record = PlexRecordORM(**new_record_data)
                self.session.add(new_record)
                loaded += 1

            # Commit after each record update/addition
            try:
                self.session.commit()
            except Exception as e:
                print(f"Error committing changes for {item['title']} ({item['year']}): {e}")
                self.session.rollback()

        print(f'Updated {updated} existing items and loaded {loaded} new items from {additional_media_csv}')

        if updated and tmdb:
            tmdb_object.save_to_file()


    def title_list(self, plex=False):
        if plex:
            return [record.title for record in self.session.query(PlexRecordORM).all()]
        else:
            # exclude titles with no plex_guida
            return [(x.title, x.year) for x in self.session.query(PlexRecordORM).filter(PlexRecordORM.plex_guid == None).all()]
        # return [
        #     f"{record.title} {record.year if record.year else ''}".strip()
        #     for record in self.session.query(PlexRecordORM).all()
        # ]

    def update_test(self):
        print("Checking for updates. Please allow 10-20 seconds...")
        clock = time.perf_counter()
        try:
            database_date = self.session.query(func.max(PlexRecordORM.updated_at)).scalar()
        except Exception as e:
            print(f"Error getting database date: {e}")
            return
        print(f"Database date: {database_date}")
        # get time in seconds since database_date
        seconds_ago = convert_seconds(time.time() - database_date.timestamp())
        print(f'Last update was {seconds_ago} ago.')

        self.connect_to_plex()
        libraries = self.get_libraries()
        # show name and updated date of anything that has changed since database_date
        total = 0
        updated = []
        new = []
        for library in libraries:
            print(f"Checking library: {library.title}: {len(library.all()):,} items")
            for item in library.all():
                total += 1
                if hasattr(item, 'updatedAt') and item.updatedAt is not None and item.updatedAt > database_date:
                    print(f"  {item.title} - {item.updatedAt}")
                    # uppdate that single item in the database
                    # Process attributes
                    attributes = self._process_attributes(item, get_possible_attributes(), library)

                    # Check if record exists, then update or insert
                    existing_record = self.session.query(PlexRecordORM).filter_by(plex_guid=attributes['plex_guid']).first()
                    if existing_record:
                        # Update existing record
                        for key, value in attributes.items():
                            if value is not None:  # Skip attributes that are None
                                setattr(existing_record, key, value)
                        updated.append((item.title, item.updatedAt))
                    else:
                        # Insert new record
                        record = PlexRecord(**attributes)
                        self.save_record_to_db(record)
                        print(f"Added new record for {item.title}")
                        new.append(item.title)

        if new or updated:
            self.session.commit()
            if new:
                print(f"Added {len(new):,} new records:")
                [print(x) for x in new]
            if updated:
                print(f"Updated {len(updated):,}:")
                [print(f'{x[0]} : {x[1]}') for x in updated]
        report = f"New : {len(new):,} " if new else ""
        report += f"Updated : {len(updated):,} " if updated else ""
        report += f"Total: {total:,}"
        clock = time.perf_counter() - clock
        if not (updated or new):
            print("No updates found.")
        print(f"{report} records checked in {clock:.2f} seconds.")


def get_media_list():
    library = PlexLibrary()
    return library.title_list()