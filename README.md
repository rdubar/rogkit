# rogkit

Personal command-line toolkit: 85+ Python tools, a dozen Go binaries, and a small Rust workspace. Built for daily use on macOS; most tools also work on Linux.

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
| `backup` | Archive files/folders with compression, dry-run plans, manifests, and optional `age`-encrypted sets |
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
| `primer` | Cold-start machine briefing: uptime, disk, dirty repos, ports, notes, recent `drift` changes |
| `toolfind` | Fuzzy-search rogkit's own tool catalogue by name or description |
| `recall` | Unified activity timeline: git reflogs, Claude session starts, and notes, merged and filterable |
| `httpcheck` | Check HTTP status, timing, redirects, and content type for URLs |
| `setup` | Create rogkit config.toml if missing and wire aliases into your shell profile |
| `speed_test` | Network speed test |
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
| `pgscratch` | Disposable Postgres container (Apple `container`/Docker) for throwaway DB work |
| `pw` | Cryptographically secure password generator with strength analysis |
| `pyinfo` | Python environment info and CPU benchmark |
| `tomlr` | TOML config file manager (`~/.config/rogkit/config.toml`) |
| `xmlr` | Odoo/OpenERP XML-RPC connection manager |

---

## Go tools

Twelve compiled Go binaries live in `go/bin/` and are built with `./scripts/build_go.sh`.

| Binary | What it does |
|--------|-------------|
| `finder` | Canonical filesystem search — honours `.gitignore`, supports hidden files, include/exclude extensions, smart casing |
| `fastfind` | Alternate-defaults variant of finder for scripting hooks |
| `dirfind` | Experimental fuzzy directory locator powered by `fd` and Go |
| `replacer` | Fast in-place text replacement across a file tree, with confirmation |
| `search` | Multi-term content search with batching |
| `ishtime` | Time zone conversion and "is it time?" helper |
| `sysreboot` | Ultra-fast one-or-two-line reboot advisor (aliased as `sys`/`syscheck`) |
| `space` | Disk usage summary with a colored table, sortable by size |
| `mem` | Memory usage summary, grouped by app; `mem <name>` filters to matching processes plus a total |
| `drift` | Snapshots disk/mem/ports/launch-agents/packages/dirty-repos and reports what changed since the last run or a named baseline |
| `squeeze` | Distills a log stream into unique templates, with `--fit` to budget output to roughly N tokens |
| `why` | One-shot slowness triage: swap pressure, CPU-bound, or memory-bound, with a named culprit |

Build all: `./scripts/build_go.sh`

Usage examples:

```sh
finder "todo" --root ~/code          # recursive content search
replacer --find TODO --replace DONE --write --confirm --path ./project
search --path ./project "TODO" "FIXME" --limit 10
ishtime --time 1530                  # convert hhmm to readable delta
sys                                  # "✅ No reboot needed (score 12%)" + stats line
sys -1                               # squash to one line
space                                # colored table: mount, total, used, free, usage
space -s -t                          # sorted by size, plus a combined totals row
space -q                             # plain pipe-delimited output, no color
mem                                  # top 10 apps by memory, colored table
mem chrome                           # every matching process, plus a TOTAL row
mem -n 5                             # top 5 apps instead of the default 10
drift                                # what changed since the last snapshot/run
drift --since 7d                     # diff against the nearest snapshot ~a week old
drift --set-baseline morning         # name the current snapshot as a baseline
squeeze app.log                      # cluster a log file into unique templates
squeeze app.log --fit 4000           # budget output to ~4000 tokens, bulk noise elided first
why                                  # "🔥 CPU-bound: load 8.1 on 4 cores — mediaanalysisd at 340% CPU"
```

`sysreboot` replaced the old Python `syscheck` tool: no `psutil`/Rich dependency, ~150ms→sub-10ms runtime, and on Linux it checks the canonical reboot marker directly (`/run/reboot-required`, with `/var/run` as a compatibility alias) instead of re-deriving reboot need from `apt-cache policy` heuristics. macOS stays native too: uptime, load, and swap come from sysctls, with only `vm_stat` left for the memory-pressure page counters. Exit code doubles as a script-friendly signal: `0` = fine, `1` = moderate, `2` = reboot required/advised.

