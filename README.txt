# RogKit

Add this to your ~/bashrc:
```
# RogKit
if [ -d ~/bin/rogkit/bin ] && [[ ":$PATH:" != *":~/bin/rogkit/bin:"* ]]; then
    export PATH="$PATH:~/bin/rogkit/bin"
fi
if [ -f ~/bin/rogkit/bin/aliases ]; then
    source ~/bin/rogkit/bin/aliases
fi
```