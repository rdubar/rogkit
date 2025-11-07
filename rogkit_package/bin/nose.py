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
    if not root:
        raise RuntimeError("Missing `openerp.nose.root` in rogkit config.")

    command = section.get(
        "command",
        "bin/nosetests_odoo -- -v --with-timer --logging-clear-handlers",
    )
    addons = section.get("addons", ["addons", "ext_addons"])

    return Path(root).expanduser(), command, addons

def main():
    """CLI entry point for Odoo nosetests wrapper."""
    parser = argparse.ArgumentParser(description='Run nosetests for the specified folder in the openerp-addons directory.')
    parser.add_argument('folder', help='The folder or addon name to run tests on.')
    args = parser.parse_args()

    root, command, addons = load_settings()

    folder_path = get_full_folder_path(root, addons, args.folder)
    if folder_path:
        run_tests(root, command, folder_path)
    else:
        print(f'Error: The specified folder or addon "{args.folder}" does not exist.')
        parser.print_help()
        exit(1)

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
    print(full_command)
    subprocess.run(full_command, shell=True)

if __name__ == '__main__':
    main()
