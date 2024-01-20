#!/home/pi/.env/bin/python

import os, argparse, time, datetime
from yt_dlp import YoutubeDL
from requests_html import HTMLSession
from colorama import init, Fore

init(autoreset=True)  # colorama

ytdlp_options = {
    "format": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
    "outtmpl": "%(title)s-%(id)s.%(ext)s",
}


def get_title_from_url(url):
    return HTMLSession().get(url).html.find("title", first=True).text


SAVE_TO = [
    ("/mnt/expansion/Incomplete", "/mnt/expansion/Media/Incoming"),
    ("/Users/Roger/usr/temp", "/Users/roger/Downloads"),
    ("/home/rdubar/temp", "/home/rdubar/incoming"),
]

DEFAULT_FILE = "/home/pi/usr/media/data/movies.txt"


def set_directory(*dirs, default=False):
    """
    Set directory to the first available from the list provided
    Return the incoming folder
    """
    if not default:
        default = SAVE_TO
    if not dirs:
        dirs = default
    if type(dirs) != list:
        dirs = [dirs]
    incoming = None
    for location in dirs:
        if isinstance(location, (list, tuple)) and len(location) > 0:
            directory = location[0]
        else:
            directory = location
        if os.path.isdir(directory):
            try:
                os.chdir(directory)
                incoming = location[1]
                break
            except Exception as e:
                print(Fore.RED + f"Failed to change directory to {directory} {e}")
    else:
        print(Fore.RED + f"Unable to set output directory to {directory}")
    print(Fore.BLUE + "Output directory: ", os.getcwd())
    return incoming


def showtime(s: float) -> str:
    """return seconds (s) as H:M:S or seconds < 10"""
    return f"{s:.5f} seconds" if s < 10 else datetime.timedelta(seconds=s)


def get_movies(search, default=DEFAULT_FILE, verbose=False):
    # is search term a file?
    clock = time.perf_counter()
    if verbose:
        print("Verbose mode. Does not do anything yet.")
    print(Fore.MAGENTA + f"Getting movies: {search}")
    if "-f" in search:
        search = default
    if type(search) == str and os.path.exists(search):
        with open(search, "r", encoding="utf-8") as f:
            lines = f.readlines()
            print(Fore.GREEN + f"Processing file {search} ({len(lines)} lines)")
    elif type(search) != list:
        lines = [search]
    else:
        lines = search

    # set working directory to ensure out in correct place
    incoming = set_directory()

    # Calculate how many items will be downloaded
    total = 0
    completed = 0

    def s(x):
        if x == 1:
            return ""
        else:
            return "s"

    # print(lines)
    for i in lines:
        if "http" in i.lower():
            total += 1
    print(Fore.MAGENTA + f"{total} item{s(total)} to download.")

    for item in lines:
        if item[0] == "#":
            print(item)

        elif item[:4].lower() == "http":
            title = get_title_from_url(item)
            print(Fore.GREEN + "Downloading:", title)
            try:
                with YoutubeDL(ytdlp_options) as ydl:
                    video_info = ydl.extract_info(item, download=True)
                    output = ydl.prepare_filename(video_info)
            except Exception as e:
                print(Fore.RED + f"Error downloading {item}\n{e}")
                output = None

            if incoming and output:
                print(f"Moving {output} to {incoming}")
                os.rename(output, incoming + "/" + output)
            completed += 1
            print(Fore.GREEN + f"Downloaded {completed} of {total}.")

        else:
            s = item.replace(" ", "+")
            print(Fore.BLUE + f"Search for: {item}")
            print(
                Fore.MAGENTA
                + f"https://duckduckgo.com/?q={s}&iax=videos&ia=videos&iaf=videoDuration%3Along"
            )
    clock = time.perf_counter() - clock
    print(Fore.GREEN + f"Completed tasks in {showtime(clock)}.")


def set_get_subtitles():
    print("Attempting to get subtitles...")
    ydl_opts = {
        #'outtmpl': '/Downloads/%(title)s_%(ext)s.mp4',
        "format": "(bestvideo[width>=1080][ext=mp4])+bestaudio/best",
        "writesubtitles": True,
        "subtitle": "--write-sub --sub-lang en",
    }


def main():
    print(Fore.MAGENTA + "Rogkit Yout(ube) Movie Downloader")
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "search",
        help="Search for movies (URL, filename or search term)",
        type=str,
        nargs="*",
    )
    parser.add_argument(
        "-f",
        "--file",
        help=f"Search using file (default: {DEFAULT_FILE})",
        nargs="*",
        type=get_movies,
    )
    parser.add_argument(
        "-s", "--subs", help="attempt to get subtitles", action="store_true"
    )
    parser.add_argument(
        "-v", "--verbose", help="increase output verbosity", action="store_true"
    )
    args = parser.parse_args()
    verbose = args.verbose
    if verbose:
        print(args)

    if args.subs:
        set_get_subtitles()

    if args.file is not None:
        search = "-f"
    elif args.search == []:
        search = input(Fore.CYAN + "Enter URL, filename or search term: ")
    else:
        search = args.search

    if search:
        get_movies(search, verbose=verbose)


if __name__ == "__main__":
    main()
