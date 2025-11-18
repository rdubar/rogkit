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

import os
import sys
import tempfile
import argparse
import time
import datetime
import toml  # type: ignore
from yt_dlp import YoutubeDL  # type: ignore
from colorama import init, Fore # type: ignore

# Initialize colorama
init(autoreset=True)

class Config:
    """Video downloader configuration from TOML file."""
    
    def __init__(self, config_file):
        try:
            self.config = toml.load(config_file)
            self.temp_folder = self.config['vido']['temp_folder']
            self.download_folder = self.config['vido']['download_folder']
            self.default_input_file = self.config['vido']['default_input_file']
        except Exception as e:
            print(Fore.MAGENTA + f"Failed to load [vido] section of config file {config_file}: {e}")
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
        print(Fore.MAGENTA + f"Error fetching title with yt_dlp: {e}")
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
        print(Fore.CYAN + "Working directory set to:", os.getcwd())
        return directory
    except Exception as e:
        print(Fore.MAGENTA + f"Failed to change directory: {e}")
        return None

def showtime(s: float) -> str:
    """Format time duration as seconds or timedelta."""
    return f"{s:.5f} seconds" if s < 10 else str(datetime.timedelta(seconds=s))


def process_lines(lines, config):
    """Process multiple lines/URLs for downloading."""
    temp_folder = config.temp_folder
    set_directory(temp_folder)

    print(Fore.CYAN + "Processing the following lines:")
    for line in lines:
        print(Fore.YELLOW + line.strip())

    for line in lines:
        if "http" in line.lower():
            process_url(line.strip(), config)

def process_url(url, config):
    """Download video from URL and move to final destination."""
    title = get_title_from_url(url)
    if not title:
        print(Fore.MAGENTA + "Skipping URL due to title fetch failure.")
        return

    print(Fore.CYAN + "Downloading:", title)
    try:
        with YoutubeDL(config.get_download_options()) as ydl:
            video_info = ydl.extract_info(url, download=True)
            output = ydl.prepare_filename(video_info)

            final_output = os.path.join(config.download_folder, os.path.basename(output))
            os.rename(output, final_output)

    except Exception as e:
        print(Fore.MAGENTA + f"Error downloading {url}\n{e}")
        return

    print(Fore.GREEN + f"Downloaded to {final_output}")

def get_movies(search, config):
    """Main function to download videos from URLs, files, or search terms."""
    clock = time.perf_counter()

    # Handle multiple parameters
    if isinstance(search, list) and len(search) > 1:
        print(Fore.CYAN + f"Processing {len(search)} parameters sequentially...")
        for i, item in enumerate(search, 1):
            print(Fore.YELLOW + f"\n--- Processing item {i}/{len(search)}: {item} ---")
            get_movies(item, config)  # Recursively process each item
        print(Fore.CYAN + f"\nCompleted all {len(search)} tasks in {showtime(time.perf_counter() - clock)}.")
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
        print(Fore.CYAN + "Processing single input.")

    process_lines(lines, config)
    print(Fore.CYAN + f"Completed task in {showtime(time.perf_counter() - clock)}.")
    
def update_yt_dlp():
    """Report whether a newer yt_dlp exists and how to upgrade (no installs)."""
    from importlib import metadata
    import json
    import urllib.request

    current_version = "unknown"
    try:
        current_version = metadata.version("yt_dlp")
    except metadata.PackageNotFoundError:
        print(Fore.MAGENTA + "yt_dlp is not currently installed in this environment.")
    except Exception as e:
        print(Fore.MAGENTA + f"Could not determine installed yt_dlp version: {e}")

    latest_version = None
    try:
        with urllib.request.urlopen("https://pypi.org/pypi/yt-dlp/json", timeout=5) as resp:
            data = json.load(resp)
            latest_version = data["info"]["version"]
    except Exception as e:
        print(Fore.MAGENTA + f"Unable to check PyPI for the latest yt_dlp release: {e}")
        print(Fore.CYAN + "You can manually check with `uv pip index versions yt-dlp` or visit https://pypi.org/project/yt-dlp/.")
        return

    print(Fore.CYAN + f"Installed yt_dlp version: {current_version}")
    print(Fore.CYAN + f"Latest    yt_dlp version: {latest_version}")

    def parse_version(v):
        try:
            from packaging.version import Version
            return Version(v)
        except Exception:
            return None

    parsed_installed = parse_version(current_version)
    parsed_latest = parse_version(latest_version)

    needs_upgrade = False
    if parsed_installed and parsed_latest:
        needs_upgrade = parsed_latest > parsed_installed
    elif current_version != "unknown" and latest_version:
        needs_upgrade = current_version != latest_version

    if needs_upgrade:
        print(Fore.YELLOW + f"Update available: {current_version} -> {latest_version}")
        print(Fore.CYAN + "Upgrade steps (uv-managed project):")
        print("  uv add -U yt-dlp")
        print("  uv export -o requirements.txt")
        print("  uv sync --all-extras")
    else:
        print(Fore.GREEN + "yt_dlp is up to date.")

def main():
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
        help="Check for a newer yt_dlp and show how to upgrade (no install)"
    )
    parser.add_argument("-d", "--debug", action="store_true", help="Enable debug mode")
    args = parser.parse_args()
    
    if args.update:
        update_yt_dlp()

    # Expand ~ to full path
    args.config = os.path.expanduser(args.config)

    # Fallback to legacy config path if the preferred config file doesn't exist
    if not os.path.exists(args.config):
        legacy_path = os.path.expanduser("~/.rogkit.toml")
        if os.path.exists(legacy_path):
            print(f"⚠️  Config not found at {args.config}, falling back to legacy: {legacy_path}")
            args.config = legacy_path
        else:
            print(f"❌ No configuration file found at {args.config} or legacy location.")
            sys.exit(1)

    # Load and print config (example usage)
    try:
        with open(args.config, 'r', encoding='utf-8') as f:
            config_data = toml.load(f)
            if args.debug:
                print("Loaded config:")
                print(toml.dumps(config_data))
    except Exception as e:
        print(f"❌ Failed to load config from {args.config}: {e}")
        sys.exit(1)

    config = Config(args.config)

    if args.search:
        search = args.search
    else:
        search = input(Fore.CYAN + "Enter URL, filename or search term: ")

    if args.debug:
        get_movies(search, config)
    else:
        try:
            get_movies(search, config)
        except Exception as e:
            print(Fore.MAGENTA + f"Error: {e}")

if __name__ == "__main__":
    main()
