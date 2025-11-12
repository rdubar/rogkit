"""
Media records schema and ORM models for Plex library management.

Defines database schema, ORM models, and dataclasses for storing and
displaying media metadata from Plex servers.
"""
import dataclasses
from sqlalchemy import Column, Integer, Boolean, String, DateTime
from .database_utils import Base, engine
from rogkit_package.bin.bytes import byte_size
from rogkit_package.bin.seconds import hms_string

# Schema definition for media records (both ORM and dataclass)
common_schema = {
    'id': (Integer, {'primary_key': True, 'default': None}),
    'plex_guid': (String, {'unique': True, 'default': None}),
    'title': (String, {'default': None}),
    'year': (Integer, {'default': None}),
    'rating': (Integer, {'default': None}),
    'duration': (Integer, {'default': None}),
    'genres': (String, {'default': None}),
    'actors': (String, {'default': None}),
    'directors': (String, {'default': None}),
    'writers': (String, {'default': None}),
    'summary': (String, {'default': None}),
    'library': (String, {'default': None}),
    'thumb': (String, {'default': None}),
    'art': (String, {'default': None}),
    'section': (String, {'default': None}),
    'key': (String, {'default': None}),
    'rating_key': (String, {'default': None}),
    'guid': (String, {'default': None}),
    'media_type': (String, {'default': None}),
    'added_at': (DateTime, {'default': None}),
    'updated_at': (DateTime, {'default': None}),
    'viewed_at': (DateTime, {'default': None}),
    'last_viewed_at': (DateTime, {'default': None}),
    'originally_available_at': (DateTime, {'default': None}),
    'platform': (String, {'default': None}),
    'full_title': (String, {'default': None}),
    'extras': (Boolean, {'default': None}),
    'resolution': (String, {'default': None}),
    'bitrate': (Integer, {'default': None}),
    'codec': (String, {'default': None}),
    'size': (Integer, {'default': None}),
    'video_path': (String, {'default': None}),
    'last_modified': (DateTime, {'default': None}),
}

def create_orm_columns(schema):
    """
    Convert schema definition to SQLAlchemy Column objects.
    
    Args:
        schema: Dictionary mapping field names to (type, options) tuples
        
    Returns:
        Dictionary of field names to SQLAlchemy Column objects
    """
    orm_columns = {}
    for field, (dtype, options) in schema.items():
        # Filter out non-SQLAlchemy keys if any
        column_options = {k: v for k, v in options.items() if k in ['primary_key', 'unique', 'default', 'onupdate']}
        orm_columns[field] = Column(dtype, **column_options)
    return orm_columns

class PlexRecordORM(Base):
    """
    SQLAlchemy ORM model for Plex media records.
    
    Stores metadata for movies and TV shows from Plex servers,
    including titles, ratings, file sizes, and technical details.
    """
    __tablename__ = 'plex_records'
    locals().update(create_orm_columns(common_schema))

    def __str__(self):
        """
        Format record as single-line display with platform, size, resolution, and title.
        
        Returns:
            Formatted string: "plex      4.13 GB  1080     Movie Title (2024)"
        """
        year_str = f" ({self.year})" if self.year is not None else ""
        resolution_str = f" {self.resolution}" if self.resolution is not None and self.resolution != "None" else ""
        size_str = f" {byte_size(self.size, unit='GB')}" if self.size is not None else ""

        # Default values for None fields
        platform_str = self.platform if self.platform is not None else "Unknown"
        title_str = self.title if self.title is not None else "No Title"

        return f"{platform_str:7}{size_str:>10} {resolution_str:>6}    {title_str}{year_str}"

    
    def info(self):
        """
        Format record as detailed multi-line display with full metadata.
        
        Returns:
            Formatted string with title, credits, summary, and technical details
        """
        year_str = f" ({self.year})" if self.year else ""
        resolution_str = f"{self.resolution}" if self.resolution else ""
        size_str = f"{byte_size(self.size)}" if self.size else ""
        rating = f"[{self.rating}/10]" if self.rating else ""
        genres = f"{self.genres}" if self.genres else ""
        # Convert duration from milliseconds to seconds, but round to the nearest minute
        time_str = hms_string((self.duration / 1000)) if self.duration else ""
        information = f'{self.title}{year_str}\n'
        if self.directors:
            information += f'd. {self.directors}'
        if self.writers:
            information += f', w. {self.writers}'
        if self.actors:
            information += f', a. {self.actors}'
        # get the internal ID of the record from the database for easy of reference
        id_str = f'ID: {self.id}'
        information += f'\n{self.summary}\n{self.platform} {resolution_str}  {rating}   {size_str}   {time_str}  [{id_str}]  {genres}\n'
        return information

def create_dataclass_fields(schema):
    """
    Convert schema definition to dataclass field tuples.
    
    Args:
        schema: Dictionary mapping field names to (type, options) tuples
        
    Returns:
        List of (field_name, type) tuples for make_dataclass()
    """
    fields = []
    for field_name, (_dtype, _options) in schema.items():
        # For make_dataclass, we just need (name, type) tuples
        # Defaults will be None for all fields
        fields.append((field_name, type(None)))
    return fields

PlexRecord = dataclasses.make_dataclass('PlexRecord', create_dataclass_fields(common_schema))

# After defining PlexRecordORM
Base.metadata.create_all(engine) 

def get_possible_attributes():
    """
    Get list of all field names from the PlexRecord dataclass.
    
    Returns:
        List of field name strings
    """
    return [f.name for f in dataclasses.fields(PlexRecord)]