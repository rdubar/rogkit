#!/usr/bin/env python3
"""Decode JWT header and payload without signature verification."""

from __future__ import annotations

import argparse
import base64
import json
import sys
from datetime import UTC, datetime
from typing import Any

from ..settings import get_invoking_cwd

try:
    from rich.console import Console
    from rich.syntax import Syntax
    from rich.text import Text

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


def _read_token(token: str | None) -> str:
    """Read a token argument or fall back to stdin."""
    if token is not None:
        return token.strip()
    try:
        if sys.stdin.isatty():
            raise ValueError("Provide a JWT token or pipe one on stdin.")
    except OSError:
        pass
    data = sys.stdin.read().strip()
    if not data:
        raise ValueError("No token provided.")
    return data


def _decode_segment(segment: str) -> Any:
    """Decode one base64url JSON JWT segment."""
    padding = "=" * (-len(segment) % 4)
    try:
        raw = base64.urlsafe_b64decode(segment + padding)
    except (ValueError, base64.binascii.Error) as exc:
        raise ValueError("Invalid JWT encoding.") from exc
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("JWT segment is not valid JSON.") from exc


def decode_jwt(token: str) -> dict[str, Any]:
    """Return decoded header and payload for a JWT."""
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("JWT must have exactly 3 dot-separated segments.")
    header = _decode_segment(parts[0])
    payload = _decode_segment(parts[1])
    return {
        "header": header,
        "payload": payload,
        "signature": parts[2],
    }


def _format_epoch_claim(value: Any) -> dict[str, str] | None:
    """Convert a numeric JWT time claim into friendly UTC/local strings."""
    if not isinstance(value, (int, float)):
        return None
    try:
        dt_utc = datetime.fromtimestamp(value, UTC)
    except (OverflowError, OSError, ValueError):
        return None
    dt_local = dt_utc.astimezone()
    return {
        "epoch": str(int(value)),
        "utc": dt_utc.isoformat().replace("+00:00", "Z"),
        "local": dt_local.isoformat(),
    }


def annotate_time_claims(data: dict[str, Any]) -> dict[str, Any]:
    """Add friendly metadata for common JWT time claims when present."""
    payload = data.get("payload")
    if not isinstance(payload, dict):
        return data

    time_claims: dict[str, dict[str, str]] = {}
    for claim in ("exp", "iat", "nbf"):
        formatted = _format_epoch_claim(payload.get(claim))
        if formatted is not None:
            time_claims[claim] = formatted

    if not time_claims:
        return data

    annotated = dict(data)
    annotated["time_claims"] = time_claims
    return annotated


def render_decoded(data: dict[str, Any], *, compact: bool = False, plain: bool = False) -> None:
    """Render decoded JWT data as JSON."""
    indent = None if compact else 2
    text = json.dumps(data, indent=indent, ensure_ascii=False)
    if RICH_AVAILABLE and not plain:
        console.print(Syntax(text, "json", theme="monokai", word_wrap=True))
    else:
        print(text)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Decode JWT header and payload without verification.")
    parser.add_argument("token", nargs="?", help="JWT token (or pipe on stdin)")
    parser.add_argument("-c", "--compact", action="store_true", help="Compact output")
    parser.add_argument("--plain", action="store_true", help="Plain text output")
    return parser.parse_args()


def main() -> int:
    """CLI entry point."""
    _ = get_invoking_cwd()
    args = parse_args()
    try:
        token = _read_token(args.token)
        decoded = annotate_time_claims(decode_jwt(token))
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    render_decoded(decoded, compact=args.compact, plain=args.plain)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
