# rogkit

Personal command-line toolkit — 85+ tools built in Python, with Go binaries and a Rust experiment.

Built and maintained by Roger Dubar. Reflects a consistent engineering approach across a large, multi-language codebase: uniform conventions, modern tooling, and real daily use.

---

## Quick start

```sh
uv sync --all-extras   # install all dependencies
source aliases         # load shell aliases into your current shell
```

Reload on every new terminal session by sourcing `aliases` from your shell profile.

---

## Tool categories

### AI & LLM

| Tool | What it does |
|------|-------------|
| `aish` | AI-powered shell assistant — describe a task, get a shell command |
| `chat` | ChatGPT CLI client |
| `lm` | Local LLM chat client for LM Studio |

### File management

| Tool | What it does |
|------|-------------|
| `backup` | Archive files/folders with compression; supports incremental runs |
| `clean` | Translation file cleaner — removes unused keys from `.po`/`.pot` files |
| `collate` | Merge files from multiple locations into one directory |
| `delete` | Delete or trash files/folders; accepts piped filenames with confirmation |
| `dirs` | Recursive directory size calculator with sorted output |
| `empties` | Find empty folders and sparse directory trees |
| `fuzzy` | Fuzzy file/text search helper with interactive selection |
| `hidden` | Find hidden files and folders |
| `large` | Find large files over SSH |
| `paths` | Full-path search with optional media metadata display |
| `purge` | Remove junk files (`.DS_Store`, `__pycache__`, etc.) by pattern |
| `renamer` | Bulk file rename with pattern matching and preview |
| `space` | Disk usage summary, sorted by size |

### Media

