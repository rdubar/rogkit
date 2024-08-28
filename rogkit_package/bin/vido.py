import os
import sys
import argparse
import time
import datetime
import toml
from yt_dlp import YoutubeDL
from requests_html import HTMLSession
from colorama import init, Fore

# Initialize colorama
init(autoreset=True)

class Config:
    def __init__(self, config_file):
        try:
            self.config = toml.load(config_file)
            self.temp_folder = self.config['yout']['temp_folder']
            self.download_folder = self.config['yout']['download_folder']
            self.default_input_file = self.config['yout']['default_input_file']
        except Exception as e:
            print(Fore.MAGENTA + f"Failed to load [yout] section of config file {config_file}: {e}")
            exit(1)

    def get_download_options(self):
        return {
            "format": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
            "outtmpl": "%(title).80s-%(id)s.%(ext)s",  # Limit title to 80 characters
        }

def get_title_from_url(url):
    ydl_opts = {'quiet': True, 'no_warnings': True, 'skip_download': True}
    try:
        with YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=False)
            return info_dict.get('title', None)
    except Exception as e:
        print(Fore.MAGENTA + f"Error fetching title with yt_dlp: {e}")
        return None

def set_directory(directory):
    try:
        os.chdir(directory)
        print(Fore.CYAN + "Output directory: ", os.getcwd())
    except Exception as e:
        print(Fore.MAGENTA + f"Failed to change directory: {e}")
        return False
    return True

def showtime(s: float) -> str:
    return f"{s:.5f} seconds" if s < 10 else datetime.timedelta(seconds=s)

def process_lines(lines, config):
    incoming = config.download_folder
    set_directory(incoming)

    print(lines)

    for line in lines:
        if "http" in line.lower():
            process_url(line, config)

def process_url(url, config):
    title = get_title_from_url(url)
    if not title:
        return

    print(Fore.CYAN + "Downloading:", title)
    try:
        with YoutubeDL(config.get_download_options()) as ydl:
            video_info = ydl.extract_info(url, download=True)
            output = ydl.prepare_filename(video_info)

            final_output = os.path.join(config.download_folder, output)
            os.rename(output, final_output)

    except Exception as e:
        print(Fore.MAGENTA + f"Error downloading {url}\n{e}")
        return

    print(Fore.GREEN + f"Downloaded to {final_output}")

def get_movies(search, config):
    clock = time.perf_counter()

    if isinstance(search, list) and len(search) == 1 and isinstance(search[0], str):
        search = search[0]

    if "-f" in search:
        search = config.default_input_file

    lines = [search]
    if type(search) == str and os.path.isfile(search):
        with open(search, "r", encoding="utf-8") as f:
            lines = f.readlines()

    process_lines(lines, config)
    print(Fore.CYAN + f"Completed tasks in {showtime(time.perf_counter() - clock)}.")

def main():
    parser = argparse.ArgumentParser(description="Rog's Movie Downloader")
    parser.add_argument("search", nargs="*", help="Search term, URL, or filename")
    parser.add_argument("-c", "--config", default="~/.rogkit.toml", help="Path to config file")
    parser.add_argument("-d", "--debug", action="store_true", help="Enable debug mode")
    args = parser.parse_args()

    if len(sys.argv) == 1:
        print(parser.description)
        
    if args.config == "~/.rogkit.toml":
        # get the users home directory
        home = os.path.expanduser("~")
        # get the path to the config file
        args.config = os.path.join(home, ".rogkit.toml")

    config = Config(args.config)

    search = args.search or input(Fore.CYAN + "Enter URL, filename or search term: ")

    if args.debug:
        get_movies(search, config)
    else:
        try:
            get_movies(search, config)
        except Exception as e:
            print(Fore.MAGENTA + f"Error: {e}")

if __name__ == "__main__":
    main()
