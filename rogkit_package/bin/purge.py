#!/usr/bin/env python3
"""
File purge utility for removing junk files.

Folder targets are read from the rogkit config `[purge]` section (`folders = [...]`)
when available; otherwise at least one `--folder PATH` must be supplied.

Recursively searches for and deletes files that satisfy all of:
  • extension whitelist (e.g., .txt, .nfo, .jpg)
  • case-insensitive substring match (no wildcards)
  • maximum size threshold
"""
import argparse
import os
from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Sequence, Set, Tuple

from ..bin.bytes import byte_size
from ..bin.delete import safe_delete
from .tomlr import get_config_value


def _process_text_list(raw_list: str) -> List[str]:
    return [
        line.strip().lower()
        for line in raw_list.strip().split("\n")
        if line.strip()
    ]


BASE_TEXT_MATCHES: List[str] = _process_text_list(
    """
._
00.nfo
ahashare.com
downloaded
new upcoming releases
rarbg
sample.
torrent
tsyifyup
visit me on facebook
www.yts
yif
yts
zone.identifier
"""
)

BASE_EXTENSIONS: Set[str] = {
    ".txt",
    ".nfo",
    ".exe",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".rtf",
    ".pdf",
}


def _normalise_extensions(extensions: Iterable[str]) -> Set[str]:
    result: Set[str] = set()
    for ext in extensions:
        ext = ext.strip()
        if not ext:
            continue
        if not ext.startswith("."):
            ext = f".{ext}"
        result.add(ext.lower())
    return result


def _prepare_text_matches(
    base_matches: Sequence[str],
    extra_matches: Optional[Iterable[str]] = None,
    positional: Optional[str] = None,
) -> List[str]:
    matches: List[str] = list(base_matches)
    if extra_matches:
        matches.extend(extra_matches)
    if positional:
        matches.append(positional)

    seen = set()
    deduped: List[str] = []
    for match in matches:
        normalised = match.strip().lower()
        if not normalised:
            continue
        if normalised not in seen:
            seen.add(normalised)
            deduped.append(normalised)
    return deduped

@dataclass
class PurgeResults:
    """Encapsulates purge results including files to delete and total files scanned."""
    files_to_delete: List[str] = field(default_factory=list)
    total_files: int = 0
    skipped_extension: int = 0
    skipped_text: int = 0
    skipped_size: int = 0

def matches_criteria(
    path: str,
    text_matches: Sequence[str],
    extensions: Set[str],
    max_size: Optional[int],
) -> Tuple[bool, Optional[str]]:
    filename = os.path.basename(path)
    extension = os.path.splitext(filename)[1].lower()
    if extensions and extension not in extensions:
        return False, "extension"

    lower_name = filename.lower()
    lower_path = path.lower()
    if text_matches and not any(
        match in lower_name or match in lower_path for match in text_matches
    ):
        return False, "text"

    if max_size is not None:
        try:
            size = os.path.getsize(path)
        except OSError:
            return False, "size-unreadable"
        if size > max_size:
            return False, "size"

    return True, None


def search_and_collect_files(
    folders: Sequence[str],
    text_matches: Sequence[str],
    extensions: Set[str],
    max_size: Optional[int],
) -> PurgeResults:
    """Recursively search folders for files matching purge criteria."""
    results = PurgeResults()
    if not isinstance(folders, list):
        folders = [folders]
    for folder in folders:
        for root, dirs, files in os.walk(folder):
            for file in files:
                filepath = os.path.join(root, file)
                results.total_files += 1
                matched, reason = matches_criteria(
                    filepath, text_matches, extensions, max_size
                )
                if matched:
                    results.files_to_delete.append(filepath)
                else:
                    if reason == "extension":
                        results.skipped_extension += 1
                    elif reason == "text":
                        results.skipped_text += 1
                    elif reason in {"size", "size-unreadable"}:
                        results.skipped_size += 1
    return results
        
def _is_sample_media_file(path):
    """Check if file is a sample media file (not an actual media file)."""
    file = os.path.basename(path)
    return file.lower().startswith('sample.') or file.lower().endswith('.sample')

def delete_files(file_list):
    """Delete files from list, skipping actual media files for safety."""
    for file in file_list:
        # check for media files
        if file.endswith(('.mkv', '.mp4', '.avi', '.srt')) and not _is_sample_media_file(file):
            print(f"Skipping media file: {file}")
            continue
        safe_delete(file)


def _expand_paths(entries: Iterable[str]) -> List[str]:
    expanded: List[str] = []
    for entry in entries:
        entry = entry.strip()
        if not entry:
            continue
        expanded.append(os.path.abspath(os.path.expanduser(entry)))
    return expanded


