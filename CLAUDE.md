# Project: rogkit

Personal utility toolkit -- 85+ CLI tools in Python, Go utilities, Rust experiments.

## Architecture

- Python tools live in `rogkit_package/bin/<tool>.py` -- each is a standalone CLI with `main()` entry point
- Media subsystem lives in `rogkit_package/media/` -- daemon-backed, SQLite-cached
- Go commands live in `go/cmd/<name>/main.go` with shared logic in `go/internal/`
- Rust workspace in `rust/` -- currently only `filehash`
- Shell aliases in `aliases` file -- all Python tools run via `rogkit_py()` which uses `uv run --directory`

## CLI Tool Conventions (CRITICAL -- follow these exactly)

- Every Python CLI uses `argparse` (NOT click, NOT typer, NOT sys.argv parsing)
- Rich is OPTIONAL -- always wrap in try/except with plain-text fallback:
  ```python
  try:
      from rich.console import Console
      from rich.table import Table
      from rich.text import Text
      console = Console()
      RICH_AVAILABLE = True
  except ModuleNotFoundError:
      console = None
      RICH_AVAILABLE = False
  ```
- Use `from ..settings import get_invoking_cwd` for CWD -- do NOT use `os.getcwd()` directly
  (because `uv run --directory` changes cwd to rogkit root; ROGKIT_CWD preserves the original)
- Config via TOML: `~/.config/rogkit/config.toml`, accessed through `from .tomlr import get_config_value`
- Module-level docstrings are REQUIRED on all files
- Type hints are expected

## Package Management

- `uv` is the package manager (NOT pip, NOT poetry, NOT conda)
- `uv sync --all-extras` to install everything
- `uv run pytest -q` to run tests
- `uv run ruff check .` to lint
- Makefile targets: `sync`, `dev`, `export`, `upgrade`, `test`, `lint`
- Dependencies go in `pyproject.toml` under `[project.dependencies]` or appropriate optional group

## Aliases

- The `aliases` file defines shell aliases for all tools
- All Python aliases use `rogkit_py()` wrapper which sets `ROGKIT_CWD="$PWD"` before running
- Pattern: `alias name='rogkit_py -m rogkit_package.bin.module_name'`
- New tools need a corresponding alias entry

## Git Conventions

- Single branch: `main` (no feature branches in this repo)
- Commit directly to main
- Commit message style: `"tool_name: description"` (e.g., `"clean: add -t/--total option"`)
- Keep commits focused -- one logical change per commit

## Testing

- Tests in `tests/` directory
- pytest is the test runner
- Import from `rogkit_package.bin` modules directly
- When adding tests, follow existing pattern: `tests/test_<tool>.py`

## What NOT to Do

- Do NOT use click or typer for CLI argument parsing
- Do NOT assume pip is available -- always use uv
- Do NOT use `os.getcwd()` in tool code -- use `get_invoking_cwd()`
- Do NOT add colorama to new tools -- use rich (with fallback) instead
- Do NOT create new top-level scripts -- all tools go in `rogkit_package/bin/`
