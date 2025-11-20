# RogKit

**Utility toolkit for system administration, media management, and productivity.**

A collection of 85+ Python (and some Go) utilities for developers and system administrators, featuring powerful Plex media library management, file operations, text processing, and system utilities.

---

## 🚀 Features

- **📺 Media Library Management** - Full Plex integration with SQLite caching, fuzzy search, and TMDB metadata
- **🗂️ File System Operations** - Backup, cleaning, renaming, searching, and analysis tools
- **🖼️ Image & Document Processing** - HEIC conversion, resizing, PDF generation, transparency tools
- **📊 Data Format Tools** - XML, TOML, ISO, and JSON parsing and manipulation
- **🔢 Calculation & Conversion** - Time, bytes, numbers, ages, and unit conversions
- **🐳 Container Management** - Docker utilities
- **🔐 Security Tools** - Password generation with strength analysis
- **🎯 Text Utilities** - Clipboard, formatting, case conversion, and ASCII art
- **ℹ️ System Information** - Hardware, network, location, and weather data
- **⚡ Go CLI Utilities** - High-performance binaries for heavy file operations and time utilities
- **🎮 Entertainment** - Games, video downloads, Wikipedia queries

---

## 📦 Installation

### Prerequisites

- Python 3.11+ (3.12 recommended)
- Go 1.22+ (optional, required for Go CLI tools)
- Git and GitHub CLI (optional for clone)
- Linux: Additional packages for full functionality (see below)

### Quick Install

```bash
# Set up the installation directory
INSTALL=~/dev
mkdir -p "$INSTALL"
cd "$INSTALL"

# Clone repository
gh repo clone rdubar/rogkit
# or: git clone https://github.com/rdubar/rogkit.git

cd rogkit

# Option 1: Using uv (recommended - faster, better dependency management)
curl -LsSf https://astral.sh/uv/install.sh | sh
uv python pin 3.12
uv sync --all-extras  # Install all dependencies (use --group ui for Streamlit)

# Option 2: Using traditional venv
python3.12 -m venv --without-pip venv
source venv/bin/activate
curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
python get-pip.py
rm get-pip.py
pip install pipreqs
pipreqs . --force

# Install requirements (with error handling)
cat requirements.txt | while read package; do
    echo "Installing $package..."
    pip install "$package" || echo "Failed to install $package, continuing..."
done

# Install additional core dependencies
pip install ffmpeg-python python-dotenv sqlalchemy requests-html

# Set up configuration
mkdir -p ~/.config/rogkit
cp rogkit_sample.toml ~/.config/rogkit/config.toml

# Make scripts executable
chmod +x rogkit_package/bin/*
```

### Linux System Dependencies

```bash
sudo apt update

# For HEIC image processing
sudo apt install libheif-dev

# For clipboard functionality
sudo apt install wl-clipboard

# For video downloading and processing
sudo apt install ffmpeg
```

### Shell Integration

Add to your `~/.bashrc` or `~/.zshrc`:

```bash
# RogKit Integration
INSTALL=~/dev
ROGKIT="$INSTALL/rogkit"
ROGKIT_BIN="$ROGKIT/rogkit_package/bin"
ROGKIT_GO="$ROGKIT/go"
ROGKIT_GO_BIN="$ROGKIT_GO/bin"

# Add to PATH (optional, if not using aliases)
if [ -d "$ROGKIT_BIN" ] && [[ ":$PATH:" != *":$ROGKIT_BIN:"* ]]; then
    export PATH="$PATH:$ROGKIT_BIN"
fi
if [ -d "$ROGKIT_GO_BIN" ] && [[ ":$PATH:" != *":$ROGKIT_GO_BIN:"* ]]; then
    export PATH="$PATH:$ROGKIT_GO_BIN"
fi

# Load aliases (recommended)
if [ -f "$ROGKIT/aliases" ]; then
    source "$ROGKIT/aliases"
fi
```

Reload your shell configuration:

```bash
source ~/.bashrc  # or source ~/.zshrc
```

---

## 🐹 Go Utilities

RogKit ships several experimental Go binaries for high-speed file/directory operations. Build them once and they’ll be available on `PATH` via the aliases file.

### Build All Go Commands

```bash
cd ~/dev/rogkit
./scripts/build_go.sh
```

The script runs `go install ./cmd/...` with `GOBIN` pointing to `go/bin`, so every command under `go/cmd` is rebuilt together.

### Usage

After building, use the Go utilities directly:

