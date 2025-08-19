#!/usr/bin/env python3
import dataclasses
import os
import time
import csv
import sys
from typing import List

from tqdm import tqdm
from sqlalchemy import func, text, or_
import pandas as pd

from .plex_server import PlexServer
from .media_records import PlexRecordORM, PlexRecord, common_schema, get_possible_attributes 
from .database_utils import Base, engine, Session, update_database_schema
from .media_settings import additional_media_csv, db_df_path
from .tmdb import DataList
from ..bin.seconds import convert_seconds

from thefuzz import fuzz, process


@dataclasses.dataclass
class PlexLibrary:
    plex_server: PlexServer = None
    session: Session = Session()
    libraries: list = dataclasses.field(init=False, default_factory=list)
    sections: list = dataclasses.field(init=False, default_factory=list)

    def __post_init__(self):
        self.ensure_database_ready()
        self.load_data_from_db()

    def total_records(self):
        return self.session.query(PlexRecordORM).count()

    def ensure_database_ready(self):
        try:
            # Execute PRAGMA statements for optimization
            self.session.execute(text("PRAGMA journal_mode = WAL"))         # Set journal mode to Write-Ahead Logging for better concurrency
            self.session.execute(text("PRAGMA synchronous = NORMAL"))       # Set synchronous mode to NORMAL to reduce disk I/O overhead
            self.session.execute(text("PRAGMA cache_size = 10000"))         # Increase the cache size to keep more data in memory
            self.session.execute(text("PRAGMA foreign_keys = OFF"))         # Disable foreign key constraints for performance improvement (if not using foreign keys)
            self.session.execute(text("PRAGMA automatic_index = ON"))       # Enable automatic indexing to optimize query performance
            self.session.execute(text("PRAGMA temp_store = MEMORY"))        # Use memory for temporary storage to speed up operations
            self.session.execute(text("PRAGMA page_size = 4096"))           # Increase the page size to 4096 bytes for better performance
            self.session.execute(text("PRAGMA cache_spill = OFF"))          # Disable cache spilling to reduce disk I/O operations
            self.session.execute(text("ANALYZE"))                           # Run ANALYZE to gather statistics for the query planner
            # This lock causes reset to fail        
            # self.session.execute(text("PRAGMA locking_mode = EXCLUSIVE"))   # Set locking mode to EXCLUSIVE to reduce locking overhead

            # Check if the database is ready by executing a simple query
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
            # Log the status
            print("Closing session and disposing engine...")
            # Ensure all sessions are properly closed
            self.session.close()
            engine.dispose()
            
            # Sleep for a short duration to ensure all connections are fully closed
            import time
            time.sleep(1)
            
            # Connect to the database and perform reset operations
            print("Connecting to the database...")
            with engine.connect() as connection:
                try:
                    print("Setting PRAGMA journal_mode=DELETE...")
                    connection.execute(text("PRAGMA journal_mode=DELETE"))
                    connection.execute(text("PRAGMA locking_mode=NORMAL"))
                    connection.execute(text("PRAGMA busy_timeout = 30000"))  # Increase busy timeout to 30 seconds

                    # Log all current database connections for debugging
                    print("Checking for existing database connections...")
                    connections = connection.execute(text("PRAGMA database_list")).fetchall()
                    for conn in connections:
                        print(f"Database connection: {conn}")

                    print("Dropping all tables...")
                    Base.metadata.drop_all(connection)
                    print("Creating all tables...")
                    Base.metadata.create_all(connection)
                    
                except Exception as e:
                    print(f"Error during schema reset: {e}")
                    raise
                finally:
                    print("Restoring PRAGMA journal_mode=WAL...")
                    connection.execute(text("PRAGMA journal_mode=WAL"))
                    connection.execute(text("PRAGMA locking_mode=EXCLUSIVE"))
                    
            print("Creating a new session for the next operations...")
            # Create a new session for the next operations
            self.session = Session()
            print("Populating the database...")
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
                attributes['video_path'] = getattr(part, 'file', None)
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
        from sqlalchemy import func

        # Find duplicates based on title and size (adjust criteria if necessary)
        duplicates = (
            self.session.query(PlexRecordORM.title, PlexRecordORM.size)
            .filter(PlexRecordORM.title != None, PlexRecordORM.size != None)  # Ignore records with missing data
            .group_by(PlexRecordORM.title, PlexRecordORM.size)
            .having(func.count() > 1)
            .all()
        )

        removed = 0
        removed_titles = []  # To store removed titles

        for title, size in duplicates:
            # Fetch duplicate records
            dup_records = (
                self.session.query(PlexRecordORM)
                .filter_by(title=title, size=size)
                .order_by(PlexRecordORM.id)  # Ensure deterministic order
                .all()
            )
            # Keep the first record, delete others
            for record in dup_records[1:]:
                if record.title not in removed_titles:
                    removed_titles.append(record.title)
                self.session.delete(record)
                removed += 1

        self.session.commit()

        # Return the list of removed titles
        return removed_titles

    def search(self, text, fuzzy=90, verbose=False):
        """
        Search in three ways:
        1. General search
        3. Search by title and then (year)
        2. Fuzzy match (as a percentage)
        """
        search_pattern = f"%{text.lower()}%"
        results = self.session.query(PlexRecordORM).filter(
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
                (PlexRecordORM.full_title + ' ' + PlexRecordORM.year).ilike(search_pattern)
            )
        ).all()
        
        if not results:
            # check for a year. e.g. "(2019)" then search for the title without the year, and filter by year
            if text[-5:-1].isdigit():
                title = text[:-6].strip()
                year = text[-5:-1]
                results = self.session.query(PlexRecordORM).filter(
                    or_(
                        PlexRecordORM.title.ilike(f"%{title}%"),
                        PlexRecordORM.full_title.ilike(f"%{title}%")
                    ),
                    PlexRecordORM.year == year
                ).all()

        # Fallback to fuzzy matching if no results
        if not results and fuzzy < 100:
            if verbose:
                print(f"Fuzzy search with threshold: {fuzzy}")
            all_records = self.session.query(PlexRecordORM).all()
            
            def get_relevant_fields(record):
                return (
                    f"{record.title or ''} {record.year or ''}",  # Handle None values
                    record.full_title or '',
                    record.summary or '',
                    record.actors or ''
                )

            candidates = [(get_relevant_fields(record), record) for record in all_records]

            matched_records = []
            for field_values, record in candidates:
                for field in field_values:
                    # Ensure field is a string before calling lower()
                    if field:  # Skips None and empty strings
                        score = fuzz.partial_ratio(text.lower(), field.lower())
                        if score > fuzzy:
                            matched_records.append((score, record))
            
            matched_records.sort(reverse=True, key=lambda x: x[0])
            results = [record for score, record in matched_records]

        return results


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
            item['extras'] = str(item.get('extras', 'False')).lower() == 'true'

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
            # exclude titles with no plex_guid
            return [(x.title, x.year) for x in self.session.query(PlexRecordORM).filter(PlexRecordORM.plex_guid == None).all()]
        # return [
        #     f"{record.title} {record.year if record.year else ''}".strip()
        #     for record in self.session.query(PlexRecordORM).all()
        # ]

    def update_test(self, force=False):
        print("Checking for updates. Please wait...")
        clock = time.perf_counter()
        database_date = None
        try:
            database_date = self.session.query(func.max(PlexRecordORM.updated_at)).scalar()
        except Exception as e:
            print(f"Error getting database date: {e}")
        if not database_date and not force:
            print("No valid database date found - quitting update.")
            sys.exit(1)
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
        if not libraries:
            print("No libraries found.")
            return
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

    def get_df(self):
        try:
            # Assuming self.session is an instance of SQLAlchemy session
            # and PlexRecordORM is an ORM model of your table
            query = self.session.query(PlexRecordORM).statement
            df = pd.read_sql(query, self.session.bind)
            return df
        except Exception as e:
            print(f"Error exporting to DataFrame: {e}")
            return None

    def find(self, title):
        return self.session.query(PlexRecordORM).filter(PlexRecordORM.title == title).first()
    
    def get_db_path(self):
        # Extract the database file path from the SQLAlchemy engine URL
        db_url = engine.url.database
        if not db_url:
            raise FileNotFoundError("Database URL is not set or the database file does not exist.")
        return db_url

    def get_db_stats(self):
        stats = {}
        db_path = self.get_db_path()
        stats['size'] = os.path.getsize(db_path)
        start_time = time.time()
        count = self.session.execute(text('SELECT COUNT(*) FROM plex_records')).scalar()
        stats['count'] = count
        stats['sample_query_time'] = time.time() - start_time
        return stats

    def vacuum_db(self):
        # perform warmup query
        self.session.execute(text('SELECT COUNT(*) FROM plex_records'))
        
        # Get stats before vacuuming
        stats_before = self.get_db_stats()
        print(f"Database stats before vacuuming: {stats_before}")
        
        # Perform vacuuming
        start_vacuum_time = time.time()
        
        self.session.execute(text('VACUUM;'))
        vacuum_time = time.time() - start_vacuum_time
        
        # Get stats after vacuuming
        stats_after = self.get_db_stats()
        print(f"Database stats after vacuuming: {stats_after}")
        
        # Print vacuuming duration
        print(f"Vacuuming took {vacuum_time:.2f} seconds")
        
        # Print comparison
        size_diff = stats_before['size'] - stats_after['size']
        query_time_diff = stats_before['sample_query_time'] - stats_after['sample_query_time']
        print(f"Size reduced by {size_diff} bytes")
        print(f"Sample query time improved by {query_time_diff:.4f} seconds")

    def remove_record(self, id, verbose=False, check=False):
        """
        Remove a record based on its ID, as long as a single record is found matching the ID.
        """
        record = self.session.query(PlexRecordORM).filter(PlexRecordORM.id == id).first()

        if not record:
            if verbose:
                print(f"Record with ID {id} not found.")
            return False

        if check:
            res = input(f"Are you sure you want to delete {record.title}? (yes/y to confirm): ").lower()
            if res not in ['y', 'yes']:
                if verbose:
                    print(f"Record {record.title} [{id}] not deleted.")
                return False

        self.session.delete(record)
        self.session.commit()
        if verbose:
            print(f"Record {record.title} [{id}] deleted.")
        return True
    
    def reset_watch_count(self, rating_key: str):
        """
        Reset the view count (or watch flag) for a series and its episodes, or for standalone media.

        :param rating_key: The rating key of the media (series, movie, or episode).
        """
        try:
            # Fetch the record by rating key
            media_item = self.session.query(PlexRecordORM).filter(
                PlexRecordORM.rating_key == rating_key
            ).first()

            if not media_item:
                print(f"No media found for rating key: {rating_key}")
                return

            # Output media details
            print(f"Found media: {media_item.title} (Type: {media_item.media_type}, Year: {media_item.year})")
            print(f"Details: Library: {media_item.library}, Key: {media_item.key}, Guid: {media_item.guid}")

            # Check if the media is a series
            if media_item.media_type == "show":  # Adjust "show" if it differs in your schema
                print(f"Media with rating key {rating_key} is a series. Fetching episodes...")

                # Fetch all episodes for the series
                episodes = self.session.query(PlexRecordORM).filter(
                    PlexRecordORM.guid.like(f"%/library/metadata/{rating_key}/children%")
                ).all()

                if not episodes:
                    print(f"No episodes found for series with rating key: {rating_key}")
                    return

                # Output episode details
                print(f"Found {len(episodes)} episodes for series {media_item.title}:")
                for episode in episodes:
                    print(f"  - Episode: {episode.title} (Rating Key: {episode.rating_key}, Guid: {episode.guid})")

                # Reset watch flags for all episodes
                episode_rating_keys = [episode.rating_key for episode in episodes]
                result = self.session.query(PlexRecordORM).filter(
                    PlexRecordORM.rating_key.in_(episode_rating_keys)
                ).update({"viewed_at": None, "last_viewed_at": None}, synchronize_session="fetch")

                # Commit changes
                self.session.commit()
                print(f"Reset watch flags for {len(episode_rating_keys)} episodes with result: {result}.")
            else:
                print(f"Media with rating key {rating_key} is a standalone item.")

                # Reset watch flag for standalone item
                result = self.session.query(PlexRecordORM).filter(
                    PlexRecordORM.rating_key == rating_key
                ).update({"viewed_at": None, "last_viewed_at": None}, synchronize_session="fetch")

                # Commit changes
                self.session.commit()
                print(f"Reset watch flag for standalone item with result: {result}.")
        except Exception as e:
            self.session.rollback()
            print(f"An error occurred: {e}")


# Helper functions

def get_media_list():
    library = PlexLibrary()
    return library.title_list()

def find_video_path(self, title):
    record = self.session.query(PlexRecordORM).filter(PlexRecordORM.title == title).first()
    if record:
        return record.video_path
    return None


