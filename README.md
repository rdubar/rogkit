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
python3.12 -m venv --without-pip venv
source venv/bin/activate
curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
python get-pip.py
rm get-pip.py
pip install -r requirements.txt

# Make scripts executable
chmod +x "$INSTALL/rogkit/rogkit_package/bin/*"

# install for clipboard functionality
sudo apt install wl-clipboard
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
### Commands

| Command  | Description       | Python Imports                        |
|----------|-------------------|---------------------------------------|
| backup   | Backup files      |                                       |
| bignum   | Show big numbers  | from bignum import bignum             |
| bytes    | Bytes to KB/MB/GB | from bytes import byte_size           |
| clean    | Clean translation |                                       |
| clip     | Copy to clipboard | from clipboard import clipboard       |
| config   | config .ini tool  | from config import read_config        |
| empties  | Check for empties |                                       |
| fakes    | Generate text etc | from fakes import fake_data           |
| files    | Find files & dirs | from files import find_files          |
| heic     | Fix heics to jpgs |                                       |
| loc      | Show locale info  | from location import get_weather_data |
| media    | Media Libary      |                                       |
| purge    | Purge files       | from purge import delete_files        |
| pw       | Generate password | from pw import PasswordGenerator      |
| replacer | Replace text      |                                       |
| rcase    | rANdoMcAse text   | from randomcase import randomcase     |
| search   | Search for text   | from search import search_folder      |
| seconds  | Seconds to H/M/S  | from seconds import convert_seconds   |
| spot     | Spotify cli tool  |                                       |
| strike   | Strikethru text   | from strike import strikethru         |
| tim      | Sync system clock |                                       |
| update   | Update system     |                                       |
|          |                   |                                       |
| rogkit   | Display this info |                                       |

### Known Issues:

* backup: not excluding files correctly? Add test showing what would be archived

### Experimental

* bac: a better, simpler backup. Test code. 

Roger D.