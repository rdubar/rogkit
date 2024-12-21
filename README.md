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
cp rogkit.sample.toml ~/rogkit.tomlcd ..
# Make scripts executable
chmod +x rogkit_package/bin/*

# additional linux installs
sudo apt update
# for heic processing by imager
sudo apt install libheif-dev
# for clipboard functionality
sudo apt install wl-clipboard
# for video downloading with yout
sudo apt install ffmpeg

```
Add this to your `~/bashrc` (or `~/.zshrc`):
```
# RogKit
INSTALL=~/opt
ROGKIT="$INSTALL/rogkit"
ROGKIT_BIN="$INSTALL/rogkit/bin"
if [ -d "$ROGKIT_BIN" ] && [[ ":$PATH:" != *":$ROGKIT_BIN:"* ]]; then
    export PATH="$PATH:$ROGKIT_BIN"
fi
if [ -f "$ROGKIT/aliases" ]; then
    source "$ROGKIT/aliases"
fi
```
Then reload your `~/bashrc` (or `~/.zshrc`):
```
source ~/bashrc  # or source ~/.zshrc
```
### Credentials
Edit `~/rogkit.toml` to add your own credentials and API keys.
### Commands

| Command  | Description        | Python Imports                         |
|----------|--------------------|----------------------------------------|
| backup   | Backup files       |                                        |
| bignum   | Show big numbers   | from bignum import bignum              |
| bytes    | Bytes to KB/MB/GB  | from bytes import byte_size            |
| clean    | Clean translation  |                                        |
| clip     | Copy to clipboard  | from clipboard import clipboard        |
| empties  | Check for empties  |                                        |
| fakes    | Generate text etc  | from fakes import fake_data            |
| gen      | show generations   |                                        |
| files    | Find files & dirs  | from files import find_files           |
| hidden   | Find hidden items  |                                        |
| imager   | Resize images      |                                        |
| loc      | Show locale info   | from location import get_weather_data  |
| media    | Media Libary       |                                        |
| plural   | Pluralise a word   | from plural import plural              |
| purge    | Purge files        | from purge import delete_files         |
| pw       | Generate password  | from pw import PasswordGenerator       |
| remote   | run remote/local   | from remote import execute_command     |
| replacer | Replace text       |                                        |
| rcase    | rANdoMcAse text    | from randomcase import randomcase      |
| rounder  | Round decimals     | from rounder import round_decimals     |
| search   | Search for text    | from search import search_folder       |
| seconds  | Seconds to H/M/S   | from seconds import convert_seconds    |
| spot     | Spotify cli tool   |                                        | 
| strike   | Strikethru text    | from strike import strikethru          |
| tim      | Sync system clock  |                                        |
| space    | Show free space    |                                        |
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
* dice: throw dice
* inter: run Open Interpreter
* large: show folders with multiple very large files
* lm: run a local LLM (using the LM application)
* mcscan: scan media for resolution, bitrate etc. 
* miso: make video from an iso file
* mongo: basic MongoDB tools
* nose: run nosetests in ERP
* padding: delete Internet Archive padding files
* pdfer: experimental images to pdf
* speeder: run with python interpreters as a benchmark
* tkm: am experimentl graphical front end for media searches
* transparent: make image transparent
* xmlr: an xmlrpc tool

Use `streamlit run Home.py` to try out the Streamlit frontend.

Roger D.