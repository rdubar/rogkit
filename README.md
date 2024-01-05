# RogKit
Install (use as needed)
```
cd ~/bin
gh repo clone rdubar/rogkit
cd ~/bin/rogkit
python3.12 -m venv --without-pip venv
source venv/bin/activate
curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
python get-pip.py
rm get-pip.py
pip install -r requirements.txt
chmod +x  ~/bin/rogkit/bin/*
```
Add this to your ~/bashrc (or ~/.zshrc):
```
# RogKit
if [ -d ~/bin/rogkit/bin ] && [[ ":$PATH:" != *":~/bin/rogkit/bin:"* ]]; then
    export PATH="$PATH:~/bin/rogkit/bin"
fi
if [ -f ~/bin/rogkit/bin/aliases ]; then
    source ~/bin/rogkit/bin/aliases
fi
```
Then reload your ~/bashrc (or ~/.zshrc):
```
source ~/bashrc  # or source ~/.zshrc
```
Current commands are:
| Command | Description       |
|---------|-------------------|
| backup  | Backup files      |
| bignum  | Show big numbers  |
| bytes   | Bytes to KB/MB/GB |
| pw      | Generate password |
| rcase   | rANdoMcAse text   |
| seconds | Seconds to H/M/S  |
| tim     | Sync clock        |
| update  | Update system     |


More to come.