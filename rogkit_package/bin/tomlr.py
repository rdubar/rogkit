import os
import toml
import argparse
import sys
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

def get_default_toml():
    return DEFAULT_ROGKIT_TOML

def write_default_toml():
    toml_string = toml.dumps(get_default_toml())
    toml_path = toml_sample_path
    if os.path.exists(toml_path):
        prompt = input(f"{toml_path} already exists. Press y overwrite, n to cancel: ")
    if prompt.lower() not in ['y', 'yes']:
        print("Aborting.")
        return
    try:
        with open(toml_path, 'w') as f:
            f.write(toml_string)
        print(f"Wrote {toml_path} with default settings.")
    except IOError as e:
        print(f"Error writing {toml_path}: {e}", file=sys.stderr)
        sys.exit(1)


def parse_args():

    """ Setup command-line argument parsing. """
    parser = argparse.ArgumentParser(description="Rogkit TOML tool")
    parser.add_argument("-c", "--create", action="store_true", help="Create ~/.rogkit.toml with default settings (if it doesn't exist)")
    parser.add_argument("-d", "--default", action="store_true", help="Print default rogkit toml")
    parser.add_argument("-s", "--show", action="store_true", help="Show current rogkit toml")
    parser.add_argument("-w", "--write", action="store_true", help="Write default rogkit toml to rogkit_sample.toml")
    parser.add_argument("--lowercase", action="store_true", help="Make all keys in the current rogkit toml lowercase")
    return parser.parse_args()

def main():
    args = parse_args()
    print("Rogkit TOML Tool")

    if args.write:
        write_default_toml()
    if args.create:
        setup_rogkit_toml()
    if args.lowercase:
        make_cuttent_rogkit_toml_lowercase()
    if args.default:
        toml_string = toml.dumps(get_default_toml())
        print(toml_string)
    elif args.show:
        print(f'Current rogkit toml: {user_rogkit_toml_path()}')
        config = load_rogkit_toml()
        print(toml.dumps(config))

if __name__ == "__main__":
    main()