```bash
dirfind project-name           # Fuzzy dir locating via fd + Go
fastfind --path ~/code foo     # Parallel content search (ripgrep-like)
finder --root ~/media "foo"    # Interactive finder with cached results
ishtime --time 1115            # Quick time difference calculator
replacer --find TODO --path /some/project
replacer --find TODO --replace DONE --write --confirm --path /some/project
search --path /some/project TODO "bar baz" --limit 10
```

Re-run the build script whenever Go sources change or after pulling updates.

#### Available Go Commands

| Command   | Description |
|-----------|-------------|
| `dirfind` | Experimental fuzzy directory locator powered by `fd` and Go. Supports caching, hidden-dir search, and optional subshell launch. |
| `fastfind` | High-performance content search tailored for large trees. |
| `finder`  | Helper used by some scripts for cached lookups/interactions. |
| `ishtime` | “Is it time?” helper to convert hhmm strings to readable deltas. |
| `replacer` | Mass find/replace utility with confirmation prompts. |
| `search`  | Multi-term project searcher (ripgrep-style) with batching. |

---

## ⚙️ Configuration

### Primary Configuration File

Edit `~/.config/rogkit/config.toml` for API keys and tool settings:

```toml
# Plex Media Server
[plex]
plex_server_url = "http://192.168.1.100"
plex_server_token = "your_plex_token_here"
plex_server_port = 32400

# TMDb API
[tmdb]
tmdb_api_key = "your_tmdb_api_key_here"

# Video Downloader (vido)
[vido]
temp_folder = "/tmp/vido"
download_folder = "~/Downloads/Videos"
default_input_file = "~/urls.txt"

# MongoDB
[mongodb]
uri = "mongodb://localhost:27017"
db = "rogkit"
collection = "logs"

# Translation Cleaner
[clean]
script_path = "/absolute/path/to/translation_clean.sh"
root_directory = "/absolute/path/to/project/root"
```

**Legacy fallback**: `~/.rogkit.toml` (still supported by some tools)

---

## 📚 Command Reference

### Core Commands

| Command | Description | Aliases |
|---------|-------------|---------|
| `rogkit` | Display command reference | - |
| `update` | Update system packages | - |

### 🤖 AI & API Tools

| Command | Description | Aliases |
|---------|-------------|---------|
| `aish` | AI-powered shell assistant | - |
| `amaz` | AWS CLI tool | - |
| `chat` | Interactive AI chat | - |
| `lm` | Run local LLM (LM application) | - |

### 📺 Media Toolkit

| Command | Description | Aliases |
|---------|-------------|---------|
| `media` (daemon-backed) | Daemon-backed media search with local caches | `pd`, `p`, `pb` |
| `media.extra_sources.integrate` | Merge external catalogues into the cache | `integrate` |
| `tmdb` | TMDb metadata manager and extras JSON builder | - |
| `media_files` | Scan and analyze media files | `mfiles`, `mf` |
| `media_scan` | Display technical video details | `mscan` |
| `media_play` | Stream videos via SFTP (experimental) | `play` |
| `shrink` | Find uncompressed DVD rips | - |
| `tkm` | Experimental GUI media search | - |

`media` (no args) lists the ten newest additions. Add a search term for instant cache-backed lookups, `-z` to show every match sorted by year, `-a/--all` to disable pagination, `--deep` for summary/path/tag matches from the raw Plex database, `--people` to focus on actors/directors via SQL, and `--stats` to print totals for the displayed set.

#### Media Workflow

1. **Refresh the Plex snapshot:** `media --update` uses rsync with compression to pull the live database (skipping the download entirely if it has not changed) and automatically merges any extras JSON cache into the search cache. Use `media --update-plex` if you only want the raw Plex snapshot without merging extras (SSH settings come from `config.toml`).
2. **Regenerate TMDb extras from CSV:** `tmdb --csv data/media.csv` (defaults to `data/media.csv` if omitted). Use `--refresh` to force new lookups.
3. **Merge external catalogues manually (optional):** `integrate` writes the extras JSON into `plex_search_cache.sqlite3`, deduping on `(source, source_id)`, then rebuilds the pickle cache (already handled by `media --update`).
4. **Search instantly:** `media` for recents, `media "<title>"`, `media "<title>" --deep`, `media "<title>" -z`, or append `--stats` to any of them for totals.
5. **Restart the daemon after updates:** If you keep the media daemon running in the background (e.g., via `media --daemon`), restart it after upgrading the CLI—use `media --stop-daemon` followed by `media --daemon`—so new flags like `--people` are recognized.

