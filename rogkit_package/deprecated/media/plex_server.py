#!/usr/bin/env python3
"""
Plex server connection manager.

Handles Plex server authentication using URL/token from TOML config or environment variables.
"""
import dataclasses
import os
from dotenv import load_dotenv  # type: ignore
from plexapi.server import PlexServer as PlexAPIServer  # type: ignore

from rogkit_package.bin.tomlr import load_rogkit_toml

load_dotenv()


@dataclasses.dataclass
class PlexServer:
    """Plex server connection wrapper with configuration from TOML or environment."""
    url: str = None
    token: str = None
    port: int = None
    connection: PlexAPIServer = dataclasses.field(init=False, default=None)

    def __post_init__(self):
        toml = load_rogkit_toml()
        self.url = self.url or toml.get('plex', {}).get('plex_server_url', '') or os.environ.get("PLEX_SERVER_URL", "localhost")
        self.token = self.token or toml.get('plex', {}).get('plex_server_token', '') or os.environ.get("PLEX_SERVER_TOKEN")
        self.port = int(self.port or os.environ.get("PLEX_SERVER_PORT", 32400))
        if not self.url.startswith("http"):
            self.url = f"http://{self.url}"
        self.full_url = f"{self.url}:{self.port}"
        # Establish connection to the Plex server
        self.get_connection()

    def get_connection(self):
        """Establish and return Plex API connection."""
        # Ensure the connection is established and return it
        if not self.connection:
            print(f"Connecting to Plex server: {self.url}:{self.port}")
            try:
                self.connection = PlexAPIServer(self.full_url, self.token)
            except Exception as e:
                print(f"Error connecting to Plex server: {e}")
        return self.connection

