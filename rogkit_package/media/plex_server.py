#!/usr/bin/env python3
import dataclasses
import os
from plexapi.server import PlexServer as PlexAPIServer


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
