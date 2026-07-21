"""
OpenERP/Odoo XML-RPC connection manager.

Provides XML-RPC client for connecting to OpenERP/Odoo servers
with configuration management via rogkit TOML or .env files.
"""
from dataclasses import dataclass
import argparse
import sys
import xmlrpc.client
from pathlib import Path
from typing import Any, Optional

from ..settings import get_invoking_cwd
from .tomlr import get_rogkit_toml_path, load_rogkit_toml


REQUIRED_CONFIG_KEYS = ("url", "db", "username", "password")


class XmlrConfigError(Exception):
    """Raised when xmlr cannot find a usable connection configuration."""


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
        section = f"erp-{environment}"
        config: dict[str, Any] = {}
        try:
            loaded = load_rogkit_toml(section)
            if isinstance(loaded, dict):
                config = loaded
        except KeyError:
            config = {}

        if not config:
            config = _load_dotenv_config(get_invoking_cwd() / ".env")

        missing = [key for key in REQUIRED_CONFIG_KEYS if not config.get(key)]
        if missing:
            raise XmlrConfigError(_missing_config_message(section, missing))

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

    def connect(self) -> bool:
        """Establish XML-RPC connection and authenticate with server."""
        # Establish XML-RPC Common connection for authentication
        try:
            self.common = xmlrpc.client.ServerProxy(f'{self.config.url}/xmlrpc/common')
            self.uid = self.common.login(self.config.db, self.config.username, self.config.password)
        except Exception as e:
            print(f"xmlrpc connect error: {e}", file=sys.stderr)
            return False
        if self.uid:
            print(f"Successfully logged in as UID: {self.uid}")
            # Establish XML-RPC Object connection for calling methods
            self.models = xmlrpc.client.ServerProxy(f'{self.config.url}/xmlrpc/object')
            return True
        print("Failed to authenticate.", file=sys.stderr)
        return False

    def execute_kw(self, model: str, method: str, args: list[Any], kwargs: dict[str, Any] | None = None) -> Any:
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


def _load_dotenv_config(path: Path) -> dict[str, str]:
    """Load simple KEY=VALUE pairs from a .env file."""
    config: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return config
    except OSError as e:
        raise XmlrConfigError(f"Error reading {path}: {e}") from e

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        config[key.strip()] = value.strip().strip("\"'")
    return config


def _missing_config_message(section: str, missing: list[str]) -> str:
    config_path = get_rogkit_toml_path()
    missing_text = ", ".join(missing)
    keys = "\n".join(f'{key} = ""' for key in REQUIRED_CONFIG_KEYS)
    return (
        f"Missing XML-RPC configuration for [{section}] ({missing_text}).\n\n"
        f"Add this section to {config_path} or {config_path.parent / 'secrets.toml'}:\n\n"
        f"[{section}]\n{keys}\n\n"
        "Alternatively, create a .env file in the directory where you run xmlr "
        "with url, db, username, and password."
    )
    

def main() -> int:
    """CLI entry point for OpenERP XML-RPC connector."""
    parser = argparse.ArgumentParser(description='Connect to OpenERP XML-RPC services.')
    parser.add_argument('--env', type=str, choices=['live', 'test'], default='test',
                        help='The environment to connect to: live or test. Defaults to test if not provided.')

    args = parser.parse_args()

    # Load configuration
    try:
        config = Config.load_config(args.env)
    except XmlrConfigError as e:
        print(e, file=sys.stderr)
        return 2

    # Create an OpenERPConnector instance and connect
    connector = OpenERPConnector(config)
    if not connector.connect():
        return 1

    # Example: Read user details using the connector
    user_id = connector.uid  # Assuming you want details of the logged-in user
    user_details = connector.execute_kw('res.users', 'read', [user_id], {'fields': ['name', 'login', 'email']})

    if user_details:
        print(f"User Details: {user_details}")
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
