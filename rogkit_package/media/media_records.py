import dataclasses
from sqlalchemy import Column, Integer, Boolean, String, DateTime, Integer
from .database_utils import Base
from ..bin.bytes import byte_size

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
    'size': (Integer, {'default': None})
}

def create_dataclass_fields(schema):
    dataclass_fields = {}
    for field, (dtype, options) in schema.items():
        # Check if a default is provided in the schema
        default_value = options.get('default', dataclasses.MISSING)
        dataclass_field = dataclasses.field(default=default_value)
        dataclass_fields[field] = (dtype, dataclass_field)
    return dataclass_fields

def create_orm_columns(schema):
    orm_columns = {}
    for field, (col_type, options) in schema.items():
        # Remove 'default' key as it's not valid for ORM columns
        options.pop('default', None)
        orm_columns[field] = Column(col_type, **options)
    return orm_columns

# Dynamically create PlexRecord as a dataclass with default values
PlexRecord = dataclasses.make_dataclass('PlexRecord', create_dataclass_fields(common_schema).items())

# Dynamically create the ORM class using the common schema
class PlexRecordORM(Base):
    __tablename__ = 'plex_records'
    locals().update(create_orm_columns(common_schema))

    def __str__(self):
        # Customize the string representation of PlexRecord
        year_str = f" ({self.year})" if self.year else ""
        resolution_str = f" {self.resolution}" if self.resolution else ""
        size_str = f" {byte_size(self.size)}" if self.size else ""
        return f"{self.platform:7}{size_str:>10} {resolution_str:<6}    {self.title}{year_str}"

def get_possible_attributes():
    return [f.name for f in dataclasses.fields(PlexRecord)]