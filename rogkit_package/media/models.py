#!/usr/bin/env python3
import dataclasses
from sqlalchemy import Column, Integer, Boolean, String, DateTime, Integer
from .database_utils import Base 
from ..bin.bytes import byte_size

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
    size = Column(Integer)

    def __str__(self):
        # Customize the string representation of PlexRecord
         year = f" ({self.year})" if self.year else ""
         resolution = f" {self.resolution}" if self.resolution else ""
         size = f" {byte_size(self.size)}" if self.size else ""
         return f"{self.platform:7} {size:10} {resolution:<6}    {self.title}{year}"
    