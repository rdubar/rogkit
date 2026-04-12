#!/usr/bin/env python3
"""Check HTTP status, redirects, timing, and content type for URLs."""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import requests
from requests import RequestException

from ..settings import get_invoking_cwd

try:
    from rich.console import Console
    from rich.table import Table
    from rich.text import Text

    console = Console()
    RICH_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover
    console = None  # type: ignore[assignment]
    RICH_AVAILABLE = False


DEFAULT_TIMEOUT = 10


@dataclass(frozen=True)
class CheckResult:
    """HTTP probe result for a single URL."""

    url: str
    final_url: str | None
    status_code: int | None
    elapsed_ms: int | None
    content_type: str
    redirect_count: int
    ok: bool
    error: str | None = None


def _print_message(message: str, *, style: str | None = None) -> None:
    """Print with optional Rich styling and a plain fallback."""
    if RICH_AVAILABLE:
        console.print(Text(message, style=style) if style else message)
    else:
        print(message)


def _normalize_url(url: str) -> str:
    """Ensure URLs have a scheme so requests can fetch them."""
    if url.startswith(("http://", "https://")):
        return url
    return f"https://{url}"


def _read_urls(args: argparse.Namespace) -> list[str]:
    """Collect URLs from CLI args, a file, and/or stdin."""
    urls: list[str] = []
    urls.extend(args.urls)

    if args.file:
        path = Path(args.file).expanduser()
        if not path.is_absolute():
            path = get_invoking_cwd() / path
        with path.open(encoding="utf-8") as handle:
            urls.extend(line.strip() for line in handle if line.strip())

    stdin_is_available = False
    try:
        stdin_is_available = not sys.stdin.isatty()
    except OSError:
        stdin_is_available = False

    if stdin_is_available:
        try:
            urls.extend(line.strip() for line in sys.stdin if line.strip())
        except OSError:
            pass

    seen: set[str] = set()
    deduped: list[str] = []
    for url in urls:
        if url in seen:
            continue
        seen.add(url)
        deduped.append(url)
    return deduped


def check_url(url: str, timeout: int = DEFAULT_TIMEOUT) -> CheckResult:
    """Perform a GET request and capture status, timing, and redirect metadata."""
    target = _normalize_url(url)
    started = time.perf_counter()
    try:
        response = requests.get(target, timeout=timeout, allow_redirects=True)
    except RequestException as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return CheckResult(
            url=target,
            final_url=None,
            status_code=None,
            elapsed_ms=elapsed_ms,
            content_type="-",
            redirect_count=0,
            ok=False,
            error=str(exc),
        )

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    content_type = response.headers.get("content-type", "-").split(";")[0].strip() or "-"
    return CheckResult(
        url=target,
        final_url=response.url,
        status_code=response.status_code,
        elapsed_ms=elapsed_ms,
        content_type=content_type,
        redirect_count=len(response.history),
        ok=200 <= response.status_code < 300,
        error=None,
    )


def check_urls(urls: Sequence[str], timeout: int = DEFAULT_TIMEOUT) -> list[CheckResult]:
    """Check a sequence of URLs."""
    return [check_url(url, timeout=timeout) for url in urls]


def render_results(results: Sequence[CheckResult], *, plain: bool = False) -> None:
    """Render check results as a Rich table or aligned plain text."""
    if not results:
        _print_message("No URLs provided.", style="yellow")
        return

    if RICH_AVAILABLE and not plain:
        table = Table(header_style="bold cyan", show_lines=False)
        table.add_column("Status", justify="right", no_wrap=True)
        table.add_column("Time", justify="right", no_wrap=True)
        table.add_column("Redirects", justify="right", no_wrap=True)
        table.add_column("Type", no_wrap=True)
        table.add_column("URL", overflow="fold")
        table.add_column("Final", overflow="fold")
        for item in results:
            status = "ERR" if item.status_code is None else str(item.status_code)
            status_style = "green" if item.ok else "bold red"
            elapsed = "-" if item.elapsed_ms is None else f"{item.elapsed_ms}ms"
            final_url = item.error or (item.final_url if item.final_url and item.final_url != item.url else "")
            table.add_row(
                Text(status, style=status_style),
                elapsed,
                str(item.redirect_count),
                item.content_type,
                item.url,
                final_url,
            )
        console.print(table)
        return

    print(f"{'STATUS':>6}  {'TIME':>8}  {'REDIR':>5}  {'TYPE':<20}  URL")
    print("-" * 100)
    for item in results:
        status = "ERR" if item.status_code is None else str(item.status_code)
        elapsed = "-" if item.elapsed_ms is None else f"{item.elapsed_ms}ms"
        print(f"{status:>6}  {elapsed:>8}  {item.redirect_count:>5}  {item.content_type:<20}  {item.url}")
        if item.error:
            print(f"        error: {item.error}")
        elif item.final_url and item.final_url != item.url:
            print(f"        final: {item.final_url}")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Check HTTP status, timing, redirects, and content type for one or more URLs."
    )
    parser.add_argument("urls", nargs="*", help="One or more URLs to check")
    parser.add_argument("-f", "--file", help="Read newline-delimited URLs from a file")
    parser.add_argument("--watch", type=float, metavar="SECONDS", help="Repeat checks every N seconds")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help=f"Request timeout in seconds (default {DEFAULT_TIMEOUT})")
    parser.add_argument("--plain", action="store_true", help="Plain text output")
    return parser.parse_args()


def _run_once(urls: Sequence[str], *, timeout: int, plain: bool) -> int:
    """Check URLs once and render results."""
    results = check_urls(urls, timeout=timeout)
    render_results(results, plain=plain)
    return 0 if all(item.ok for item in results) else 1


def main() -> int:
    """CLI entry point."""
    _ = get_invoking_cwd()
    args = parse_args()
    try:
        urls = _read_urls(args)
    except FileNotFoundError:
        print(f"error: file not found: {args.file}", file=sys.stderr)
        return 1

    if not urls:
        print("error: provide at least one URL, --file, or stdin input", file=sys.stderr)
        return 1

    if args.watch:
        exit_code = 0
        try:
            while True:
                if not args.plain:
                    console.rule("httpcheck") if RICH_AVAILABLE else None
                exit_code = _run_once(urls, timeout=args.timeout, plain=args.plain)
                time.sleep(args.watch)
        except KeyboardInterrupt:
            return exit_code

    return _run_once(urls, timeout=args.timeout, plain=args.plain)


if __name__ == "__main__":
    raise SystemExit(main())
