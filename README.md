# RogKit
### Installation
Use as needed...
```
# Set up the installation directory
INSTALL=~/opt
mkdir -p "$INSTALL"  # Create the directory if it does not exist
cd "$INSTALL"

# Install and setup
gh repo clone rdubar/rogkit
cd rogkit
python3.13 -m venv --without-pip venv
source venv/bin/activate
curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
python get-pip.py
rm get-pip.py
pip install pipreqs 
pipreqs . --force
# Install requirements, advising of any issues...
cat requirements.txt | while read package; do
    echo "Installing $package..."
    pip install "$package" || echo "Failed to install $package, continuing..."
done
pip install ffmpeg-python python-dotenv sqlalchemy requests-html
mkdir -p ~/.config/rogkit
cp rogkit_sample.toml ~/.config/rogkit/config.toml
cd ..
# Make scripts executable
chmod +x rogkit_package/bin/*

# additional linux installs
sudo apt update
# for heic processing by imager
sudo apt install libheif-dev
# for clipboard functionality
sudo apt install wl-clipboard
# for video downloading with yt-dlp
sudo apt install ffmpeg

```
Add this to your `~/bashrc` (or `~/.zshrc`):
```
# RogKit
INSTALL=~/opt
ROGKIT="$INSTALL/rogkit"
ROGKIT_BIN="$ROGKIT/rogkit_package/bin"
if [ -d "$ROGKIT_BIN" ] && [[ ":$PATH:" != *":$ROGKIT_BIN:"* ]]; then
    export PATH="$PATH:$ROGKIT_BIN"
fi
if [ -f "$ROGKIT/aliases" ]; then
    source "$ROGKIT/aliases"
fi
```
Then reload your `~/.bashrc` (or `~/.zshrc`):
```
source ~/.bashrc  # or source ~/.zshrc
```
### Credentials
Preferred: edit `~/.config/rogkit/config.toml` to add your credentials and API keys.
Legacy fallback (still supported by some tools): `~/.rogkit.toml`.

Example config:
```toml
[vido]
temp_folder = "/path/to/tmp"
download_folder = "/path/to/downloads"
default_input_file = "/path/to/urls.txt"

[clean]
# path to your translation_clean.sh script
script_path = "/absolute/path/to/translation_clean.sh"
# base directory to search for .po/.pot files
root_directory = "/absolute/path/to/project/root"
```
### Commands

| Command  | Description        | Python Imports                         |
|----------|--------------------|----------------------------------------|
| backup   | Backup files       |                                        |
| bignum   | Show big numbers   | from bignum import bignum              |
| bytes    | Bytes to KB/MB/GB  | from bytes import byte_size            |
| clean    | Clean translation  |                                        |
| clip     | Copy to clipboard  | from clipboard import clipboard        |
| collate  | Collate files      |                                        |
| delete   | Safe delete files  | from delete import safe_delete         |
| empties  | Check for empties  |                                        |
| fakes    | Generate text etc  | from fakes import fake_data            |
| gen      | show generations   |                                        |
| files    | Find files & dirs  | from files import find_files           |
| fig      | Generate ascii art | from fig import generate_ascii_art     |
| hidden   | Find hidden items  |                                        |
| imager   | Resize images      |                                        |
| loc      | Show locale info   | from location import get_weather_data  |
| media    | Media Library      |                                        |
| plural   | Pluralise a word   | from plural import plural              |
| purge    | Purge files        | from purge import delete_files         |
| pw       | Generate password  | from pw import PasswordGenerator       |
| remote   | run remote/local   | from remote import execute_command     |
| renamer  | Rename files.      |                                        |
| replacer | Replace text       |                                        |
| rcase    | rANdoMcAse text    | from randomcase import randomcase      |
| rounder  | Round decimals     | from rounder import round_decimals     |
| search   | Search for text    | from search import search_folder       |
| seconds  | Seconds to H/M/S   | from seconds import convert_seconds    |
| spot     | Spotify cli tool   |                                        | 
| strike   | Strikethru text    | from strike import strikethru          |
| tim      | Sync system clock  |                                        |
| space    | Show free space    |                                        |
| syscheck | Check system info  |                                        |
| sysinfo  | Show system info   |                                        |
| tomlr    | Rogkit TOML tools  | from tomlr import load_rogkit_toml     |
| update   | Update system      |                                        |
| wikipedia| Query Wikipedia    | from wikipedia import search_wikipedia |
| venv     | Activate venv      |                                        |
| vido     | Video downloads    |                                        |
|          |                    |                                        |
| rogkit   | Display this info  |                                        |

### TODO

* media: rename plex_library  / PlexLibrary to media_library / MediaLibrary
* toml: use in backup

### Experimental

* aish: an AI shell
* amaz: an AWS cli tool
* bmi_calc
* catyears: show a cat's age in human years
* cleanup: experimental disk cleanup utility
* dice: throw dice
* docker_bash / dbash: bash shell into a docker container
* drying: should you put your drying outside? 
* inter: run Open Interpreter
* iso: extract the largest media file from an ISO file
* large: show folders with multiple very large files
* lm: run a local LLM (using the LM application)
* mapper: create a map from a csv of addresses
* mfiles media files utility
* mscan: scan media for resolution, bitrate etc. 
* miso: make video from an iso file
* mongo: basic MongoDB tools
* media_play: attempt to play video by ssh (not yet working)
* nose: run nosetests in ERP
* padding: delete Internet Archive padding files
* pdfer: experimental images to pdf
* pyinfo: show python system information
* speeder: run with python interpreters as a benchmark
* tkm: an experimental graphical front end for media searches
* transparent: make image transparent
* Plex: tool to connect to Plex server (and attempt to mark as watched)
* shrink: experimental utility to shrink DVD rips
* stars: print stars or other characters
* xmlr: an xmlrpc tool

Use `streamlit run Home.py` to try out the Streamlit frontend.

Roger D.

### Using uv (recommended)

Install `uv` and create the environment from the lock (or pyproject on first run):
```
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync            # core deps
uv sync --all-extras  # everything (media/ui/aws/db/data/cli/dev)
```

Daily workflow:
```
# add/upgrade a dependency
uv add requests-html           # add
uv add -U requests-html        # upgrade

# run tools
uv run python rogkit_package/bin/vido.py --help

# export pinned requirements if needed
uv export -o requirements.txt
```