import dataclasses
from datetime import datetime
from sqlalchemy import Column, Integer, Boolean, String, DateTime, Integer
import sqlalchemy as sa
from .database_utils import Base ,engine
from ..bin.bytes import byte_size
from ..bin.seconds import convert_seconds

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
    'last_modified': (DateTime, {'default': sa.func.now(), 'onupdate': sa.func.now()}),
}

def create_dataclass_fields(schema):
    fields = []
    for field, (dtype, options) in schema.items():
        default_factory = options.get('dataclass_default', lambda: None)
        fields.append((field, dtype, dataclasses.field(default_factory=default_factory)))
    return fields

def create_orm_columns(schema):
    orm_columns = {}
    for field, (dtype, options) in schema.items():
        # Filter out non-SQLAlchemy keys if any
        column_options = {k: v for k, v in options.items() if k in ['primary_key', 'unique', 'default', 'onupdate']}
        orm_columns[field] = Column(dtype, **column_options)
    return orm_columns

class PlexRecordORM(Base):
    __tablename__ = 'plex_records'
    locals().update(create_orm_columns(common_schema))

    def __str__(self):
        # Customize the string representation of PlexRecord
        year_str = f" ({self.year})" if self.year is not None else ""
        resolution_str = f" {self.resolution}" if self.resolution is not None and self.resolution != "None" else ""
        size_str = f" {byte_size(self.size)}" if self.size is not None else ""

        # Default values for None fields
        platform_str = self.platform if self.platform is not None else "Unknown"
        title_str = self.title if self.title is not None else "No Title"

        return f"{platform_str:7}{size_str:>10} {resolution_str:<6}    {title_str}{year_str}"

    
    def info(self):
        # Customize the string representation of PlexRecord
        year_str = f" ({self.year})" if self.year else ""
        resolution_str = f"{self.resolution}" if self.resolution else ""
        size_str = f"{byte_size(self.size)}" if self.size else ""
        rating = f"[{self.rating}/10]" if self.rating else ""
        genres = f"{self.genres}" if self.genres else ""
        # Convert duration from milliseconds to seconds, but round to the nearest minute
        time_str = convert_seconds((self.duration / 1000), show_seconds=False) if self.duration else ""
        information = f'{self.title}{year_str}\n'
        if self.directors:
            information += f'd. {self.directors}'
        if self.writers:
            information += f', w. {self.writers}'
        if self.actors:
            information += f', a. {self.actors}'
        information += f'\n{self.summary}\n{self.platform} {resolution_str}  {rating}   {size_str}   {time_str}  {genres}\n'
        return information

# Dataclass field defaults handling (if required)
def create_dataclass_fields(schema):
    fields = []
    for field, (dtype, options) in schema.items():
        # Assuming 'default' is used for dataclass default values
        default = options.get('default', dataclasses.MISSING)
        fields.append((field, dtype, dataclasses.field(default=default)))
    return fields

PlexRecord = dataclasses.make_dataclass('PlexRecord', create_dataclass_fields(common_schema))

# After defining PlexRecordORM
Base.metadata.create_all(engine) 

def get_possible_attributes():
    return [f.name for f in dataclasses.fields(PlexRecord)]