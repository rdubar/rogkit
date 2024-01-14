#!/usr/bin/env python3
import dataclasses
import datetime


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
    size: int = None

    def __post_init__(self):
        # Set full_title to 'title (year)' if year is present, otherwise just 'title'
        if self.year:
            self.full_title = f"{self.title} ({self.year})"
        else:
            self.full_title = self.title

def get_possible_attributes():
    return [f.name for f in dataclasses.fields(PlexRecord)]

