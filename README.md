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
INSTALL=~/opt
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
INSTALL=~/opt
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

RogKit ships several performance-sensitive tools as Go binaries (`replacer`, `files`, `ishtime`, etc.). Build them once and they’ll be available on `PATH` via the aliases file.

### Build All Go Commands

```bash
cd ~/opt/rogkit
./scripts/build_go.sh
```

The script runs `go install ./cmd/...` with `GOBIN` pointing to `go/bin`, so every command under `go/cmd` is rebuilt together.

### Usage

After building, use the Go versions directly:

```bash
replacer --find TODO --path /some/project
files --folder /some/project TODO
ishtime --time 1115
```

Re-run the build script whenever Go sources change or after pulling updates.

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

### 📺 Media Library Management

| Command | Description | Aliases |
|---------|-------------|---------|
| `media` | Main Plex media library interface | `m` |
| `plex` | Plex server operations | `p` |
| `plex_db` | Inspect Plex SQLite database | `pd` |
| `media_files` | Scan and analyze media files | `mfiles`, `mf` |
| `media_scan` | Display technical video details | `mscan` |
| `media_play` | Stream videos via SFTP (experimental) | `play` |
| `shrink` | Find uncompressed DVD rips | - |
| `tmdb` | TMDb API metadata manager | - |
| `tkm` | Tkinter GUI media search | - |

`pd` (no args) lists the 10 most recently added items. `pd tarantino -n 20 -i -p` mirrors the formatted Plex CLI output (title + year, size, resolution, runtime, disk), and `pd tarantino -z` shows every match sorted by year. Add `--deep` when you need slower summary/path/tag matching.

**Media Library Features:**
- SQLite database with SQLAlchemy ORM
- Fuzzy search with thefuzz
- TMDB metadata integration
- Duplicate detection and removal
- Custom CSV import for additional media
- Resolution, codec, and bitrate tracking
- Database backup/restore (`-F`/`-U`)
- Export to DataFrame/CSV

### 🗂️ File System Operations

| Command | Description | Aliases |
|---------|-------------|---------|
| `backup` | Backup files to archive | `bac` |
| `collate` | Merge files from subdirectories | - |
| `delete` | Safe file deletion with confirmation | `del` |
| `renamer` | Batch rename files with patterns | - |
| `replacer` | Find and replace text in files | - |
| `files` | Advanced file searching | - |
| `search` | Search for text in files | - |
| `dirs` | Directory analysis and statistics | - |
| `empties` | Find empty files and directories | - |
| `hidden` | Discover hidden files | - |
| `large` | Find large files and directories | - |
| `clean` | Clean translation files | - |
| `cleanup` | Experimental disk cleanup | - |
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

### 💻 System Information & Utilities

| Command | Description | Aliases | Python Import |
|---------|-------------|---------|---------------|
| `location` | Show location and weather | `loc` | `from location import get_weather_data` |
| `space` | Disk space usage | - | - |
| `mapper` | Create map from CSV addresses | - | - |
| `syscheck` | System health check | - | - |
| `sysinfo` | Detailed system information | - | - |
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
| `inter` | Run Open Interpreter | - |
| `fuzzy` | Fuzzy search utility | - |
| `rogstream` | Launch Streamlit dashboard using rogkit venv | - |

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
cd ~/opt/rogkit

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
print(strikethru("deprecated"))   # "d̶e̶p̶r̶e̶c̶a̶t̶e̶d̶"
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

# Plex media library
from rogkit_package.media.plex_library import PlexLibrary
library = PlexLibrary()
results = library.search("inception", fuzzy=90)
for movie in results:
    print(f"{movie.title} ({movie.year}) - {movie.resolution}")
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

### Media Library Management

```bash
# Initial database setup
media --reset                # Drop and rebuild database
media --update              # Sync with Plex server

# Search operations
media inception              # Basic search
media -f 85 inception       # Fuzzy search (85% match)
media "The Matrix" 1999     # Search with year

# Display options
media -a                     # Show all records
media -y -a                 # Show all, sorted by year
media -v -a                 # Show all, sorted by resolution
media -n 20 -l              # Show latest 20 additions

# Database maintenance
media -D                     # Remove duplicates
media -F                     # Freeze (backup) database
media -U                     # Unfreeze (restore) database
media --vacuum              # Optimize database
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

- [ ] Rename `plex_library`/`PlexLibrary` to `media_library`/`MediaLibrary`
- [ ] Integrate TOML config into `backup` command
- [ ] Complete `media_play` SSH streaming functionality
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
