import os
import toml
import argparse
import sys

DEFAULT_ROGKIT_TOML = {
    "BackupFrom": {"primary": "~/"},
    "BackupTo": {"primary": "~/archive/"},
    "Plex": {"PLEX_SERVER_URL": "", "PLEX_SERVER_TOKEN": ""},
    "OpenWeather": {"OPENWEATHER_API_KEY": ""},
    "ipinfo": {"IPINFO_API_KEY": ""}
}

def user_rogkit_toml_path():
    return os.path.join(os.path.expanduser('~'), '.rogkit.toml')

def setup_rogkit_toml():
    """ Create ~/.rogkit.toml with default settings if it doesn't exist. """
    rogkit_toml_path = user_rogkit_toml_path()
    if not os.path.exists(rogkit_toml_path):
        try:
            with open(rogkit_toml_path, 'w') as f:
                toml.dump(DEFAULT_ROGKIT_TOML, f)
            print(f"Created {rogkit_toml_path} with default settings.")
        except IOError as e:
            print(f"Error creating {rogkit_toml_path}: {e}", file=sys.stderr)
    else:
        print(f"{rogkit_toml_path} already exists.")

def load_rogkit_toml():
    """ Load and return the contents of ~/.rogkit.toml as a dict. """
    rogkit_toml_path = user_rogkit_toml_path()
    if not os.path.exists(rogkit_toml_path):
        setup_rogkit_toml()

    try:
        with open(rogkit_toml_path, 'r') as f:
            return toml.load(f)
    except IOError as e:
        print(f"Error reading {rogkit_toml_path}: {e}", file=sys.stderr)
        sys.exit(1)

def print_default_toml():
    """ Print the default TOML configuration. """
    print(toml.dumps(DEFAULT_ROGKIT_TOML))

def parse_args():
    """ Setup command-line argument parsing. """
    parser = argparse.ArgumentParser(description="Rogkit TOML tool")
    parser.add_argument("-c", "--create", action="store_true", help="Create ~/.rogkit.toml with default settings (if it doesn't exist)")
    parser.add_argument("--default", action="store_true", help="Print default rogkit toml")
    return parser.parse_args()

def main():
    args = parse_args()
    print("Rogkit TOML Tool")

    if args.create:
        setup_rogkit_toml()

    if args.default:
        print_default_toml()
    else:
        config = load_rogkit_toml()
        print(toml.dumps(config))

if __name__ == "__main__":
    main()