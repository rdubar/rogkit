"""
Script Name: Rog's Movie Downloader

Description:
This script allows users to download videos from URLs or search terms using `yt_dlp`. 
It reads configuration settings from a TOML file (`~/.config/rogkit/config.toml`), 
which specifies the temporary download folder (`temp_folder`), 
the final download folder (`download_folder`), and the default input file (`default_input_file`). 

The script downloads videos into the temporary folder and then moves them to the final download folder after the download is complete.

Features:
- Supports downloading videos from URLs provided as command-line arguments, from an input file containing URLs, or from user input.
- Reads configuration settings for folders and default input file from a TOML configuration file.
- Downloads videos to a temporary folder before moving them to the final destination folder.
- Provides a debug mode for detailed output and easier troubleshooting.
- Handles exceptions gracefully and provides user-friendly error messages.
- Limits video resolution to 1080p and truncates video titles to 80 characters for file naming.

Usage:
- Run the script with a URL, search term, or filename as an argument:
  `python vido.py "https://www.youtube.com/watch?v=example"`
- Use the `-c` or `--config` option to specify a custom configuration file:
  `python vido.py -c "/path/to/config.toml"`
- Use the `-d` or `--debug` flag to enable debug mode:
  `python vido.py -d "search_term_or_url"`
- If no arguments are provided, the script will prompt for input.
"""

import argparse
import datetime
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from importlib import metadata
from pathlib import Path

import toml  # type: ignore
from yt_dlp import YoutubeDL  # type: ignore

from ..settings import root_dir

try:  # optional rich formatting
    from rich.console import Console
    from rich.text import Text

    console = Console()
    RICH_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover
    console = None
    RICH_AVAILABLE = False


_PLAIN_OUTPUT = False


def _print_message(message: str, *, style: str | None = None) -> None:
    """Print with optional rich styling, fallback to plain print."""
    if RICH_AVAILABLE and not _PLAIN_OUTPUT:
        console.print(Text(message, style=style) if style else message)
    else:
        print(message)

class Config:
    """Video downloader configuration from TOML file."""
    
    def __init__(self, config_file):
        try:
            self.config = toml.load(config_file)
            self.temp_folder = self.config['vido']['temp_folder']
            self.download_folder = self.config['vido']['download_folder']
            self.default_input_file = self.config['vido']['default_input_file']
        except Exception as e:
            _print_message(f"Failed to load [vido] section of config file {config_file}: {e}", style="magenta")
            exit(1)

    def get_download_options(self):
        """Get yt_dlp download options with format and output template."""
        return {
            "format": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
            "outtmpl": os.path.join(self.temp_folder, "%(title).80s-%(id)s.%(ext)s"),  # Include temp_folder in output template
        }

def get_title_from_url(url):
    """Extract video title from URL using yt_dlp."""
    ydl_opts = {'quiet': True, 'no_warnings': True, 'skip_download': True}
    try:
        with YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=False)
            return info_dict.get('title', None)
    except Exception as e:
        _print_message(f"Error fetching title with yt_dlp: {e}", style="magenta")
        _print_message("If this site used to work, try `vido --update` to get the latest yt_dlp.", style="cyan")
        return None

def set_directory(directory=None):
    """Set working directory, creating temp directory if none specified."""
    try:
        if directory is None:
            # Create a unique temporary directory (auto-cleaned on reboot)
            directory = tempfile.mkdtemp(prefix="rogkit_")
        else:
            directory = os.path.expanduser(directory)

        os.makedirs(directory, exist_ok=True)
        os.chdir(directory)
        _print_message(f"Working directory set to: {os.getcwd()}", style="cyan")
        return directory
    except Exception as e:
        _print_message(f"Failed to change directory: {e}", style="magenta")
        return None

def showtime(s: float) -> str:
    """Format time duration as seconds or timedelta."""
    return f"{s:.5f} seconds" if s < 10 else str(datetime.timedelta(seconds=s))


def process_lines(lines, config):
    """Process multiple lines/URLs for downloading."""
    temp_folder = config.temp_folder
    set_directory(temp_folder)

    _print_message("Processing the following lines:", style="cyan")
    for line in lines:
        _print_message(line.strip(), style="yellow")

    for line in lines:
        if "http" in line.lower():
            process_url(line.strip(), config)

