import dataclasses
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, Boolean, String, DateTime, Integer
from .database_utils import Base
from ..bin.bytes import byte_size

common_schema = {
    'id': (Integer, {'primary_key': True}),
    'plex_guid': (String, {'unique': True}),
    'title': (String, {}),
    'year': (Integer, {}),
    'rating': (Integer, {}),
    'duration': (Integer, {}),
    'genres': (String, {}),
    'actors': (String, {}),
    'directors': (String, {}),
    'writers': (String, {}),
    'summary': (String, {}),
    'library': (String, {}),
    'thumb': (String, {}),
    'art': (String, {}),
    'section': (String, {}),
    'key': (String, {}),
    'rating_key': (String, {}),
    'guid': (String, {}),
    'media_type': (String, {}),
    'added_at': (DateTime, {}),
    'updated_at': (DateTime, {}),
    'viewed_at': (DateTime, {}),
    'last_viewed_at': (DateTime, {}),
    'originally_available_at': (DateTime, {}),
    'platform': (String, {}),
    'full_title': (String, {}),
    'extras': (Boolean, {}),
    'resolution': (String, {}),
    'bitrate': (Integer, {}),
    'codec': (String, {}),
    'size': (Integer, {})
}

def create_dataclass_fields(schema):
    return {field: data_type for field, (data_type, _) in schema.items()}

def create_orm_columns(schema):
    return {field: Column(sqlalchemy_type, **options) for field, (sqlalchemy_type, options) in schema.items()}

def get_possible_attributes():
    return [f.name for f in dataclasses.fields(PlexRecord)]

# Generate PlexRecord as a dataclass
@dataclasses.dataclass
class PlexRecord:
    __annotations__ = create_dataclass_fields(common_schema)

# Generate PlexRecordORM with SQLAlchemy
class PlexRecordORM(Base):
    __tablename__ = 'plex_records'
    locals().update(create_orm_columns(common_schema))

    def __str__(self):
        # Customize the string representation of PlexRecord
         year = f" ({self.year})" if self.year else ""
         resolution = f" {self.resolution}" if self.resolution else ""
         size = f" {byte_size(self.size)}" if self.size else ""
         return f"{self.platform:7}{size:>10} {resolution:<6}    {self.title}{year}"
