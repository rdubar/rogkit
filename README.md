# rogkit

Personal command-line toolkit: 85+ Python tools, a handful of Go binaries, and a small Rust workspace. Built for daily use on macOS; most tools also work on Linux.

Built and maintained by [Roger Dubar](https://github.com/rdubar).

## Highlights

A few tools you may find immediately useful:

| Tool | What it does |
|------|-------------|
| `pw` | Cryptographically secure password generator |
| `serve` | Serve any folder over HTTP instantly |
| `json` | Pretty-print and query JSON from file or stdin |
| `dedupe` | Find duplicate files by content across a directory tree |
| `purge` | Remove `.DS_Store`, `__pycache__`, and other junk recursively |
| `scrape` | Extract readable text from any URL |
| `note` | Append a timestamped note to a Markdown file; `-l` to search |
| `myip` | Show all local interfaces and your external IP |

---

## Prerequisites

- **Python** — 3.14+
- **[uv](https://github.com/astral-sh/uv)** — used for dependency management and running tools
- **Go** 1.21+ — only needed to build the Go binaries (`go/`)
- **Rust** stable toolchain — only needed to build the Rust tools (`rust/`)
- **Optional external tools** — some media tools require `ffmpeg`, HandBrake, Plex access, or API credentials

---

## Installation

### Try the packaged command

```sh
uvx --from git+https://github.com/rdubar/rogkit rogkit --help
```

This is useful for a quick smoke test without cloning the repository.

To keep the top-level command installed:

```sh
uv tool install git+https://github.com/rdubar/rogkit
rogkit
rogkit --help
rogkit --credits
```

The packaged `rogkit` command provides the project overview, credits, help, doctor, and update entry points. Use a full checkout for the short utility commands (`json`, `pw`, `p`, `doctor`, and so on), which are provided by the repository `aliases` file.

### Full checkout

```sh
git clone https://github.com/rdubar/rogkit
cd rogkit
uv sync --all-extras
source "$(pwd)/aliases"
rogkit-dev
doctor
```

`uv sync --all-extras` creates the project environment and installs all optional dependency groups. You do not need to activate the `.venv`; the aliases run tools through `uv run --directory`.

The `aliases` file auto-detects the checkout path, so it can be sourced from any clone location. To load it automatically in future shells, run:

```sh
setup --apply
```

`setup` creates `~/.config/rogkit/config.toml` if needed and adds the aliases source line to your shell profile. It previews changes by default; `--apply` writes them.

Use `doctor` for a health check covering config, secrets, aliases, common binaries, and media connectivity. It includes remediation hints for common warnings and failures.

`rogkit-dev` is the repo-local top-level command. It mirrors the packaged `rogkit` entry point while running from your checkout.

Command naming convention:
Short user-facing commands live in `aliases` (`json`, `csv`, `env`) while the
underlying Python modules may use disambiguated names such as `jsonr.py` and
`csvr.py` to avoid collisions with standard-library modules or common utilities.

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
| `backup` | Archive files/folders with compression; per-set secrets exclusion for cloud vs local destinations |
| `archive` | Inspect archive contents or extract them safely |
| `clean` | Translation file cleaner — removes unused keys from `.po`/`.pot` files |
| `collate` | Merge files from multiple locations into one directory |
| `dedupe` | Find duplicate files by size and hash under a directory tree, with exclude globs and optional `.gitignore` filtering |
| `delete` | Delete or trash files/folders; accepts piped filenames with confirmation |
| `dirs` | Recursive directory size calculator with sorted output |
| `empties` | Find empty folders and sparse directory trees |
| `fuzzy` | Fuzzy file/text search helper with interactive selection |
| `hidden` | Find hidden files and folders |
| `large` | Find large files over SSH |
| `paths` | Full-path search with optional media metadata display |
| `purge` | Remove junk files (`.DS_Store`, `__pycache__`, etc.) by pattern |
| `renamer` | Bulk file rename with pattern matching and preview |
| `serve` | Serve a local directory over HTTP for quick previews |
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
| `rogkit` | Top-level toolkit entry point: help, version, credits, update, doctor, and setup |
| `doctor` | Diagnose rogkit setup: config, secrets, aliases, binaries, and media connectivity |
| `docker_bash` | Interactive bash into a running Docker container |
| `location` | Current location and weather data |
| `myip` | Show local IPv4 interfaces and your current external IP |
| `procs` | Find running processes by name/command, with optional termination |
| `ports` | Show listening TCP/UDP ports with the owning process |
| `httpcheck` | Check HTTP status, timing, redirects, and content type for URLs |
| `setup` | Create rogkit config.toml if missing and wire aliases into your shell profile |
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
| `hash` | Hash files or stdin with common digest algorithms |
| `clipboard` | Copy text to the system clipboard |
| `csv` | Render CSV files as terminal tables with column selection and sorting |
| `env` | Pretty-print environment variables with key/value filtering |
| `fakes` | Generate fake names, emails, addresses using Faker |
| `fig` | ASCII art text via pyfiglet |
| `generations` | Genealogy calculator — ancestors and DNA percentages per generation |
| `json` | Pretty-print JSON or query simple paths from file/stdin |
| `jwt` | Decode JWT header and payload without verification |
| `note` | Append or list timestamped notes in a Markdown file |
| `plural` | Pluralise English words correctly, including irregulars |
| `randomcase` | Convert text to random case |
| `rounder` | Round decimals while stripping unnecessary trailing zeros |
| `scrape` | Extract readable text from a URL, with pagination support |
| `seconds` | Convert seconds to human-readable durations |
| `stars` | Star/pattern generator |
| `strike` | Apply Unicode strikethrough to text |
| `ts` | Convert timestamps between epoch seconds, local time, and UTC |
| `url` | Encode, decode, parse, and normalize URLs/query strings |
| `wikipedia` | Search and fetch Wikipedia articles |

### Developer & integration tools

| Tool | What it does |
|------|-------------|
| `amaz` | AWS S3 file operations |
| `bmi_calc` | BMI calculator and progression tracker |
| `catyears` | Cat age to equivalent human years |
| `dice` | Dice roller (configurable count and sides) |
| `drying` | Clothes-drying weather advisor |
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
tmdb --csv your_media.csv   # rebuild TMDB metadata from a CSV export
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
           → uv run --directory "$ROGKIT" python -m rogkit_package.bin.<tool>
           → tool.main()
```

Tools use `from ..settings import get_invoking_cwd` to recover the user's original working directory, since `uv run --directory` changes cwd to the rogkit root.

Configuration lives under `~/.config/rogkit/`:

**`config.toml`** — non-sensitive settings:

```toml
[plex]
plex_server_url = "http://192.168.1.100"

[vido]
download_folder = "~/Downloads/Videos"

[backup]
secret_patterns = ["secrets.toml", ".env"]

[[backup.set]]
name = "CloudBackup"
destinations = ["~/Dropbox/Backups"]
paths = ["~/.config/", "~/dev"]

[[backup.set]]
name = "LocalBackup"
include_secrets = true
destinations = ["~/Archive/Backups"]
paths = ["~/.config/", "~/dev", "~/.env"]
```

**`secrets.toml`** — credentials only:

```toml
[plex]
plex_server_token = "your_token"

[tmdb]
tmdb_api_key = "your_key"

[spotify]
spotify_client_id = "..."
spotify_client_secret = "..."
```

Both files share the same TOML structure. `secrets.toml` is deep-merged on top of `config.toml` at load time, so tools see a single unified config. See [`rogkit_sample.toml`](rogkit_sample.toml) for a full annotated example.

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
make dev
make test
make lint
./scripts/build_go.sh
```

These map to `uv sync --all-extras`, `uv run pytest -q`, `uv run ruff check .`, and the Go build script respectively.

Commit style: `tool_name: what changed` (e.g. `clean: add -t/--total option`). One logical change per commit, directly to `main`.

---

## Streamlit web interface

A lightweight web UI is available for browsing the media library and a few interactive tools:

```sh
uv run streamlit run Home.py
```

Available pages: Media library browser, password generator, random-case converter.

---

## Platform support

Primarily developed and tested on **macOS**. Most tools work on Linux. A small number of tools (`cleaner`, `system`, `myip`) have macOS-specific behaviour but degrade gracefully on other platforms.

The top-level `rogkit` command works on both macOS and Linux. `rogkit update`
currently supports macOS plus `apt`-based Linux distributions (Debian, Ubuntu,
Raspberry Pi OS).

---

## Licence

MIT — see [LICENSE](LICENSE).

## Credits

Built and maintained by [Roger Dubar](https://github.com/rdubar), with development assistance from Claude (Anthropic) and Codex (OpenAI).

With thanks to [Alphapet Ventures](https://alpha.pet).