def process_url(url, config):
    """Download video from URL and move to final destination."""
    title = get_title_from_url(url)
    if not title:
        _print_message("Skipping URL due to title fetch failure.", style="magenta")
        return

    _print_message(f"Downloading: {title}", style="cyan")
    try:
        with YoutubeDL(config.get_download_options()) as ydl:
            video_info = ydl.extract_info(url, download=True)
            output = ydl.prepare_filename(video_info)

            final_output = os.path.join(config.download_folder, os.path.basename(output))
            os.rename(output, final_output)

    except Exception as e:
        _print_message(f"Error downloading {url}\n{e}", style="magenta")
        _print_message("If this site used to work, try `vido --update` to get the latest yt_dlp.", style="cyan")
        return

    _print_message(f"Downloaded to {final_output}", style="green")

def get_movies(search, config):
    """Main function to download videos from URLs, files, or search terms."""
    clock = time.perf_counter()

    # Handle multiple parameters
    if isinstance(search, list) and len(search) > 1:
        _print_message(f"Processing {len(search)} parameters sequentially...", style="cyan")
        for i, item in enumerate(search, 1):
            _print_message(f"\n--- Processing item {i}/{len(search)}: {item} ---", style="yellow")
            get_movies(item, config)  # Recursively process each item
        _print_message(f"\nCompleted all {len(search)} tasks in {showtime(time.perf_counter() - clock)}.", style="cyan")
        return

    # Handle single parameter (original logic)
    if isinstance(search, list) and len(search) == 1 and isinstance(search[0], str):
        search = search[0]

    if isinstance(search, str) and "-f" in search:
        search = config.default_input_file

    lines = [search]
    if isinstance(search, str) and os.path.isfile(search):
        with open(search, "r", encoding="utf-8") as f:
            lines = f.readlines()
    else:
        _print_message("Processing single input.", style="cyan")

    process_lines(lines, config)
    _print_message(f"Completed task in {showtime(time.perf_counter() - clock)}.", style="cyan")
    
def get_installed_yt_dlp_version() -> str:
    """Return the installed yt-dlp distribution version."""
    current_version = "unknown"
    try:
        current_version = metadata.version("yt_dlp")
    except metadata.PackageNotFoundError:
        _print_message("yt_dlp is not currently installed in this environment.", style="magenta")
    except Exception as e:
        _print_message(f"Could not determine installed yt_dlp version: {e}", style="magenta")
    return current_version


def get_latest_yt_dlp_version() -> str | None:
    """Fetch the latest yt-dlp version published on PyPI."""
    try:
        with urllib.request.urlopen("https://pypi.org/pypi/yt-dlp/json", timeout=5) as resp:
            data = json.load(resp)
            return data["info"]["version"]
    except Exception as e:
        _print_message(f"Unable to check PyPI for the latest yt_dlp release: {e}", style="magenta")
        _print_message(
            "You can manually check with `uv lock --upgrade-package yt-dlp --dry-run` "
            "or visit https://pypi.org/project/yt-dlp/.",
            style="cyan",
        )
        return None


def _parse_version(version: str):
    """Parse a package version when packaging is available."""
    try:
        from packaging.version import Version

        return Version(version)
    except Exception:
        return None


def yt_dlp_needs_upgrade(current_version: str, latest_version: str | None) -> bool:
    """Return True when PyPI reports a newer yt-dlp than the installed one."""
    if latest_version is None:
        return False

    parsed_installed = _parse_version(current_version)
    parsed_latest = _parse_version(latest_version)

    if parsed_installed and parsed_latest:
        return parsed_latest > parsed_installed
    return current_version != "unknown" and current_version != latest_version


def report_yt_dlp_versions() -> tuple[str, str | None, bool]:
    """Print installed/latest yt-dlp versions and whether an upgrade is available."""
    current_version = get_installed_yt_dlp_version()
    latest_version = get_latest_yt_dlp_version()
    _print_message(f"Installed yt_dlp version: {current_version}", style="cyan")
    if latest_version is not None:
        _print_message(f"Latest    yt_dlp version: {latest_version}", style="cyan")

    needs_upgrade = yt_dlp_needs_upgrade(current_version, latest_version)
    if needs_upgrade:
        _print_message(f"Update available: {current_version} -> {latest_version}", style="yellow")
    elif latest_version is not None:
        _print_message("yt_dlp is up to date.", style="green")
    return current_version, latest_version, needs_upgrade


