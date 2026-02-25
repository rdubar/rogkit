# Project: rogkit

> **Full project guide for all AI agents: [`AGENTS.md`](AGENTS.md)**
> Read that file for repository layout, tool template, key imports, and build commands.

Personal utility toolkit -- 85+ CLI tools in Python, Go utilities, Rust experiments.

## Quick Reference (Claude Code specifics)

- Scaffold new tools with `/rogkit-tool <name> <description>`
- Canonical reference tool: `rogkit_package/bin/clean.py`
- Run tests: `uv run pytest -q` or `make test`
- Lint: `uv run ruff check .` or `make lint`

## Hard Rules

All conventions are documented in [`AGENTS.md`](AGENTS.md). The critical ones:

- **argparse only** -- never click, typer, or sys.argv
- **Rich is optional** -- always try/except with plain-text fallback
- **CWD** -- use `from ..settings import get_invoking_cwd`, never `os.getcwd()`
- **Config** -- TOML at `~/.config/rogkit/config.toml` via `get_config_value()`
- **uv only** -- never pip, poetry, or conda
- **Pathlib** over os.path, **f-strings** over .format()
- **Module docstrings** and **type hints** required
- **No colorama** -- use rich with fallback
- **All tools in `rogkit_package/bin/`** -- no top-level scripts
- **Alias entry required** in `aliases` file for every new tool

## Git Conventions

- Single branch: `main` (no feature branches)
- Commit directly to main
- Message style: `"tool_name: description"` (e.g., `"clean: add -t/--total option"`)
- One logical change per commit
