import os
import toml
import argparse
import sys

DEFAULT_ROGKIT_TOML = {
    "backup" : { 
        "backup_from": ["~/"],
        "backup_to": ["~/archive/"],
    },
    "plex": {"plex_server_url": "", "plex_server_token": ""},
    "openweather": {"openweather_api_key": ""},
    "ipinfo": {"ipinfo_api_key": ""},
    "yout": { "temp_folder" : "", "download_folder" : "", "default_input_file" : "" } 
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

def make_keys_lowercase(d):
    """ Recursively make all keys in a dict lowercase. """
    if isinstance(d, dict):
        return {k.lower(): make_keys_lowercase(v) for k, v in d.items()}
    else:
        return d

def make_cuttent_rogkit_toml_lowercase():
    """ Load the current rogkit toml and make all keys lowercase. """
    toml_lower = make_keys_lowercase(load_rogkit_toml())
    # write the file
    rogkit_toml_path = user_rogkit_toml_path()
    print(f"Writing {rogkit_toml_path} with lowercase keys.")
    try:
        with open(rogkit_toml_path, 'w') as f:
            toml.dump(toml_lower, f)
    except IOError as e:
        print(f"Error writing {rogkit_toml_path}: {e}", file=sys.stderr)
        sys.exit(1)

def parse_args():

    """ Setup command-line argument parsing. """
    parser = argparse.ArgumentParser(description="Rogkit TOML tool")
    parser.add_argument("-c", "--create", action="store_true", help="Create ~/.rogkit.toml with default settings (if it doesn't exist)")
    parser.add_argument("-s", "--show", action="store_true", help="Show current rogkit toml")
    parser.add_argument("--lowercase", action="store_true", help="Make all keys in the current rogkit toml lowercase")
    parser.add_argument("--default", action="store_true", help="Print default rogkit toml")
    return parser.parse_args()

def main():
    args = parse_args()
    print("Rogkit TOML Tool")

    if args.create:
        setup_rogkit_toml()
    if args.lowercase:
        make_cuttent_rogkit_toml_lowercase()
    if args.default:
        print_default_toml()
    elif args.show:
        print(f'Current rogkit toml: {user_rogkit_toml_path()}')
        config = load_rogkit_toml()
        print(toml.dumps(config))

if __name__ == "__main__":
    main()