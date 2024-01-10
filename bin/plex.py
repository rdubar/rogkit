#!/usr/bin/env python3
import dataclasses
import os
from plexapi.server import PlexServer as PlexAPIServer
from dotenv import load_dotenv

load_dotenv()

@dataclasses.dataclass
class PlexServer:
    url: str = None
    token: str = None
    port: int = None
    connection: PlexAPIServer = dataclasses.field(init=False, default=None)

    def __post_init__(self):
        self.url = self.url or os.environ.get("PLEX_SERVER_URL", "localhost")
        self.token = self.token or os.environ.get("PLEX_SERVER_TOKEN")
        self.port = self.port or os.environ.get("PLEX_SERVER_PORT", 32400)
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

@dataclasses.dataclass
class PlexLibrary:
    plex_server: PlexServer = None
    libraries: list = dataclasses.field(init=False, default_factory=list)
    sections: list = dataclasses.field(init=False, default_factory=list)

    def __post_init__(self):
        print('PlexLibrary.__post_init__()')
        if not self.plex_server:
            self.plex_server = PlexServer()

        try:
            self.get_libraries()
        except Exception as e:
            print(f"Error in getting libraries: {e}")

    def get_libraries(self):
        print('PlexLibrary.get_libraries()')
        try:
            self.libraries = self.plex_server.connection.library.sections()
            return self.libraries
        except Exception as e:
            print(f"Error in get_libraries: {e}")
            return None

    def get_sections(self):
        print('PlexLibrary.get_sections()')
        self.sections = []
        for library in self.libraries:
            self.sections.append(library.title)
        return self.sections


# Example usage
# plex_server = PlexServer()
# plex_connection = plex_server.get_connection()
# print('Plex connection:', plex_connection)
plex_library = PlexLibrary()

print(plex_library.get_libraries()) 
print(plex_library.get_sections())

for library in plex_library.get_libraries():
    print(vars(library))