def run_uv_command(args: list[str], *, cwd: Path | None = None) -> int:
    """Run a uv command and return its exit code."""
    uv_path = shutil.which("uv")
    if uv_path is None:
        _print_message("Error: `uv` is required to update yt-dlp.", style="magenta")
        return 1

    command = [uv_path, *args]
    _print_message(f"Running: {' '.join(command)}", style="cyan")
    result = subprocess.run(command, cwd=cwd or Path(root_dir), check=False)
    return result.returncode


def update_yt_dlp(*, check_only: bool = False) -> int:
    """Update the uv-managed yt-dlp lock and environment."""
    report_yt_dlp_versions()
    project_root = Path(root_dir)

    if check_only:
        _print_message("Dry run: checking what uv would update.", style="cyan")
        return run_uv_command(["lock", "--upgrade-package", "yt-dlp", "--dry-run"], cwd=project_root)

    lock_rc = run_uv_command(["lock", "--upgrade-package", "yt-dlp"], cwd=project_root)
    if lock_rc != 0:
        _print_message("yt-dlp lockfile update failed.", style="magenta")
        return lock_rc

    sync_rc = run_uv_command(["sync", "--all-extras", "--reinstall-package", "yt-dlp"], cwd=project_root)
    if sync_rc != 0:
        _print_message("yt-dlp lockfile updated, but environment sync failed.", style="magenta")
        return sync_rc

    current_version, latest_version, _ = report_yt_dlp_versions()
    if latest_version is not None and current_version != latest_version:
        _print_message(
            "yt-dlp was updated for future vido runs. Restart the command if this shell still reports the old import.",
            style="yellow",
        )
    else:
        _print_message("yt-dlp update complete.", style="green")
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for video downloader."""
    default_config = "~/.config/rogkit/config.toml"
    parser = argparse.ArgumentParser(description="Rog's Movie Downloader")
    parser.add_argument("search", nargs="*", help="Search term, URL, or filename")
    parser.add_argument(
        "-c", "--config",
        default=default_config,
        help=f"Path to config file (default: {default_config})"
    )
    parser.add_argument(
        "--update", "-u",
        action="store_true",
        help="Upgrade yt-dlp in the uv-managed rogkit environment and exit"
    )
    parser.add_argument(
        "--check-update",
        action="store_true",
        help="Check the yt-dlp update path without changing the lockfile or environment"
    )
    parser.add_argument("-d", "--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("-p", "--plain", action="store_true", help="Plain text output")
    args = parser.parse_args(argv)

    global _PLAIN_OUTPUT
    _PLAIN_OUTPUT = args.plain

    if args.update or args.check_update:
        return update_yt_dlp(check_only=args.check_update)

    # Expand ~ to full path
    args.config = os.path.expanduser(args.config)

    # Fallback to legacy config path if the preferred config file doesn't exist
    if not os.path.exists(args.config):
        legacy_path = os.path.expanduser("~/.rogkit.toml")
        if os.path.exists(legacy_path):
            _print_message(f"Config not found at {args.config}, falling back to legacy: {legacy_path}", style="yellow")
            args.config = legacy_path
        else:
            _print_message(f"No configuration file found at {args.config} or legacy location.", style="red")
            return 1

    # Load and print config (example usage)
    try:
        with open(args.config, 'r', encoding='utf-8') as f:
            config_data = toml.load(f)
            if args.debug:
                _print_message("Loaded config:")
                _print_message(toml.dumps(config_data))
    except Exception as e:
        _print_message(f"Failed to load config from {args.config}: {e}", style="red")
        return 1

    config = Config(args.config)

    if args.search:
        search = args.search
    else:
        search = input("Enter URL, filename or search term: ")

    if args.debug:
        get_movies(search, config)
    else:
        try:
            get_movies(search, config)
        except Exception as e:
            _print_message(f"Error: {e}", style="magenta")
            return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