The CLI header shows cache size and age so you know when to rerun the refresh steps.

### 🗂️ File System Operations

| Command | Description | Aliases |
|---------|-------------|---------|
| `backup` | Backup files to archive | `bac` |
| `collate` | Merge files from subdirectories | - |
| `delete` | Safe file deletion with confirmation | `del` |
| `renamer` | Batch rename files with patterns | - |
| `replacer` | Find and replace text in files | - |
| `files` | Advanced file searching | - |
| `search` | Go multicore content search | - |
| `dirs` | Directory analysis and statistics | - |
| `empties` | Find empty files and directories | - |
| `hidden` | Discover hidden files | - |
| `large` | Find large files and directories | - |
| `clean` | Clean translation files | - |
| `cleaner` | Experimental disk cleaner | - |
| `purge` | Bulk file deletion | - |

### 🖼️ Image & Document Processing

| Command | Description | Aliases |
|---------|-------------|---------|
| `imager` | Batch resize/convert images (HEIC→JPG) | - |
| `pdfer` | Convert images to PDF | - |
| `transparent` | Make colors transparent in images | - |

### 📝 Text & String Utilities

| Command | Description | Aliases | Python Import |
|---------|-------------|---------|---------------|
| `clipboard` | Copy text to clipboard | `clip` | `from clipboard import clipboard` |
| `randomcase` | rAnDoM cAsE text generator | `rcase` | `from randomcase import randomcase` |
| `strike` | S̶t̶r̶i̶k̶e̶t̶h̶r̶o̶u̶g̶h̶ text | - | `from strike import strikethru` |
| `fig` | ASCII art text generator | - | `from fig import generate_ascii_art` |
| `plural` | Pluralize words | - | `from plural import plural` |
| `padding` | Remove padding files | - | - |

### 📊 Data Format Tools

| Command | Description | Aliases |
|---------|-------------|---------|
| `xmlr` | XML/XMLRPC utilities | `xml`, `api` |
| `tomlr` | TOML configuration manager | `toml` |
| `iso` | Extract largest file from ISO | - |
| `miso` | Create video from ISO | - |

**TOML Manager Features:**
- Create/edit rogkit config
- Validate TOML syntax
- Convert case (uppercase/lowercase)
- Merge TOML files
- Display current configuration

### 🔢 Calculation & Conversion Tools

| Command | Description | Aliases | Python Import |
|---------|-------------|---------|---------------|
| `bignum` | Format large numbers | - | `from bignum import bignum` |
| `bytes` | Convert bytes to KB/MB/GB | - | `from bytes import byte_size` |
| `rounder` | Round decimals intelligently | - | `from rounder import round_decimals` |
| `seconds` | Convert seconds to H:M:S | - | `from seconds import convert_seconds` |
| `catyears` | Cat age to human years | - | - |
| `generations` | Calculate genealogical generations | `gen` | - |
| `bmi_calc` | BMI calculator with progression | `bmi` | - |
| `multical` | Show date across multiple calendars | - | `from rogkit_package.bin.multical import main` |

#### Multi-calendar conversions

- Requires the `convertdate` dependency (installed automatically when you `uv sync`).
- Run directly with uv: `uv run python rogkit_package/bin/multical.py 2024-11-16`
- Omit the date to default to today; output includes Julian, Hebrew, Islamic (tabular and Umm al-Qura when available), Persian, Bahá'í, Indian Civil, and Mayan Long Count.

### 💻 System Information & Utilities

| Command | Description | Aliases | Python Import |
|---------|-------------|---------|---------------|
| `location` | Show location and weather | `loc` | `from location import get_weather_data` |
| `space` | Disk space usage | - | - |
| `mapper` | Create map from CSV addresses | - | - |
| `syscheck` | System health check | - | - |
| `system` | System utilities | - | - |
| `pyinfo` | Python environment info | - | - |
| `speeder` | Python benchmark across versions | - | - |

### 🐳 Container & Remote Management

| Command | Description | Aliases |
|---------|-------------|---------|
| `docker_bash` | Bash into Docker container | `dbash` |
| `spot` | Spotify CLI control | - |

### 🗄️ Database & Storage

| Command | Description | Aliases |
|---------|-------------|---------|
| `mongo` | MongoDB logging and queries | - |

### 🛠️ Development Tools

