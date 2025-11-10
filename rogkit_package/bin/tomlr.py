"""
TOML configuration file manager for rogkit.

Manages rogkit configuration in TOML format, supporting XDG config paths,
default settings creation, and config file manipulation.
"""
import os
import toml  # type: ignore
import argparse
import sys
from pathlib import Path

from ..settings import toml_sample_path


DEFAULT_ROGKIT_TOML = {
    "backup" : {
        "backup_from": ["~/"],
        "backup_to": ["~/archive/"],
    },
    "plex": {"plex_server_url": "", "plex_server_token": ""},
    "openweather": {"openweather_api_key": ""},
    "ipinfo": {"ipinfo_api_key": ""},
    "yout": { "temp_folder" : "", "download_folder" : "", "default_input_file" : "" },
    "openai": {"openai_api_key": ""},
    "tmdb": {"tmdb_api_key": "", "tmdb_api_read_access_token": ""},
    "clean": {"script_path": ""},
    "purge": {
        "folders": [
            "~/Media",
        ],
    },
    "spotify": {
        "spotify_client_id": "",
        "spotify_client_secret": "",
        "spotify_redirect_uri": "https://your-app.example.com/callback",
    },
    "media": {
        "paths": [
            "~/Media",
        ],
        "remote_host": "192.168.0.50",
        "remote_user": "rog",
        "remote_password": "",
        "remote_folder": "/mnt/media1/Media/Movies",
    },
}

def get_config_value(group: str, key: str, verbose: bool = False):
    """
    Retrieve a value from the rogkit config TOML using group and key.
    Returns [] if either is missing or not found.
    """
    if not group or not key:
        if verbose:
            print("⚠️  Missing group or key for rogkit config.")
        return []

    config = load_rogkit_toml()
    value = config.get(group, {}).get(key)

    if value is None and verbose:
        print(f"⚠️  No value found for '{key}' in group '{group}'.")

    return value if value is not None else []

def get_rogkit_toml_path() -> Path:
    """
    Get the preferred rogkit config path, falling back to legacy.
    """
    xdg_config_home = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    modern_path = xdg_config_home / "rogkit" / "config.toml"
    legacy_path = Path.home() / ".rogkit.toml"

    if modern_path.exists():
        return modern_path
    if legacy_path.exists():
        print(f"Using legacy config path: {legacy_path}")
        return legacy_path

    # Default to modern path for new creation
    return modern_path

def setup_rogkit_toml():
    """Create rogkit config file with default settings if it doesn't exist."""
    rogkit_toml_path = get_rogkit_toml_path()
    if not rogkit_toml_path.exists():
        try:
            rogkit_toml_path.parent.mkdir(parents=True, exist_ok=True)
            with open(rogkit_toml_path, 'w', encoding='utf-8') as f:
                toml.dump(DEFAULT_ROGKIT_TOML, f)
            print(f"Created {rogkit_toml_path} with default settings.")
        except IOError as e:
            print(f"Error creating {rogkit_toml_path}: {e}", file=sys.stderr)
    else:
        print(f"{rogkit_toml_path} already exists.")

def load_rogkit_toml(*args):
    """ Load and return the contents of rogkit toml as a dict. """
    rogkit_toml_path = get_rogkit_toml_path()
    if not os.path.exists(rogkit_toml_path):
        setup_rogkit_toml()

    with open(rogkit_toml_path, 'r', encoding='utf-8') as f:
        try:
            data = toml.load(f)
        except toml.TomlDecodeError as e:
            print(f"Error parsing {rogkit_toml_path}: {e}", file=sys.stderr)
            sys.exit(1)
        
        if args:
            return data[args[0]]
        return data

def make_keys_lowercase(d):
    """ Recursively make all keys in a dict lowercase. """
    if isinstance(d, dict):
        return {k.lower(): make_keys_lowercase(v) for k, v in d.items()}
    else:
        return d

def make_current_rogkit_toml_lowercase():
    """Load the current rogkit toml and make all keys lowercase."""
    toml_lower = make_keys_lowercase(load_rogkit_toml())
    # write the file
    rogkit_toml_path = get_rogkit_toml_path()
    print(f"Writing {rogkit_toml_path} with lowercase keys.")
    try:
        with open(rogkit_toml_path, 'w', encoding='utf-8') as f:
            toml.dump(toml_lower, f)
    except IOError as e:
        print(f"Error writing {rogkit_toml_path}: {e}", file=sys.stderr)
        sys.exit(1)

def get_default_toml():
    """Return default rogkit TOML configuration dictionary."""
    return DEFAULT_ROGKIT_TOML


def write_default_toml():
    """Write default TOML configuration to sample file."""
    toml_string = toml.dumps(get_default_toml())
    toml_path = toml_sample_path
    prompt = ""
    if os.path.exists(toml_path):
        prompt = input(f"{toml_path} already exists. Press y overwrite, n to cancel: ")
        if prompt.lower() not in ['y', 'yes']:
            print("Aborting.")
            return
    try:
        with open(toml_path, 'w', encoding='utf-8') as f:
            f.write(toml_string)
        print(f"Wrote {toml_path} with default settings.")
    except IOError as e:
        print(f"Error writing {toml_path}: {e}", file=sys.stderr)
        sys.exit(1)


def parse_args():
    """Setup command-line argument parsing."""
    parser = argparse.ArgumentParser(description="Rogkit TOML tool")
    parser.add_argument("-c", "--create", action="store_true", help="Create ~/.rogkit.toml with default settings (if it doesn't exist)")
    parser.add_argument("-d", "--default", action="store_true", help="Print default rogkit toml")
    parser.add_argument("-s", "--show", action="store_true", help="Show current rogkit toml")
    parser.add_argument("-w", "--write", action="store_true", help="Write default rogkit toml to rogkit_sample.toml")
    parser.add_argument("--lowercase", action="store_true", help="Make all keys in the current rogkit toml lowercase")
    return parser.parse_args()

def main():
    """CLI entry point for TOML configuration tool."""
    args = parse_args()
    print("Rogkit TOML Tool")

    if args.write:
        write_default_toml()
    if args.create:
        setup_rogkit_toml()
    if args.lowercase:
        make_current_rogkit_toml_lowercase()
    if args.default:
        toml_string = toml.dumps(get_default_toml())
        print(toml_string)
    elif args.show:
        print(f'Current rogkit toml: {get_rogkit_toml_path()}')
        config = load_rogkit_toml()
        print(toml.dumps(config))

if __name__ == "__main__":
    main()
