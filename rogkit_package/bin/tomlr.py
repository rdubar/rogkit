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
    "backup": {
        "backup_from": ["~/"],
        "backup_to": ["~/archive/"],
        "secret_patterns": ["secrets.toml", ".env"],
        "set": [
            {
                "name": "CloudBackup",
                "destinations": [
                    "/mnt/nas/backups/docs",
                    "/mnt/external1/docs",
                ],
                "paths": [
                    "~/Documents",
                    "~/Work/Reports",
                    "/etc/hosts",
                ],
            },
            {
                "name": "LocalBackup",
                "include_secrets": True,
                "destinations": [
                    "/mnt/nas/media",
                    "/mnt/cloud/media",
                ],
                "paths": [
                    "~/Pictures",
                    "~/Videos",
                ],
            },
        ],
    },
    "clean": {"script_path": ""},
    "media": {
        "remote_host": "192.168.0.50",
        "remote_user": "rog",
        "remote_password": "",
        "remote_folders": ["/mnt/media1/Media/Movies"],
    },
    "plex": {"plex_server_url": ""},
    "spotify": {
        "spotify_redirect_uri": "http://127.0.0.1:8888/callback/",
    },
    "purge": {
        "folders": [
            "~/Media",
        ],
    },
    "media_files": {
        "folders": [
            "/mnt/media1/Media/",
            "/mnt/media2/Media/",
            "/mnt/media3/Media/",
        ],
    },
    "vido": {"temp_folder": "", "download_folder": "", "default_input_file": ""},
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

