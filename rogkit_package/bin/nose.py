"""
Odoo/OpenERP nosetests wrapper.

Simplifies running nosetests for specific addons in OpenERP projects
by automatically finding addon paths and constructing test commands.
"""
import argparse
import sys
import subprocess
from pathlib import Path
from typing import Iterable

from ..bin.fuzzy import MatchResult, find_candidates
from ..bin.tomlr import load_rogkit_toml

try:  # optional rich formatting
    from rich.console import Console
    from rich.table import Table
    from rich.text import Text

    console = Console()
    RICH_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover
    console = None
    RICH_AVAILABLE = False


def _print(message: str, *, style: str | None = None) -> None:
    if RICH_AVAILABLE:
        console.print(Text(message, style=style) if style else message)
    else:
        print(message)


def _render_settings(root: Path, command: str, addons: Iterable[str]) -> None:
    if RICH_AVAILABLE:
        table = Table(title="Active Settings", box=None, show_header=False, pad_edge=False)
        table.add_column("Key", style="bold cyan")
        table.add_column("Value", style="white")
        table.add_row("root", str(root))
        table.add_row("command", command)
        table.add_row("addons", ", ".join(addons))
        console.print(table)
    else:
        print("Loaded settings:")
        print(f"  root: {root}")
        print(f"  command: {command}")
        print(f"  addons: {', '.join(addons)}")


CONFIG_HELP = (
    "Configure ~/.config/rogkit/config.toml:\n"
    "[openerp.nose]\n"
    'root = "/path/to/openerp"\n'
    'command = "bin/nosetests_odoo -- -v --with-timer --logging-clear-handlers"\n'
    'addons = ["addons", "ext_addons"]'
)


def load_settings():
    """
    Load nosetest settings from rogkit config.
    Expected TOML structure:

    [openerp.nose]
    root = "/path/to/openerp"
    command = "bin/nosetests_odoo -- -v --with-timer --logging-clear-handlers"
    addons = ["addons", "ext_addons"]
    """

    config = load_rogkit_toml()
    section = config.get("openerp", {}).get("nose", {})

    root = section.get("root")
    command = section.get(
        "command",
        "bin/nosetests_odoo -- -v --with-timer --logging-clear-handlers",
    )
    addons = section.get("addons", ["addons", "ext_addons"])

    return (
        Path(root).expanduser() if root else None,
        command if command else None,
        addons if addons else None,
    )


def get_full_folder_path(root: Path, addons: Iterable[str], target: str):
    """Determine the full path of the folder to run tests on."""
    target_path = Path(target)
    if target_path.is_dir():
        return target_path

    search_roots = [root / "src" / "addons", *[root / "src" / addon for addon in addons]]
    for base in search_roots:
        candidate = base / target
        if candidate.is_dir():
            return candidate

    matches = _collect_candidate_paths(search_roots, target)

    if len(matches) == 1:
        return matches[0]

    if matches:
        print(f"Multiple folders found for '{target}':")
        for match in matches:
            print(f"  {match.relative_to(root)}")
        sys.exit(1)

    print(f"No folder found for '{target}'")
    return None


def _collect_candidate_paths(search_roots: Iterable[Path], target: str):
    """Return candidate paths where the folder name contains ``target``."""
    matches = find_candidates(search_roots, target)
    return [match.path if isinstance(match, MatchResult) else match for match in matches]

def run_tests(root: Path, command: str, folder):
    """Executes the nosetest command on the specified folder."""
    full_command = f'cd "{root}" && {command} "{folder}"'
    _print(full_command, style="bold green")
    subprocess.run(full_command, shell=True)
    
def main():
    """CLI entry point for Odoo nosetests wrapper."""
    parser = argparse.ArgumentParser(description='Run nosetests for the specified folder in the openerp-addons directory.')
    parser.add_argument('folder', help='The folder or addon name to run tests on.')
    parser.add_argument('--path', help='Override openerp root path.')
    parser.add_argument('--command', help='Override nosetests command.')
    parser.add_argument('--addons', nargs='*', help='Override addon folders (space separated).')
    args = parser.parse_args()

    root, command, addons = load_settings()

    if args.path:
        root = Path(args.path).expanduser()
    if args.command:
        command = args.command
    if args.addons:
        addons = args.addons

    missing = []
    if root is None:
        missing.append("root")
    if command is None:
        missing.append("command")
    if not addons:
        missing.append("addons")

    if missing:
        _print("Missing configuration:", style="bold red")
        for item in missing:
            _print(f"  - {item}", style="red")
        _print(CONFIG_HELP, style="yellow")
        parser.print_help()
        sys.exit(1)

    assert root is not None and command is not None and addons  # for type checkers
    _render_settings(root, command, addons)

    folder_path = get_full_folder_path(root, addons, args.folder)
    if folder_path:
        run_tests(root, command, folder_path)
    else:
        _print(f'Error: The specified folder or addon "{args.folder}" does not exist.', style="bold red")
        parser.print_help()
        exit(1)

if __name__ == '__main__':
    main()
