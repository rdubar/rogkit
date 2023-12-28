# RogKit
Run:
```
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
* backup
* update

More to come.