`space` replaced the old Python `space` tool for the same reason: no `rich` import cost, disk stats come straight from `statfs(2)` (`Frsize` on Linux, `Bsize` on macOS — mirroring `os.statvfs()`'s `f_frsize` semantics on each). The colored table and `-q` plain fallback are hand-rolled ANSI/box-drawing, with the same UTF-8-locale ASCII fallback `sysreboot` uses. Mount dedup uses `stat(2)`'s device id rather than `statfs`'s `Fsid`, since macOS APFS firmlinks (e.g. `/` and `/System/Volumes/Data`) share one device but report different `Fsid` values.

`mem` fills a gap the Python `procs --sort mem` tool didn't: a grouped, per-app view instead of a flat PID list. It shells out to `ps -axo pid=,rss=,comm=` once and parses every line, rather than a psutil-style per-process syscall loop. Chromium/Electron helper processes (`Google Chrome Helper (Renderer)`, `Slack Helper (Plugin)`, etc.) are rolled up under their parent app's name via a suffix-stripping heuristic, so the default summary reads like Activity Monitor's grouped view rather than a dozen near-duplicate rows. `%Mem` comes from physical RAM total (`hw.memsize` sysctl on macOS, `/proc/meminfo`'s `MemTotal` on Linux). Passing a name/substring switches to an ungrouped, per-PID view of just the matches plus a `TOTAL` row — matching processes are found by substring on the raw `ps` name, not the canonicalized one, so `mem chrome` still catches every helper.

`drift` is the missing time axis: every other system tool above (`space`, `mem`, `sysreboot`) is a point-in-time snapshot with no memory of yesterday. It gathers disk and memory data by shelling out to `space --json`/`mem --json -n 30` — composition over a shared internal package, since a risky refactor of two already-working tools wasn't worth it just to save a couple hundred lines — and implements its own collectors for listening ports (`lsof` on macOS, `ss` on Linux), launch agents (`~/Library/LaunchAgents` filenames on macOS, enabled `systemctl --user` units on Linux), package inventory (`brew`/`dpkg-query`, whichever is present), and dirty/ahead git repos under `~/dev`. Snapshots are gzipped JSON in `~/.local/state/rogkit/drift/` (one per run, pruned after 90 days unless named as a baseline via `--set-baseline`), diffed against conservative thresholds (2GB disk, 512MB per-app memory, any new listening port or launch agent) so it stays quiet on ordinary day-to-day variance. Exit codes mirror `sysreboot`: `0` = no changes, `1` = changes, `2` = a notable one (new port, new agent, crossed 90% disk).

`squeeze` masks variable fields (timestamps, UUIDs/hex IDs, IPs, paths, bare numbers) out of each line and clusters structurally identical lines into one template with a count — built for when the thing reading the output is a context window, not a scrollback buffer. `--fit N` budgets the rendered output to roughly N tokens (a documented ~4-chars-per-token estimate, not a real tokenizer): error-shaped templates and rare ones survive first, high-count bulk noise is elided, and an "N more templates elided" line accounts for what got cut.

`why` answers "why is this machine slow right now?" by composing `sysreboot --json` and `mem --json` rather than re-reading the same syscalls a third time, adding only its own top-CPU-process check (`ps -axo pid=,pcpu=,comm=`). Checks run in escalating order — swap pressure (substantial swap use *and* low available RAM), then CPU-bound (load vs. core count), then a single process dominating memory — first match wins, and a miss prints "Nothing obviously wrong" rather than guessing. Thermal and disk-I/O-wait checks are deliberately not implemented: a one-shot tool has no honest way to claim a *sustained* reading, only a snapshot, so v1 stops at checks it can back up.

Support matrix:

| Platform | Status | Notes |
|----------|--------|-------|
| Linux | Supported | `/run/reboot-required` is the authoritative reboot signal; `/var/run` is accepted as a compatibility path. |
| macOS | Supported | Uses native `sysctl` plus a tiny `vm_stat` parse for page counters. |
| Windows | Not supported yet | Explicitly out of scope for now. |

---

## rogkit for AI agents

AI agents (Claude, Codex, and similar) are a first-class user of any machine rogkit is installed on, not just a human at a terminal — `primer`, `drift`, `squeeze`, `why`, `recall`, and `toolfind` exist specifically to serve that use case. A few things worth knowing if you're an agent operating on a rogkit-equipped machine (or scripting around one):

