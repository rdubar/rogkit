import dataclasses
from plexapi.server import PlexServer as PlexAPIServer

@dataclasses.dataclass
class PlexServer:
    url: str
    token: str
    connection: PlexAPIServer = dataclasses.field(init=False, default=None)

    def __post_init__(self):
        # Establish connection to the Plex server
        self.connection = PlexAPIServer(self.url, self.token)

    def get_connection(self):
        # Ensure the connection is established and return it
        if not self.connection:
            self.connection = PlexAPIServer(self.url, self.token)
        return self.connection

# Example usage
plex_server = PlexServer(url='http://your-plex-server', token='your-token')
plex_connection = plex_server.get_connection()
