# AGENTS.md -- AI Agent Guide for rogkit

> This file is the single source of truth for any AI agent (Claude, Copilot,
> Cursor, Codex, etc.) working on this codebase. Read this first.

## Project Overview

**rogkit** is a personal utility toolkit: 88+ CLI tools in Python, plus Go
binaries and a Rust workspace. Most Python tools are standalone modules with a
`main()` entry point invoked via shell alias; the top-level `rogkit` command is
the umbrella entry point for help, version/credits, update, doctor, and setup.

## Repository Layout

```
rogkit/
├── rogkit_package/
│   ├── bin/              # Python CLI tools (one file per tool)
│   │   ├── __init__.py
│   │   ├── hash.py       # ← canonical reference tool
│   │   ├── dice.py
│   │   └── ...           # ~70 tool modules
│   ├── media/            # Media subsystem (daemon, cache, search, tmdb)
│   ├── data/             # Package-scoped data files
│   ├── settings.py       # get_invoking_cwd(), path helpers
│   └── __init__.py
├── go/
│   ├── cmd/              # Go CLI commands (dirfind, drift, fastfind, finder, ishtime, mem, replacer, search, space, squeeze, sysreboot, why)
│   ├── internal/         # Shared Go packages (finder, search, util)
│   └── bin/              # Compiled Go binaries
├── rust/
│   └── filehash/         # Rust workspace (currently filehash only)
├── tests/                # pytest tests: tests/test_<tool>.py
├── aliases               # Shell aliases -- all tools are invoked through here
├── scripts/              # Build/maintenance scripts (e.g., build_go.sh)
├── data/                 # Top-level data files (CSV, etc.)
├── pages/                # Streamlit web pages
├── Home.py               # Streamlit entry point
├── pyproject.toml        # Python deps & build config (uv-managed)
├── Makefile              # sync, dev, export, upgrade, test, lint
├── CLAUDE.md             # Claude Code-specific instructions
└── AGENTS.md             # ← you are here
```

## How Python Tools Work

### Execution flow

```
User shell → alias (in `aliases` file)
           → rogkit_py() wrapper (sets ROGKIT_CWD="$PWD", runs uv)
           → uv run --directory $ROGKIT python -m rogkit_package.bin.<tool>
           → <tool>.main()
```

The wrapper is needed because `uv run --directory` changes cwd to the rogkit
root. The original user directory is preserved in `ROGKIT_CWD`.

### Alias pattern

Most Python tools have a corresponding line in the `aliases` file:
```bash
alias tool_name='rogkit_py -m rogkit_package.bin.tool_name'
```

The repo-local developer entry point is:
```bash
alias rogkit-dev='rogkit_py -m rogkit_package.bin.rogkit'
```

## Creating a New Python Tool

Use `rogkit_package/bin/hash.py` as the canonical reference. Every new tool
**must** follow this structure:

```python
#!/usr/bin/env python3
"""Short description of what this tool does."""

import argparse
from pathlib import Path

from ..settings import get_invoking_cwd

try:  # optional rich formatting
    from rich.console import Console
    from rich.text import Text

    console = Console()
    RICH_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover
    console = None
    RICH_AVAILABLE = False


def _print_message(message: str, *, style: str | None = None) -> None:
    """Print with optional rich styling, fallback to plain print."""
    if RICH_AVAILABLE:
        console.print(Text(message, style=style) if style else message)
    else:
        print(message)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Short description")
    # add arguments here
    return parser.parse_args()


def main() -> None:
    """CLI entry point."""
    args = parse_args()
    cwd = get_invoking_cwd()
    # implementation here


if __name__ == "__main__":
    main()
```

### Checklist for a new tool

1. Create `rogkit_package/bin/<tool_name>.py` following the template above
2. Add alias to `aliases` in the appropriate section:
   `alias tool_name='rogkit_py -m rogkit_package.bin.tool_name'`
3. Create `tests/test_<tool_name>.py` with at least a smoke test
4. Add any new dependencies to `pyproject.toml` (correct optional group)

## Hard Rules (DO NOT VIOLATE)

