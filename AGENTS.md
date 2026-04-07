# AGENTS.md -- AI Agent Guide for rogkit

> This file is the single source of truth for any AI agent (Claude, Copilot,
> Cursor, Codex, etc.) working on this codebase. Read this first.

## Project Overview

**rogkit** is a personal utility toolkit: 85+ CLI tools in Python, plus Go
binaries and a Rust workspace. Every Python tool is a standalone module with a
`main()` entry point invoked via shell alias.

## Repository Layout

```
rogkit/
├── rogkit_package/
│   ├── bin/              # Python CLI tools (one file per tool)
│   │   ├── __init__.py
│   │   ├── clean.py      # ← canonical reference tool
│   │   ├── dice.py
│   │   └── ...           # ~70 tool modules
│   ├── media/            # Media subsystem (daemon, cache, search, tmdb)
│   ├── data/             # Package-scoped data files
│   ├── settings.py       # get_invoking_cwd(), path helpers
│   └── __init__.py
├── go/
│   ├── cmd/              # Go CLI commands (dirfind, fastfind, finder, ishtime, replacer, search)
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

Every Python tool has a corresponding line in the `aliases` file:
```bash
alias tool_name='rogkit_py -m rogkit_package.bin.tool_name'
```

## Creating a New Python Tool

Use `rogkit_package/bin/clean.py` as the canonical reference. Every new tool
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

## Rust

Workspace in `rust/` with `Cargo.toml` at the root. Currently only `filehash`.
Build with standard `cargo build --release`.

## Troubleshooting

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