The media subsystem is the most complex component — see [Media subsystem](#media-subsystem) below.

| Tool | What it does |
|------|-------------|
| `imager` | Batch image conversion and processing (resize, format, optimise) |
| `iso` | Extract main feature from a DVD/ISO using HandBrake |
| `media_files` | Scan and report on media file collections |
| `media_play` | Experimental local/remote media player |
| `media_scan` | Scan media files using ffmpeg-python |
| `miso` | Convert DVD/ISO to movie file |
| `pdfer` | Create PDFs from image sequences |
| `shrink` | Compress video files to target size/quality |
| `spot` | Spotify liked-songs manager (list, export, search) |
| `transparent` | Strip or add transparency to images |
| `vido` | Movie downloader with metadata lookup |

### System & network

| Tool | What it does |
|------|-------------|
| `cleaner` | System cleanup for macOS and Raspberry Pi |
| `docker_bash` | Interactive bash into a running Docker container |
| `location` | Current location and weather data |
| `speed_test` | Network speed test |
| `syscheck` | System health report: uptime, load, memory, kernel status |
| `system` | Enhanced system snapshot (CPU, memory, disk, network) |
| `time_check` | System clock check and NTP sync status |
| `venv_set` | Locate and activate virtual environments |

### Data & text utilities

| Tool | What it does |
|------|-------------|
| `bignum` | Convert large numbers to readable text (`1e12` → `1 trillion`) |
| `bytes` | Human-readable byte-size conversion (SI and binary units) |
| `clipboard` | Copy text to the system clipboard |
| `fakes` | Generate fake names, emails, addresses using Faker |
| `fig` | ASCII art text via pyfiglet |
| `generations` | Genealogy calculator — ancestors and DNA percentages per generation |
| `plural` | Pluralise English words correctly, including irregulars |
| `randomcase` | Convert text to random case |
| `rounder` | Round decimals while stripping unnecessary trailing zeros |
| `scrape` | Extract readable text from a URL, with pagination support |
| `seconds` | Convert seconds to human-readable durations |
| `stars` | Star/pattern generator |
| `strike` | Apply Unicode strikethrough to text |
| `wikipedia` | Search and fetch Wikipedia articles |

### Developer & integration tools

| Tool | What it does |
|------|-------------|
| `amaz` | AWS S3 file operations |
| `bmi_calc` | BMI calculator and progression tracker |
| `catyears` | Cat age to equivalent human years |
| `dice` | Dice roller (configurable count and sides) |
| `drying` | Clothes-drying weather advisor |
| `fakes` | Fake data generator (names, emails, addresses) |
| `mapper` | Address geocoding and map link generation |
| `mongo` | MongoDB query helper and logger |
| `multical` | Multi-calendar date conversion |
| `nose` | Odoo/OpenERP nosetests wrapper |
| `pw` | Cryptographically secure password generator with strength analysis |
| `pyinfo` | Python environment info and CPU benchmark |
| `tomlr` | TOML config file manager (`~/.config/rogkit/config.toml`) |
| `xmlr` | Odoo/OpenERP XML-RPC connection manager |

---

## Go tools

Six compiled Go binaries live in `go/bin/` and are built with `./scripts/build_go.sh`.

| Binary | What it does |
|--------|-------------|
| `finder` | Canonical filesystem search — honours `.gitignore`, supports hidden files, include/exclude extensions, smart casing |
| `fastfind` | Alternate-defaults variant of finder for scripting hooks |
| `dirfind` | Experimental fuzzy directory locator powered by `fd` and Go |
| `replacer` | Fast in-place text replacement across a file tree, with confirmation |
| `search` | Multi-term content search with batching |
| `ishtime` | Time zone conversion and "is it time?" helper |

Build all: `./scripts/build_go.sh`

Usage examples:

```sh
finder "todo" --root ~/code          # recursive content search
replacer --find TODO --replace DONE --write --confirm --path ./project
search --path ./project "TODO" "FIXME" --limit 10
ishtime --time 1530                  # convert hhmm to readable delta
```

---

## Rust

A Rust workspace lives in `rust/`. Currently contains `filehash` — a fast file hashing utility.

Build: `cargo build --release` from `rust/`.

---

## Media subsystem

`rogkit_package/media/` is a self-contained subsystem for managing a personal media library:

- **Daemon** (`daemon.py`) — background process that handles media requests asynchronously, keeping response times fast
- **Cache** (`media_cache.py`) — local SQLite + pickle cache to avoid repeated API calls
- **TMDB integration** (`tmdb.py`) — movie/TV metadata from The Movie Database
- **Plex integration** — via `plexapi` for library sync and queries
- **Search** (`search.py`) — unified search across local library and remote sources
- **Streamlit UI** (`pages/`) — web interface for browsing and managing the library

Invoked as `p` (the main alias).

Typical workflow:

```sh
p --update            # pull fresh Plex snapshot, merge extras
tmdb --csv data/media.csv   # rebuild TMDB metadata from CSV
p "blade runner"      # instant cache-backed search
p "blade runner" -z   # all matches, sorted by year
p --stats             # aggregate totals
```

If the daemon gets into a bad state:

```sh
p -S    # stop daemon
p       # next run restarts it automatically
```

---

## Architecture

```
User shell → alias
           → rogkit_py() wrapper  (sets ROGKIT_CWD="$PWD")
           → uv run -m rogkit_package.bin.<tool>
           → tool.main()
```

Tools use `from ..settings import get_invoking_cwd` to recover the user's original working directory, since `uv run --directory` changes cwd to the rogkit root.

Configuration lives at `~/.config/rogkit/config.toml`:

```toml
[plex]
plex_server_url = "http://192.168.1.100"
plex_server_token = "your_token"

[tmdb]
tmdb_api_key = "your_key"

[vido]
download_folder = "~/Downloads/Videos"
```

---

## Python import examples

All tools are importable as regular Python modules:

```python
from rogkit_package.bin.bytes import byte_size
print(byte_size(1_234_567_890))         # "1.23 GB"
print(byte_size(1_234_567_890, base=1024))  # "1.15 GiB"

from rogkit_package.bin.bignum import bignum
print(bignum(1e12))                     # "1 trillion (e+12)"

from rogkit_package.bin.seconds import convert_seconds
print(convert_seconds(3665))            # "1 hour and 1 minute"

from rogkit_package.bin.plural import plural
print(plural("person"))                 # "people"
print(plural("cat", 1))                # "cat"

from rogkit_package.bin.strike import strikethru
print(strikethru("obsolete"))          # "o̶b̶s̶o̶l̶e̶t̶e̶"

from rogkit_package.bin.pw import PasswordGenerator
pg = PasswordGenerator(length=20)
print(pg.generate_and_store_password())
```

---

## Tech stack

| Layer | Choices |
|-------|---------|
| Python runtime | Python 3.14+, [uv](https://github.com/astral-sh/uv) |
| Linting/formatting | [ruff](https://github.com/astral-sh/ruff) |
| CLI parsing | `argparse` (stdlib only — no click or typer) |
| Rich output | [rich](https://github.com/Textualize/rich) with plain-text fallback |
| Testing | pytest |
| Go | 1.21+ |
| Rust | stable toolchain |

---

## Development

```sh
make dev              # uv sync --all-extras
make test             # uv run pytest -q
make lint             # uv run ruff check .
./scripts/build_go.sh # compile all Go binaries
```

Commit style: `tool_name: what changed` (e.g. `clean: add -t/--total option`). One logical change per commit, directly to `main`.

---

## Streamlit web interface

A lightweight web UI is available for browsing the media library and a few interactive tools:

```sh
uv run streamlit run Home.py
```

Available pages: Media library browser, password generator, random-case converter.