def get_rogkit_secrets_path() -> Path:
    """Get secrets.toml path — sibling of config.toml."""
    return get_rogkit_toml_path().parent / "secrets.toml"


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base, returning a new dict."""
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


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
                toml.dump(get_default_toml(), f)
            print(f"Created {rogkit_toml_path} with default settings.")
        except IOError as e:
            print(f"Error creating {rogkit_toml_path}: {e}", file=sys.stderr)
    else:
        print(f"{rogkit_toml_path} already exists.")

def print_toml_error(path: Path, error: Exception):
    """
    Print a parse error with line/column context when available.
    """
    line_no = getattr(error, "lineno", None) or getattr(error, "line", None)
    col_no = getattr(error, "col", None) or getattr(error, "colno", None)
    print(f"Error parsing {path}: {error}", file=sys.stderr)

    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except Exception:
        return

    if line_no and 1 <= line_no <= len(lines):
        line_txt = lines[line_no - 1]
        location = f"line {line_no}"
        if col_no:
            location += f", column {col_no}"
        print(f"  at {location}:", file=sys.stderr)
        print(f"    {line_txt}", file=sys.stderr)
        if col_no and col_no > 0:
            pointer = " " * (col_no - 1)
            print(f"    {pointer}^", file=sys.stderr)

def load_toml_file(path: Path, exit_on_error: bool = True):
    """Load TOML file with friendly error messages."""
    try:
        return toml.load(path)
    except toml.TomlDecodeError as e:
        print_toml_error(path, e)
    except Exception as e:
        # toml can occasionally raise unexpected errors for malformed files
        print_toml_error(path, e)

    if exit_on_error:
        sys.exit(1)
    return None

def validate_toml_file(path: Path) -> bool:
    """Validate a TOML file, printing context on failure."""
    path = path.expanduser()
    if not path.exists():
        print(f"TOML file not found: {path}", file=sys.stderr)
        return False

    if load_toml_file(path, exit_on_error=False) is None:
        return False

    print(f"Valid TOML: {path}")
    return True

def load_rogkit_toml(*args):
    """Load config.toml, deep-merge secrets.toml on top, return the result."""
    rogkit_toml_path = get_rogkit_toml_path()
    if not os.path.exists(rogkit_toml_path):
        setup_rogkit_toml()

    data = load_toml_file(rogkit_toml_path)
    secrets_path = get_rogkit_secrets_path()
    if secrets_path.exists():
        secrets = load_toml_file(secrets_path, exit_on_error=False)
        if secrets:
            data = _deep_merge(data, secrets)

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
    """
    Return default rogkit TOML configuration dictionary.

    Prefer loading the checked-in sample file so defaults stay in sync with
    docs; fall back to the built-in structure if the sample is unavailable or
    invalid.
    """
    sample_path = Path(toml_sample_path)
    if sample_path.exists():
        sample_data = load_toml_file(sample_path, exit_on_error=False)
        if sample_data:
            return sample_data
    return DEFAULT_ROGKIT_TOML


# Keys to extract into secrets.toml, by section.
_SECRET_KEYS: dict[str, list[str]] = {
    "aws":         ["aws_access_key_id", "aws_secret_access_key"],
    "mongodb":     ["username", "password", "uri"],
    "openweather": ["openweather_api_key"],
    "ipinfo":      ["ipinfo_api_key"],
    "plex":        ["plex_server_token"],
    "spotify":     ["spotify_client_id", "spotify_client_secret"],
    "tmdb":        ["tmdb_api_key", "tmdb_api_read_access_token"],
    "openai":      ["openai_api_key"],
}


def migrate_secrets() -> None:
    """Split credential keys out of config.toml into secrets.toml.

    Idempotent: safe to run multiple times. Only moves keys that are present
    and non-empty in config.toml and not already in secrets.toml.
    Also ensures [backup] secret_patterns is set in config.toml.
    """
    config_path = get_rogkit_toml_path()
    secrets_path = get_rogkit_secrets_path()

    config = load_toml_file(config_path)
    existing_secrets = {}
    if secrets_path.exists():
        existing_secrets = load_toml_file(secrets_path, exit_on_error=False) or {}

    moved: list[str] = []
    new_secrets = _deep_merge({}, existing_secrets)

    for section, keys in _SECRET_KEYS.items():
        if section not in config:
            continue
        for key in keys:
            value = config[section].get(key)
            if not value:
                continue
            already_in_secrets = existing_secrets.get(section, {}).get(key)
            if already_in_secrets:
                continue
            new_secrets.setdefault(section, {})[key] = value
            del config[section][key]
            moved.append(f"  {section}.{key}")

    # Ensure [backup] secret_patterns is present in config
    backup = config.setdefault("backup", {})
    if "secret_patterns" not in backup:
        backup["secret_patterns"] = ["secrets.toml", ".env"]
        moved.append("  backup.secret_patterns (added)")

    if not moved:
        print("Nothing to migrate — config.toml already clean.")
        return

    # Write secrets.toml
    secrets_path.parent.mkdir(parents=True, exist_ok=True)
    with open(secrets_path, "w", encoding="utf-8") as f:
        toml.dump(new_secrets, f)

    # Write cleaned config.toml
    with open(config_path, "w", encoding="utf-8") as f:
        toml.dump(config, f)

    print(f"Migrated to {secrets_path}:")
    for line in moved:
        print(line)
    print(f"\nconfig.toml updated: {config_path}")
    print("Done. Verify with: tomlr -s")


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
    parser.add_argument("-v", "--validate", nargs="?", const="", metavar="PATH", help="Validate rogkit config (default) or a specific TOML file")
    parser.add_argument("--migrate-secrets", action="store_true", help="Split credentials out of config.toml into secrets.toml (idempotent)")
    return parser.parse_args()

def main():
    """CLI entry point for TOML configuration tool."""
    args = parse_args()
    print("Rogkit TOML Tool")

    if args.migrate_secrets:
        migrate_secrets()
        return
    if args.write:
        write_default_toml()
    if args.create:
        setup_rogkit_toml()
    if args.lowercase:
        make_current_rogkit_toml_lowercase()
    if args.validate is not None:
        target_path = get_rogkit_toml_path() if args.validate == "" else Path(args.validate)
        if not validate_toml_file(target_path):
            sys.exit(1)
    if args.default:
        toml_string = toml.dumps(get_default_toml())
        print(toml_string)
    elif args.show:
        print(f'Current rogkit toml: {get_rogkit_toml_path()}')
        config = load_rogkit_toml()
        print(toml.dumps(config))

if __name__ == "__main__":
    main()
