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
chmod +x "$INSTALL/rogkit/bin/*"

# install for clipboard functionality
sudo apt install wl-clipboard
```
Add this to your `~/bashrc` (or `~/.zshrc`):
```
# RogKit
INSTALL=~/opt
ROGKIT_BIN="$INSTALL/rogkit/bin"

if [ -d "$ROGKIT_BIN" ] && [[ ":$PATH:" != *":$ROGKIT_BIN:"* ]]; then
    export PATH="$PATH:$ROGKIT_BIN"
fi

if [ -f "$ROGKIT_BIN/aliases" ]; then
    source "$ROGKIT_BIN/aliases"
fi
```
Then reload your `~/bashrc` (or `~/.zshrc`):
```
source ~/bashrc  # or source ~/.zshrc
```
### Commands

| Command | Description       |
|---------|-------------------|
| backup  | Backup files      |
| bignum  | Show big numbers  |
| bytes   | Bytes to KB/MB/GB |
| clip    | Copy to clipboard |
| pw      | Generate password |
| rcase   | rANdoMcAse text   |
| seconds | Seconds to H/M/S  |
| strike  | Strikethru text   |
| tim     | Sync clock        |
| update  | Update system     |


### Notes:

* More utilities to come

Roger D.