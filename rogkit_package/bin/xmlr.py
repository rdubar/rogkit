"""
OpenERP/Odoo XML-RPC connection manager.

Provides XML-RPC client for connecting to OpenERP/Odoo servers
with configuration management via rogkit TOML or .env files.
"""
from dataclasses import dataclass
import argparse
import xmlrpc.client
from typing import Optional
from .tomlr import load_rogkit_toml


@dataclass
class Config:
    """OpenERP/Odoo connection configuration."""
    url: str
    db: str
    username: str
    password: str
    environment: str
    config: Optional[str] = None

    @staticmethod
    def load_config(environment: str) -> 'Config':
        """Load configuration from rogkit TOML or fallback to .env file."""
        try:
            config = load_rogkit_toml(f'erp-{environment}')
            if not config:
                raise FileNotFoundError
        except FileNotFoundError:
            # Fallback to .env file if TOML is not available or empty
            config = {}
            try:
                with open('.env') as f:
                    for line in f:
                        if '=' in line:
                            key, value = line.strip().split('=', 1)
                            config[key] = value
            except Exception as e:
                print(f"Error reading .env file: {e}")
                exit(1)

        return Config(
            url=config.get('url'),
            db=config.get('db'),
            username=config.get('username'),
            password=config.get('password'),
            environment=environment
        )

@dataclass
class OpenERPConnector:
    """XML-RPC connector for OpenERP/Odoo server operations."""
    config: Config
    uid: Optional[int] = None
    common: Optional[xmlrpc.client.ServerProxy] = None
    models: Optional[xmlrpc.client.ServerProxy] = None

    def connect(self):
        """Establish XML-RPC connection and authenticate with server."""
        # Establish XML-RPC Common connection for authentication
        try:
            self.common = xmlrpc.client.ServerProxy(f'{self.config.url}/xmlrpc/common')
            self.uid = self.common.login(self.config.db, self.config.username, self.config.password)
        except Exception as e:
            print(f"xmlrpc connect error: {e}")
            exit(1)
        if self.uid:
            print(f"Successfully logged in as UID: {self.uid}")
            # Establish XML-RPC Object connection for calling methods
            self.models = xmlrpc.client.ServerProxy(f'{self.config.url}/xmlrpc/object')
        else:
            print("Failed to authenticate.")

    def execute_kw(self, model, method, args, kwargs=None):
        """
        Execute OpenERP/Odoo model method via XML-RPC.
        
        Args:
            model: Model name (e.g., 'res.users')
            method: Method name (e.g., 'read', 'search')
            args: Positional arguments for the method
            kwargs: Keyword arguments for the method
            
        Returns:
            Result from the XML-RPC call
        """
        if kwargs is None:
            kwargs = {}
        if not self.models:
            print("Not connected to XML-RPC Object service.")
            return None
        return self.models.execute_kw(self.config.db, self.uid, self.config.password,
                                      model, method, args, kwargs)

    # Add more methods as needed for different XML-RPC activities
    
def main():
    """CLI entry point for OpenERP XML-RPC connector."""
    parser = argparse.ArgumentParser(description='Connect to OpenERP XML-RPC services.')
    parser.add_argument('--env', type=str, choices=['live', 'test'], default='test',
                        help='The environment to connect to: live or test. Defaults to test if not provided.')

    args = parser.parse_args()

    # Load configuration
    config = Config.load_config(args.env)

    # Create an OpenERPConnector instance and connect
    connector = OpenERPConnector(config)
    connector.connect()

    # Example: Read user details using the connector
    user_id = connector.uid  # Assuming you want details of the logged-in user
    user_details = connector.execute_kw('res.users', 'read', [user_id], {'fields': ['name', 'login', 'email']})

    if user_details:
        print(f"User Details: {user_details}")

if __name__ == '__main__':
    main()