| Rule | Detail |
|------|--------|
| **argparse only** | Never use click, typer, or raw sys.argv |
| **Rich is optional** | Always wrap in try/except with plain-text fallback |
| **CWD via settings** | Use `from ..settings import get_invoking_cwd` -- never `os.getcwd()` |
| **Config via TOML** | `~/.config/rogkit/config.toml`, read with `from .tomlr import get_config_value` |
| **Module docstrings** | Required on every file |
| **Type hints** | Expected on all functions |
| **uv only** | Never pip, poetry, or conda. `uv sync --all-extras` to install |
| **Pathlib** | Prefer `pathlib.Path` over `os.path` |
| **f-strings** | Prefer over `.format()` or `%` |
| **No colorama** | Use rich (with fallback) for color/formatting |
| **Tools in bin/** | All Python tools go in `rogkit_package/bin/` -- no top-level scripts |

## Package Manager & Build Commands

| Command | Purpose |
|---------|---------|
| `uv sync --all-extras` | Install all deps |
| `uv run pytest -q` | Run tests |
| `uv run ruff check .` | Lint |
| `make test` | Run tests (via Makefile) |
| `make lint` | Lint (via Makefile) |
| `make dev` | Sync with all extras |
| `./scripts/build_go.sh` | Build all Go binaries |

## Key Imports & Helpers

```python
# Get the user's original working directory (not rogkit root)
from ..settings import get_invoking_cwd
cwd = get_invoking_cwd()

# Read rogkit config values
from .tomlr import get_config_value
value = get_config_value("section", "key")

# Path helpers from settings.py
from ..settings import root_dir, data_dir, package_data_dir, ensure_package_data_dir
```

## Git Conventions

- Single branch: `main` (no feature branches)
- Commit directly to main
- Commit message style: `"tool_name: description"` (e.g., `"clean: add -t/--total option"`)
- One logical change per commit

## Go Tools

Go commands live in `go/cmd/<name>/main.go` with shared logic in
`go/internal/`. Build all with `./scripts/build_go.sh` which runs
`go install ./cmd/...` with `GOBIN=go/bin`.

## Using rogkit as an agent

If you're an AI agent *using* the tools this repo builds (not just editing
rogkit's source), read README.md's **"rogkit for AI agents"** section — it
covers which tools give instant startup, structured `--json` output, and
plain `-q`/`--plain` output, plus which tools (`primer`, `drift`, `squeeze`,
`why`, `recall`, `toolfind`) exist specifically to serve agents as users of
a rogkit-equipped machine.

## Rust

Workspace in `rust/` with `Cargo.toml` at the root. Currently only `filehash`.
Build with standard `cargo build --release`.

## Backup

`rogkit_package/bin/backup.py` is the backup tool. Two flavours of set in
`~/.config/rogkit/config.toml`:

- `[[backup.set]]` — plain tar.gz. Files matching `secret_patterns` (basename
  match only — see `_matches_basename`) are stripped. Use for cloud-synced
  destinations.
- `[[backup.encrypted_set]]` — `tar -czf - | age` piped together so plaintext
  never lands on disk. `secret_patterns` is bypassed; secrets are the point.
  Requires `recipients` and/or `recipients_file`; ages preflight before the
  real tar runs.

Both flavours support `keep = N` (per-set, or as a `[backup]`-level default):
after a successful run, all but the N most recent archives — and their
`.manifest.json` sidecars — are deleted from each destination independently.
Pruning never runs on `--plan`/`--dry-run`. `backup -b --keep N` overrides
every selected set's configured value for that invocation only.

Per-machine strategy doc (not committed; lives next to the config):
`~/.config/rogkit/backup-strategy.md`.

### One-line invocations

| Command | Effect |
|---|---|
| `backup -b` | Run all configured sets |
| `backup -b --set <name>` | Run a single set |
| `backup -b --encrypted` | Only encrypted sets |
| `backup -b --keep N` | Run all sets, then prune each destination to the N most recent archives |
| `backup --plan` | Dry-run preview (no writes) |
| `backup --list-sets` | List configured sets |

The `backup` shell alias is defined in `aliases` and resolves to
`rogkit_py -m rogkit_package.bin.backup`. Works in interactive shells; works
from `Bash` tool invocations after the shell snapshot loads.

### Scheduled weekly run (m3)

A LaunchAgent (`~/Library/LaunchAgents/com.rdubar.backup-weekly.plist`) fires
Monday 08:00 and invokes `scripts/run-backup-weekly.sh`, which runs `backup -b`
and posts a Notification Center alert on completion (Glass on success, Sosumi
on failure). Logs to `~/Library/Logs/rogkit-backup-weekly.log` (script output)
and `…launchd.log` (launchd-side stdout/stderr).

```sh
# Inspect / manage
launchctl list | grep com.rdubar.backup-weekly
launchctl unload ~/Library/LaunchAgents/com.rdubar.backup-weekly.plist
launchctl load   ~/Library/LaunchAgents/com.rdubar.backup-weekly.plist
launchctl start  com.rdubar.backup-weekly   # fire now, ignoring schedule

# Run the wrapper directly (same path launchd takes)
~/dev/rogkit/scripts/run-backup-weekly.sh
```

The wrapper (`scripts/run-backup-weekly.sh`) is committed and machine-agnostic;
the plist is per-machine and not committed. neo / pi follow the same pattern
when set up — each generates its own age identity and its own
`backup-recipients.txt` (machine-local; m3 / neo / pi do **not** share keys).

## Troubleshooting

### Pi 5 network choice

For the Pi 5 powerline Ethernet vs Wi-Fi comparison, see `docs/reports/pi5-network-comparison-2026-05-02.md`; current recommendation is to keep `eth0` as the default route.

### Media daemon

If you encounter issues with the media tool (`p` / `rogkit_package.media.media`), restart the daemon first:

```sh
p -S        # stop the running daemon
p           # next invocation starts a fresh daemon automatically
```

Or explicitly:

```sh
p --stop-daemon
p --daemon &   # start daemon in background (or just run any `p` command)
```

## Dependency Groups (pyproject.toml)

| Group | Packages |
|-------|----------|
| media | yt-dlp, ffmpeg-python, Pillow, plexapi, paramiko, python-dotenv |
| ui | streamlit |
| aws | boto3, botocore |
| db | sqlalchemy, pymongo |
| data | pandas, numpy, matplotlib, python-dateutil, pytz, reportlab, folium, geopy |
| cli | pyclip, pyfiglet, send2trash, thefuzz, sh, spotipy, psutil, openai, requests-html, faker, convertdate, wikipedia |
| dev | ruff, black, mypy, pytest |
