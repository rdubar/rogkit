#!/usr/bin/env python3
"""Inspect or extract files from zip, tar, and gzip archives."""

from __future__ import annotations

import argparse
import gzip
import shutil
import sys
import tarfile
import zipfile
from pathlib import Path, PurePosixPath

from ..settings import get_invoking_cwd

try:
    from rich.console import Console
    from rich.text import Text
    from rich.tree import Tree

    console = Console()
    RICH_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover
    console = None  # type: ignore[assignment]
    RICH_AVAILABLE = False


def _print_message(message: str, *, style: str | None = None) -> None:
    """Print with optional Rich styling and a plain fallback."""
    if RICH_AVAILABLE:
        console.print(Text(message, style=style) if style else message)
    else:
        print(message)


def _archive_kind(path: Path) -> str:
    """Return the supported archive kind for *path*."""
    lower = path.name.lower()
    if lower.endswith(".zip"):
        return "zip"
    if lower.endswith((".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tbz2", ".tar.xz", ".txz")):
        return "tar"
    if lower.endswith(".gz"):
        return "gzip"
    raise ValueError(f"Unsupported archive type: {path.name}")


def _gzip_member_name(path: Path) -> str:
    """Infer the decompressed filename for a .gz archive."""
    return path.name[:-3] if path.name.lower().endswith(".gz") else path.name


def list_archive(path: Path) -> list[str]:
    """Return member names for a supported archive."""
    kind = _archive_kind(path)
    if kind == "zip":
        with zipfile.ZipFile(path) as archive:
            return archive.namelist()
    if kind == "tar":
        with tarfile.open(path, "r:*") as archive:
            return archive.getnames()
    return [_gzip_member_name(path)]


def read_member(path: Path, member: str | None = None) -> bytes:
    """Return the bytes for one archive member or the single gzip payload."""
    kind = _archive_kind(path)
    if kind == "zip":
        if not member:
            raise ValueError("A member path is required for zip archives.")
        with zipfile.ZipFile(path) as archive:
            with archive.open(member) as handle:
                return handle.read()
    if kind == "tar":
        if not member:
            raise ValueError("A member path is required for tar archives.")
        with tarfile.open(path, "r:*") as archive:
            extracted = archive.extractfile(member)
            if extracted is None:
                raise KeyError(f"Member not found or is not a file: {member}")
            return extracted.read()

    gzip_name = _gzip_member_name(path)
    if member and member != gzip_name:
        raise KeyError(f"Member not found: {member}")
    with gzip.open(path, "rb") as archive:
        return archive.read()


def _safe_target(base: Path, member_name: str) -> Path:
    """Return a safe destination path under *base* for *member_name*."""
    parts = [part for part in PurePosixPath(member_name).parts if part not in ("", ".", "..")]
    if not parts:
        raise ValueError(f"Invalid archive member path: {member_name!r}")
    target = base.joinpath(*parts).resolve()
    base_resolved = base.resolve()
    if not str(target).startswith(str(base_resolved)):
        raise ValueError(f"Refusing to write outside destination: {member_name}")
    return target


def extract_all(path: Path, destination: Path) -> list[Path]:
    """Extract the full archive safely into *destination*."""
    kind = _archive_kind(path)
    destination.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    if kind == "zip":
        with zipfile.ZipFile(path) as archive:
            for member in archive.infolist():
                target = _safe_target(destination, member.filename)
                if member.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member) as source, target.open("wb") as dest:
                    shutil.copyfileobj(source, dest)
                written.append(target)
        return written

    if kind == "tar":
        with tarfile.open(path, "r:*") as archive:
            for member in archive.getmembers():
                target = _safe_target(destination, member.name)
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                if not member.isfile():
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                extracted = archive.extractfile(member)
                if extracted is None:
                    continue
                with extracted, target.open("wb") as dest:
                    shutil.copyfileobj(extracted, dest)
                written.append(target)
        return written

    target = destination / _gzip_member_name(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "rb") as source, target.open("wb") as dest:
        shutil.copyfileobj(source, dest)
    written.append(target)
    return written


def render_listing(path: Path, members: list[str], *, plain: bool = False) -> None:
    """Render archive contents as a tree or plain line list."""
    if not members:
        _print_message(f"{path.name}: (empty)", style="yellow")
        return

    if RICH_AVAILABLE and not plain:
        tree = Tree(f"[bold cyan]{path.name}[/bold cyan]")
        nodes: dict[tuple[str, ...], Tree] = {(): tree}
        for member in members:
            parts = tuple(part for part in PurePosixPath(member).parts if part not in ("", "."))
            cursor: tuple[str, ...] = ()
            for part in parts:
                next_cursor = cursor + (part,)
                if next_cursor not in nodes:
                    nodes[next_cursor] = nodes[cursor].add(part)
                cursor = next_cursor
        console.print(tree)
        return

    print(path.name)
    print("-" * len(path.name))
    for member in members:
        print(member)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Inspect archives, print a single member to stdout, or extract the full archive."
    )
    parser.add_argument("archive", help="Archive path")
    parser.add_argument(
        "target",
        nargs="?",
        help="Member to print to stdout, or destination directory when used with -x/--extract-all",
    )
    parser.add_argument("-x", "--extract-all", action="store_true", help="Extract the full archive")
    parser.add_argument("--plain", action="store_true", help="Plain text output")
    return parser.parse_args()


def main() -> int:
    """CLI entry point."""
    cwd = get_invoking_cwd()
    args = parse_args()
    archive_path = Path(args.archive).expanduser()
    if not archive_path.is_absolute():
        archive_path = cwd / archive_path
    archive_path = archive_path.resolve()

    if not archive_path.exists():
        print(f"error: file not found: {archive_path}", file=sys.stderr)
        return 1

    try:
        if args.extract_all:
            destination = Path(args.target).expanduser() if args.target else cwd
            if not destination.is_absolute():
                destination = cwd / destination
            written = extract_all(archive_path, destination.resolve())
            _print_message(f"Extracted {len(written)} file(s) to {destination.resolve()}", style="green")
            return 0

        if args.target:
            data = read_member(archive_path, args.target)
            sys.stdout.buffer.write(data)
            return 0

        render_listing(archive_path, list_archive(archive_path), plain=args.plain)
        return 0
    except (ValueError, KeyError, tarfile.TarError, zipfile.BadZipFile, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