| Command | Description | Aliases |
|---------|-------------|---------|
| `nose` | Nosetests for Odoo/OpenERP | - |
| `venv` | Virtual environment setup | - |
| `inter` | Run Open Interpreter *(suspended – awaiting `tiktoken` Py3.14 support)* | - |
| `fuzzy` | Fuzzy search utility | - |
| `rogstream` | Launch Streamlit dashboard using rogkit venv | - |

> **Suspended:** `inter` currently ships as a stub because `open-interpreter` →
> `tiktoken` only supports up to Python 3.13. Re-enable once CPython 3.14 wheels exist.

### 🔐 Security & Utilities

| Command | Description | Aliases | Python Import |
|---------|-------------|---------|---------------|
| `pw` | Secure password generator | - | `from pw import PasswordGenerator` |
| `fakes` | Generate fake data (names, emails, etc.) | - | `from fakes import fake_data` |

### 🎮 Entertainment & Games

| Command | Description | Aliases |
|---------|-------------|---------|
| `dice` | Roll dice (D&D style) | - |
| `stars` | Print star patterns | - |
| `drying` | Should you hang laundry outside? | - |

### 🎥 Video & Media Download

| Command | Description | Aliases |
|---------|-------------|---------|
| `vido` | YouTube/video downloader (yt-dlp) | `yout` |

### 📖 Information & Reference

| Command | Description | Aliases | Python Import |
|---------|-------------|---------|---------------|
| `wikipedia` | Query Wikipedia | `w` | `from wikipedia import search_wikipedia` |

### 🖥️ Time Management

| Command | Description | Aliases |
|---------|-------------|---------|
| `tim` | System clock sync checker | - |

---

## 🎨 Streamlit Web Interface

Launch the interactive web interface:

```bash
# From within the rogkit directory
cd ~/dev/rogkit

# Option 1: Using system Streamlit (if installed globally)
streamlit run Home.py

# Option 2: Using rogkit venv (recommended for full functionality)
source venv/bin/activate
streamlit run Home.py

# Option 3: Using uv
uv run streamlit run Home.py
```

**Available Pages:**
- **Media** - Browse and visualize Plex library with charts
- **Password** - Interactive password generator
- **Randomcase** - Live random case converter

**Note:** The web interface will work with or without optional dependencies like `pyclip`. Some features (like clipboard auto-copy) may be unavailable depending on your installation method.

---

## 🐍 Python Import Examples

Import rogkit utilities directly in your Python scripts:

```python
# File size formatting
from rogkit_package.bin.bytes import byte_size
print(byte_size(1234567890))  # "1.23 GB"
print(byte_size(1234567890, unit="MB"))  # "1,234.57 MB"

# Text utilities
from rogkit_package.bin.randomcase import randomcase
from rogkit_package.bin.strike import strikethru
from rogkit_package.bin.plural import plural

print(randomcase("hello world"))  # "HeLLo WoRLd"
print(strikethru("obsolete"))     # "o̶b̶s̶o̶l̶e̶t̶e̶"
print(plural("person"))           # "people"

# Number formatting
from rogkit_package.bin.bignum import bignum
print(bignum(1234567))  # "1,234,567"

# Time conversions
from rogkit_package.bin.seconds import convert_seconds
print(convert_seconds(3665))  # "1 hour, 1 minute, 5 seconds"

# Password generation
from rogkit_package.bin.pw import PasswordGenerator
pw_gen = PasswordGenerator(length=16, alpha=True, numeric=True, special=True)
password = pw_gen.generate_and_store_password()

# Configuration management
from rogkit_package.bin.tomlr import load_rogkit_toml
config = load_rogkit_toml()
plex_url = config.get('plex', {}).get('plex_server_url')

# Plex media cache helpers
from argparse import Namespace
from rogkit_package.media.helpers import detect_db_path
from rogkit_package.media.search import format_pretty_row, run_pretty_search

db_path = detect_db_path()
if db_path:
    rows, total = run_pretty_search(
        db_path,
        ["inception"],
        limit=5,
        sort="title",
        reverse=False,
        deep=False,
    )
    print(f"{total} match(es) cached.")
    for row in rows:
        print(format_pretty_row(row, Namespace(length=80, info=False, path=False)))
else:
    print("Plex database not detected. Run `media --list-paths` for help.")
```

---

## 📖 Documentation

All 85+ Python files include comprehensive docstrings:

- **Module-level docstrings** - Purpose and overview
- **Function/class docstrings** - Parameters, return values, examples
- **Type hints** - For better IDE support and type checking