def _resolve_target_folders(cli_folders: Optional[Iterable[str]]) -> Tuple[List[str], bool]:
    config_value = get_config_value("purge", "folders")
    config_folders: List[str] = []
    if isinstance(config_value, str):
        config_folders = _expand_paths([config_value])
    elif isinstance(config_value, (list, tuple, set)):
        config_folders = _expand_paths(config_value)

    if config_folders:
        return config_folders, True

    cli_list = _expand_paths(cli_folders or [])
    return cli_list, False


def main():
    """CLI entry point for file purge utility."""
    parser = argparse.ArgumentParser(
        description=(
            "Search and delete junk files. Matches only if extension, substring, "
            "and size filters all pass. Folder roots come from rogkit config "
            "[purge].folders unless --folder is supplied."
        )
    )
    parser.add_argument(
        "pattern",
        nargs="?",
        default=None,
        help="Optional additional case-insensitive substring to require.",
    )
    parser.add_argument(
        "-t",
        "--text",
        action="append",
        dest="extra_text",
        help="Additional substring to require (can be repeated).",
    )
    parser.add_argument(
        "-d", "--dsstore", action="store_true", help="Include .DS_Store files."
    )
    parser.add_argument(
        "-c", "--confirm", action="store_true", help="Confirm deletion of files."
    )
    parser.add_argument(
        "-f",
        "--folder",
        action="append",
        dest="folders",
        help="Folder to search (can be repeated).",
    )
    parser.add_argument(
        "-p", "--purge-list", action="store_true", help="Show the base substrings."
    )
    parser.add_argument(
        "-e",
        "--ext",
        action="append",
        dest="extra_extensions",
        help="Additional extension to include (can be repeated).",
    )
    parser.add_argument(
        "--max-size",
        type=float,
        default=5.0,
        help="Maximum file size in MiB (<=0 to disable). Default 5.",
    )
    args = parser.parse_args()

    if args.purge_list:
        print("Base substrings used for purge matching:")
        for item in BASE_TEXT_MATCHES:
            print(item)
        return

    folder_candidates, from_config = _resolve_target_folders(args.folders)
    folders = [path for path in folder_candidates if os.path.isdir(path)]
    missing = sorted(set(folder_candidates) - set(folders))

    if not folders:
        if from_config:
            print(
                "No valid purge folders found in rogkit config. "
                "Update [purge].folders or supply --folder PATH."
            )
        else:
            print(
                "No purge folders supplied. Provide --folder PATH or configure "
                "[purge] folders in rogkit config."
            )
        return

    if missing:
        print("Skipping missing folders:")
        for path in missing:
            print(f"  {path}")

    source_label = "rogkit config" if from_config else "command line"
    print(f"Scanning folders from {source_label}: {folders}")

    text_matches = _prepare_text_matches(
        BASE_TEXT_MATCHES,
        args.extra_text,
        args.pattern,
    )
    extensions = _normalise_extensions(BASE_EXTENSIONS)
    if args.extra_extensions:
        extensions.update(_normalise_extensions(args.extra_extensions))

    if args.dsstore:
        print("Including .DS_Store files.")
        extensions.add(".ds_store")
        text_matches.append(".ds_store")

    if args.max_size and args.max_size > 0:
        max_size_bytes: Optional[int] = int(args.max_size * 1024 * 1024)
    else:
        max_size_bytes = None

    print(
        f"Searching {folders} for files to purge "
        f"(extensions={sorted(extensions)}, substrings={len(text_matches)}, "
        f"max_size={'disabled' if max_size_bytes is None else byte_size(max_size_bytes)})..."
    )

    results = search_and_collect_files(folders, text_matches, extensions, max_size_bytes)
    print(
        f"Found {len(results.files_to_delete):,} files to delete "
        f"from {results.total_files:,} files scanned."
    )
    if results.skipped_extension:
        print(f"  Skipped {results.skipped_extension:,} files due to extension filter.")
    if results.skipped_text:
        print(f"  Skipped {results.skipped_text:,} files due to substring filter.")
    if results.skipped_size:
        print(f"  Skipped {results.skipped_size:,} files due to size filter.")

    if args.confirm:
        delete_files(results.files_to_delete)
    elif results.files_to_delete:
        print("Files to be deleted (use --confirm to actually delete):")
        for file in results.files_to_delete:
            size = os.path.getsize(file)
            print(f"{byte_size(size):>10}   {file}")


if __name__ == "__main__":
    main()
