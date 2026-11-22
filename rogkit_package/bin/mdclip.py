#!/usr/bin/env python3
"""Turn a Markdown file into HTML and put it on the clipboard as rich text.

Paste the result into Substack, Gmail, Google Docs and the like and the headings,
bold, links, lists and code blocks come through. Plain-text targets get the
original Markdown.

    mdclip post.md            # copy as rich text
    mdclip bug hunter         # not a path? found by name with opener's `o`
    mdclip post.md --body     # drop the leading "# Title" (Substack has its own title box)
    mdclip post.md --print    # print the HTML instead of copying
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from markdown_it import MarkdownIt

from ..settings import get_invoking_cwd
from .findfile import find_file

try:  # optional rich formatting
    from rich.console import Console
    from rich.text import Text

    console = Console()
    RICH_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover
    console = None
    RICH_AVAILABLE = False

URL_RE = re.compile(r'(?<![("\'=>\]])\b(https?://[^\s<>()]+[^\s<>().,;:!?\'"])')
COMMENT_RE = re.compile(r"<!--.*?-->\s*", re.DOTALL)


def _print_message(message: str, *, style: str | None = None) -> None:
    """Print with optional rich styling, fallback to plain print."""
    if RICH_AVAILABLE:
        console.print(Text(message, style=style) if style else message)
    else:
        print(message)


def prepare_markdown(text: str, *, body: bool = False) -> str:
    """Strip HTML comments and, with body=True, the first level-1 heading."""
    text = COMMENT_RE.sub("", text)
    if body:
        text = re.sub(r"\A\s*# [^\n]*\n+", "", text, count=1)
    return text


def _autolink(html: str) -> str:
    """Link bare URLs in text, leaving <a> and <code>/<pre> contents alone."""
    out, depth = [], 0
    for part in re.split(r"(<[^>]+>)", html):
        if part.startswith("<"):
            tag = part.lower()
            if re.match(r"<(a|code|pre)\b", tag):
                depth += 1
            elif re.match(r"</(a|code|pre)>", tag):
                depth = max(0, depth - 1)
            out.append(part)
        else:
            out.append(part if depth else URL_RE.sub(r'<a href="\1">\1</a>', part))
    return "".join(out)


def markdown_to_html(text: str) -> str:
    """Render Markdown (CommonMark plus tables and strikethrough) to an HTML fragment."""
    md = MarkdownIt("commonmark", {"html": True}).enable(["table", "strikethrough"])
    return _autolink(md.render(text))


def copy_html(html: str, plain: str) -> str:
    """Put HTML (rich text) and plain text on the system clipboard. Returns how it was done."""
    if sys.platform == "darwin":
        with tempfile.TemporaryDirectory() as tmp:
            h, p = Path(tmp, "c.html"), Path(tmp, "c.txt")
            h.write_text(html, encoding="utf-8")
            p.write_text(plain, encoding="utf-8")
            script = (
                "ObjC.import('AppKit');"
                "function run(a){"
                "const r=f=>$.NSString.stringWithContentsOfFileEncodingError(f,$.NSUTF8StringEncoding,null);"
                "const pb=$.NSPasteboard.generalPasteboard;pb.clearContents;"
                "pb.setStringForType(r(a[0]),$.NSPasteboardTypeHTML);"
                "pb.setStringForType(r(a[1]),$.NSPasteboardTypeString);}"
            )
            subprocess.run(["osascript", "-l", "JavaScript", "-e", script, str(h), str(p)], check=True)
        return "macOS pasteboard (HTML + plain text)"
    # wl-copy and xclip stay running to serve the clipboard; detach their output so ssh can exit.
    if shutil.which("wl-copy"):
        subprocess.run(["wl-copy", "--type", "text/html"], input=html.encode(), check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return "wl-copy (HTML)"
    if shutil.which("xclip"):
        subprocess.run(["xclip", "-selection", "clipboard", "-t", "text/html"], input=html.encode(), check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return "xclip (HTML)"
    raise RuntimeError("No HTML clipboard found: install wl-clipboard (Wayland) or xclip (X11).")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Copy a Markdown file to the clipboard as rich text (HTML).")
    parser.add_argument("file", nargs="+", help="a Markdown file, or words in its name (found with opener's o)")
    parser.add_argument("--body", action="store_true", help="drop the leading '# Title' line")
    parser.add_argument("--print", dest="print_only", action="store_true", help="print the HTML, don't copy")
    return parser.parse_args()


def main() -> int:
    """CLI entry point."""
    args = parse_args()
    try:
        path = find_file(args.file, suffixes=(".md", ".markdown"), cwd=get_invoking_cwd())
    except FileNotFoundError as e:
        _print_message(str(e), style="red")
        return 1
    if not path:
        _print_message(f"No Markdown file found for: {' '.join(args.file)}", style="red")
        return 1
    source = prepare_markdown(path.read_text(encoding="utf-8"), body=args.body)
    html = markdown_to_html(source)
    if args.print_only:
        print(html)
        return 0
    try:
        how = copy_html(html, source)
    except (RuntimeError, subprocess.CalledProcessError) as e:
        _print_message(f"Could not copy: {e}", style="red")
        return 1
    words = len(re.findall(r"\w+", source))
    _print_message(f"Copied {path.name} as rich text ({words} words) via {how}. Paste away.", style="green")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