Example:

```bash
python -c "import rogkit_package.bin.bytes; help(rogkit_package.bin.bytes.byte_size)"
```

---

## 🔧 Development

### Using uv (Recommended)

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Sync core dependencies
uv sync

# Install all extras (media/ui/aws/db/data/cli/dev)
uv sync --all-extras

# Add/upgrade dependencies
uv add requests-html           # Add new package
uv add -U requests-html        # Upgrade package

# Run tools directly
uv run python rogkit_package/bin/vido.py --help

# Export requirements
uv export -o requirements.txt
```

### Dependency Groups

- **media** - Plex, TMDb, video processing
- **ui** - Streamlit web interface
- **aws** - AWS/Boto3 tools
- **db** - MongoDB, database tools
- **data** - Pandas, visualization
- **cli** - Advanced CLI features
- **dev** - Development and testing tools

---

## 🎯 Common Workflows

### Plex Database Workflow

```bash
# 1. Optional: keep a fresh Plex snapshot locally
pd --update

# 2. Rebuild external catalogue metadata from CSV sources
tmdb --csv data/media.csv
# (Add --refresh to force new TMDb lookups)

# 3. Merge extras into the fast cache
integrate

# 4. Search instantly
pd                     # newest 10 items
pd "aliens"            # cache-backed title match
pd "aliens" --deep     # include summary/path/tag matching
pd "aliens" --stats    # add aggregate totals for the displayed results
pd "aliens" -z         # list every match sorted by year
```

### File Operations

```bash
# Backup with compression
backup ~/important_docs ~/backup_location

# Safe file deletion
delete -i *.tmp             # Interactive mode
del old_file.txt           # Quick alias

# Batch renaming
renamer "s/IMG_/Photo_/" *.jpg

# Find large files
large ~/Downloads --min-size 100MB
```

### Image Processing

```bash
# Batch convert and resize images
imager ~/Photos -c -s 200 -l 1200

# Create PDF from images
pdfer ~/scanned_docs

# Remove white background
transparent image.png -c FFFFFF -t 8
```

### Text & Data

```bash
# Copy to clipboard
echo "Hello World" | clip

# Generate random case
echo "hello world" | rcase

# Format numbers
bignum 1234567890          # 1,234,567,890

# Convert bytes
bytes 1234567890           # 1.23 GB
```


### Commands

| Command | Description | Aliases |
|---------|-------------|---------|
| `media` | Main Plex media library interface | `m` |

### Legacy Workflow

```bash
# Database maintenance
media --reset              # Drop and rebuild database
media --update             # Sync with Plex server

# Search operations
media inception            # Basic search
media -f 85 inception      # Fuzzy search (85% match)
media "The Matrix" 1999    # Search with year

# Display options
media -a                   # Show all records
media -y -a                # Show all, sorted by year
media -v -a                # Show all, sorted by resolution
media -n 20 -l             # Show latest 20 additions

# Database tools
media -D                   # Remove duplicates
media -F                   # Freeze (backup) database
media -U                   # Unfreeze (restore) database
media --vacuum             # Optimise database
```

**Feature Highlights:**
- SQLite database with SQLAlchemy ORM
- Fuzzy search via `thefuzz`
- TMDb metadata integration
- Duplicate detection and removal
- Custom CSV import support
- Resolution, codec, and bitrate tracking
- Database backup/restore (`-F`/`-U`)
- Data export to DataFrame/CSV

---

## 🤝 Contributing

This is a personal toolkit, but suggestions and improvements are welcome!

1. Fork the repository
2. Create a feature branch
3. Add comprehensive docstrings
4. Test your changes
5. Submit a pull request

---

## 📝 TODO

- [ ] Add comprehensive test suite
- [ ] Create detailed wiki documentation
- [ ] Package distribution via PyPI

---

## 📜 License

Personal use. See repository for license details.

---

## 👤 Author

**Roger D.**

A comprehensive toolkit built over time for personal productivity and system administration.

---

## 🙏 Acknowledgments

Built with:
- **Python 3.12** - Core language
- **SQLAlchemy** - Database ORM
- **Streamlit** - Web interface
- **PlexAPI** - Plex integration
- **yt-dlp** - Video downloading
- **Pillow** - Image processing
- **thefuzz** - Fuzzy string matching
- **pandas** - Data analysis

And many other excellent open-source libraries!

---

*For detailed alias reference, see the [aliases](aliases) file.*
