#!/usr/bin/env python3
"""Serve a local directory over HTTP for quick previews."""

from __future__ import annotations

import argparse
import functools
import os
import socket
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from ..settings import get_invoking_cwd

try:
    from rich.console import Console
    from rich.text import Text

    console = Console()
    RICH_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover
    console = None  # type: ignore[assignment]
    RICH_AVAILABLE = False


DEFAULT_PORT = 8000
DEFAULT_HOST = "127.0.0.1"


def _print_message(message: str, *, style: str | None = None) -> None:
    """Print with optional Rich styling and a plain fallback."""
    if RICH_AVAILABLE:
        console.print(Text(message, style=style) if style else message)
    else:
        print(message)


def resolve_directory(raw_path: str | None) -> Path:
    """Resolve the directory to serve, defaulting to the invoking cwd."""
    cwd = get_invoking_cwd()
    if raw_path is None:
        return cwd
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = cwd / path
    return path.resolve()


def local_url(host: str, port: int) -> str:
    """Return the local URL for the server."""
    return f"http://{host}:{port}/"


def make_server(directory: Path, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> ThreadingHTTPServer:
    """Create a configured HTTP server for the target directory."""
    handler = functools.partial(SimpleHTTPRequestHandler, directory=str(directory))
    return ThreadingHTTPServer((host, port), handler)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Serve a local directory over HTTP.")
    parser.add_argument("port", nargs="?", type=int, default=DEFAULT_PORT, help=f"Port to bind (default: {DEFAULT_PORT})")
    parser.add_argument("--path", help="Directory to serve (default: invoking cwd)")
    parser.add_argument("--host", default=DEFAULT_HOST, help=f"Host/interface to bind (default: {DEFAULT_HOST})")
    return parser.parse_args()


def main() -> int:
    """CLI entry point."""
    args = parse_args()
    directory = resolve_directory(args.path)

    if not directory.exists():
        print(f"error: directory not found: {directory}", file=sys.stderr)
        return 1
    if not directory.is_dir():
        print(f"error: not a directory: {directory}", file=sys.stderr)
        return 1

    try:
        server = make_server(directory, host=args.host, port=args.port)
    except OSError as exc:
        print(f"error: unable to start server: {exc}", file=sys.stderr)
        return 1

    try:
        _print_message(f"Serving {directory}", style="green")
        _print_message(f"URL: {local_url(args.host, args.port)}", style="cyan")
        _print_message("Press Ctrl+C to stop.", style="dim")
        server.serve_forever()
    except KeyboardInterrupt:
        _print_message("\nServer stopped.", style="yellow")
    finally:
        server.server_close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