- **The Go system tools start instantly.** `space`, `mem`, `drift`, `squeeze`, `why`, and `sysreboot` have no `uv`/Rich import cost, and all auto-detect a non-TTY stdout and switch to plain, uncolored output on their own — piping one from a shell tool never leaks ANSI codes into an agent's context, even without `-q`.
- **`--json` gives structured output** on `sysreboot`, `space`, `mem`, `drift`, `why` (Go) and `doctor`, `scrape`, `primer`, `toolfind`, `recall` (Python) — prefer it over parsing table output.
- **`-q`/`--quiet`/`--plain`** forces plain output even on a real TTY: `space`, `mem`, `drift`, and `squeeze` (Go), and every Rich-table Python tool (`ports`, `procs`, `dirs`, `system`, `note`, `pyinfo`, `purge`, `backup`, and the rest — all 38 of them). Python tools without an explicit flag still auto-detect a non-TTY stdout via Rich, but Rich's own fallback only drops color, not table borders/box-drawing — so `--plain` is still the safer bet for an agent even when piping.
- **Start with `primer`.** It's a cold-start briefing for whatever machine you're on: uptime, disk headroom, dirty repos under `~/dev`, listening ports, recent notes, and (on Linux) the configured Pi media services plus `/mnt/media1`–`/mnt/media4` mount state. Once a baseline exists, it also includes `drift`'s summary of what changed since last time — one command instead of re-deriving all of that from scratch every session.
- **`drift`** is the closest thing to memory across sessions: `drift --set-baseline morning` once, then `drift` any time to see what actually changed, with exit codes (`0`/`1`/`2`) usable in scripts.
- **`squeeze`** is for compressing large log/output dumps before they hit a context window — `squeeze --fit 4000 some.log` distills thousands of lines to their unique templates, keeping rare and error-shaped lines even under a tight budget. See the Go tools section above for the exact algorithm.
- **`recall`** and **`toolfind`** help with session handoff and tool discovery respectively — `recall yesterday` for "what happened since I was last here," `toolfind "empty folders"` instead of grepping this README for the right tool name.

---

## Rust

A Rust workspace lives in `rust/`. Contains `filehash` — a fast file hashing utility — and `asmhash`, an experimental ARM64 assembly crate `filehash` benchmarks itself against.

Build: `cargo build --release` from `rust/`.

### Experimental: hand-written ARM64 assembly (`asmhash`)

`rust/asmhash` is a small, Apple Silicon-only crate of hand-written ARM64 assembly for two hardware instruction families Clang won't emit from plain Rust or C without explicit intrinsics:

- **CRC-32C** via the `crc32cx`/`crc32cw`/`crc32ch`/`crc32cb` instructions (FEAT_CRC32)
- **SHA-256** compression via `sha256h`/`sha256h2`/`sha256su0`/`sha256su1` (FEAT_SHA256)

Both are exposed in `filehash` as extra algorithm choices for comparison:

```sh
filehash myfile -a sha256-asm
filehash myfile -a crc32c-asm
```

Correctness is verified against NIST test vectors and against the `sha2` crate at every padding-block boundary (`cargo test -p asmhash`); a criterion bench group (`cargo bench -p filehash`) compares throughput against the existing library implementations.

The interesting finding so far wasn't "assembly beats the compiler" — it's that `sha2`'s ARM hardware path is gated behind an opt-in Cargo feature (now enabled in this workspace); with it off, the crate silently falls back to a scalar implementation ~5x slower. Once enabled, hand-written asm and `sha2`'s own ACLE intrinsics land within a few percent of each other. Full write-up and the rest of the candidate-project brainstorm: [notes/arm64-asm-utility-brainstorm.md](notes/arm64-asm-utility-brainstorm.md).

This only builds on `aarch64` targets — a build on any other architecture will fail with a clear panic from `asmhash`'s `build.rs` rather than silently producing something broken.

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

[primer]
# Machine-specific Linux services and mounts shown by `primer`.
services = ["plexmediaserver", "smbd", "transmission-daemon", "wayvnc", "tailscaled"]
media_mounts = ["/mnt/media1", "/mnt/media2", "/mnt/media3", "/mnt/media4"]

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
