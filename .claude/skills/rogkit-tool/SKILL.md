---
name: rogkit-tool
description: Scaffold a new rogkit CLI tool following all project conventions
argument-hint: "<tool-name> [description]"
---

# /rogkit-tool -- Scaffold a New Rogkit CLI Tool

## Steps

1. **Parse `$ARGUMENTS`** for tool name and description:
   - Input: `duster Clean up dust files`
   - Tool name: `duster`
   - Description: `Clean up dust files`
   - If no arguments, ask for name and description

2. **Check that `rogkit_package/bin/<tool_name>.py` does not already exist** -- abort if it does

3. **Read `rogkit_package/bin/hash.py`** as a reference for the canonical tool structure

4. **Create `rogkit_package/bin/<tool_name>.py`** with this structure:
   ```python
   #!/usr/bin/env python3
   """<Description>."""

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
       parser = argparse.ArgumentParser(description="<Description>")
       # TODO: add arguments
       return parser.parse_args()


   def main() -> None:
       """CLI entry point."""
       args = parse_args()
       cwd = get_invoking_cwd()
       # TODO: implement


   if __name__ == "__main__":
       main()
   ```

5. **Add alias to `aliases` file** in the appropriate section:
   ```bash
   alias <tool_name>='rogkit_py -m rogkit_package.bin.<tool_name>'
   ```

6. **Create test stub at `tests/test_<tool_name>.py`**:
   ```python
   """Tests for <tool_name>."""

   from rogkit_package.bin.<tool_name> import main


   def test_<tool_name>_runs():
       """Smoke test: tool imports and main is callable."""
       assert callable(main)
   ```

7. **Show summary** of all created/modified files

## Rules

- ALWAYS use `argparse` -- never click or typer
- ALWAYS include the rich fallback pattern
- ALWAYS use `get_invoking_cwd()` -- never `os.getcwd()`
- ALWAYS add the alias entry
- Follow existing code style from `rogkit_package/bin/hash.py`
