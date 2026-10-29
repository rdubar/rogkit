#!/usr/bin/env python3
"""Look inside JSON without printing values you did not ask for.

jqsafe is a safe-by-default companion to ``json`` and ``jq``. With no options it
prints the *shape* of a document (paths, types, counts, string lengths) and no
values at all. Values appear only for the exact paths you name with ``--show``
(or a preset). Keys that look personal (name, street, phone, token, ...) never
have their values printed, even when named, and cannot be used in ``[key=value]``
filters either. Meant for humans reading a file that may hold customer data, and
for AI agents that must not pull that data into a session.

What it protects, and what it does not:
  * Values are never printed unless you name the path (shape mode prints none).
  * Dict keys that look like data (an email, an id, a name with spaces, or a
    dict with more than 20 keys) are shown as ``{key}`` in shape mode.
  * Short plain-word keys of a small dict are still shown: they are treated as
    structure. If a document keys a small dict by a single-word name, use
    ``--show`` on leaves only and do not trust shape mode for that file.
  * ``--present`` prints only True/False. It may name a personal-looking key, so
    that "is there a tracking number?" works, but it cannot filter on one.
  * A ``[key=value]`` filter reveals only whether the value you typed matches.

Usage:
    jqsafe payload.json                          # shape only, no values
    jqsafe payload.json --show Status.Code       # values for one path
    jqsafe payload.json --show 'Items.Qty' --present 'Items[ID.scheme=TRACKING].ID.value'
    jqsafe payload.json --preset bitergo-respond-shipment
    cat payload.json | jqsafe - --show a.b --json
    jqsafe --list-presets

Path syntax (dot separated):
    a.b            nested keys; a list met on the way is mapped over implicitly
    a[]            every element of a list (same as above, explicit)
    a[2]           one element
    a[x.y=VALUE]   elements whose child x.y equals VALUE (as text; true/false for booleans)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from ..settings import get_invoking_cwd

MAX_VALUE_CHARS = 80
MAX_SHAPE_KEYS = 20
USER_PRESET_DIR = Path.home() / ".config" / "rogkit" / "jqsafe"

# Whole words (split on camelCase, snake_case and digits) that mark a key as personal.
DENY_WORDS = frozenset(
    "name surname forename firstname lastname fullname fname lname nm street city postal postcode zipcode zip plz "
    "phone telephone tel mobile cell fax email mail address addr contact iban bic vat ustid taxid tax birth "
    "birthdate dob ssn gender password passwd pin secret token credential credentials cookie session bearer jwt "
    "auth authorization authorisation tracking binary deliverynote pdf salary payroll consignee recipient apikey geo lat lon".split()
)
DENY_PAIRS = (("api", "key"), ("account", "number"), ("tax", "id"))
# Substrings that mark a key as personal after lowercasing and removing separators
# (catches all-lowercase compounds such as "customername" or "phonenumber").
DENY_STEMS = (
    "name", "phone", "mail", "street", "addr", "zip", "plz", "birth", "iban", "tracking", "token",
    "secret", "passw", "cookie", "credential", "contact", "consignee", "recipient", "salary", "payroll",
)
STRUCTURAL_KEY = re.compile(r"[A-Za-z_][A-Za-z0-9_-]{0,40}")

BUILTIN_PRESETS: dict[str, dict[str, Any]] = {
    "bitergo-respond-shipment": {
        "description": "Bitergo RESPOND-SHIPMENT file: status, package, flags, items, presence of tracking/conformity.",
        "show": [
            "RespondShipment.RespondShipmentDataArea.Shipment.ShipmentHeader.Status.Code",
            "RespondShipment.RespondShipmentDataArea.Shipment.ShipmentHeader.AlternateDocumentID"
            "[ID.schemeID=DISPLAY_IDENTIFIER].ID.value",
            "RespondShipment.RespondShipmentDataArea.Shipment.ShipmentHeader.AlternateDocumentID"
            "[ID.schemeID=parentShipmentDisplayId].ID.value",
            "RespondShipment.RespondShipmentDataArea.Shipment.ShipmentHeader.AlternateDocumentID"
            "[ID.schemeID=lastShipment].ID.value",
            "RespondShipment.RespondShipmentDataArea.Shipment.ShipmentItem.Item.ItemMasterReference.DisplayID.value",
            "RespondShipment.RespondShipmentDataArea.Shipment.ShipmentItem.OrderQuantity.value",
            "RespondShipment.RespondShipmentDataArea.Shipment.ShipmentItem.ShippedQuantity.value",
            "RespondShipment.RespondShipmentDataArea.Shipment.ShipmentItem.Status.Code",
        ],
        "present": [
            "RespondShipment.RespondShipmentDataArea.Shipment.ShipmentUnit.ShipmentUnitContainer."
            "AlternateDocumentID[ID.schemeID=TRACKING_ID].ID.value",
            "RespondShipment.RespondShipmentDataArea.Shipment.ShipmentUnit.ShipmentUnitContainer."
            "LoadSupport.ConformityId",
        ],
    },
}

Step = tuple[Any, ...]  # ("key", name) | ("each",) | ("index", n) | ("where", [keys], value)


class PathError(ValueError):
    """The path expression could not be parsed."""


class DeniedKey(Exception):
    """A key in the path looks personal and is never printed."""


class Deny:
    """Decides whether a key looks personal. ``search`` mirrors ``re.Pattern.search`` for the walker."""

    def __init__(self, extra: str | None = None) -> None:
        self.extra = re.compile(extra, re.IGNORECASE) if extra else None

    def search(self, key: str) -> bool:
        """True if the key looks personal."""
        words = [w.lower() for w in re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])|\d+", key)]
        if any(word in DENY_WORDS for word in words):
            return True
        if any(first in words and second in words for first, second in DENY_PAIRS):
            return True
        squashed = re.sub(r"[^a-z0-9]", "", key.lower())
        if any(stem in squashed for stem in DENY_STEMS):
            return True
        return bool(self.extra and self.extra.search(key))


# ---------------------------------------------------------------------------
# Text safety
# ---------------------------------------------------------------------------


def safe_text(value: Any, *, clip: bool = True) -> str:
    """Render a value on one line with control characters escaped, clipped to MAX_VALUE_CHARS unless clip=False."""
    text = json.dumps(value, ensure_ascii=False)
    if isinstance(value, str):
        text = text[1:-1]  # drop the surrounding quotes; json.dumps already escaped \n, ESC and quotes
    if clip and len(text) > MAX_VALUE_CHARS:
        return f"{text[:MAX_VALUE_CHARS]}...(len {len(text)})"
    return text


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------


def _split_top_level(path: str) -> list[str]:
    """Split on dots that are not inside square brackets."""
    parts: list[str] = []
    depth = 0
    current: list[str] = []
    for char in path:
        if char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth < 0:
                raise PathError("unbalanced brackets in path")
        if char == "." and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(char)
    if depth != 0:
        raise PathError("unbalanced brackets in path")
    parts.append("".join(current))
    return parts


def parse_path(path: str) -> list[Step]:
    """Turn ``a.b[x=1].c`` into a list of steps. A single leading dot is allowed."""
    text = path.strip()
    text = text[1:] if text.startswith(".") else text
    segments = _split_top_level(text)
    if any(segment == "" for segment in segments) and text:
        raise PathError("empty segment in path")
    steps: list[Step] = []
    for segment in segments:
        match = re.fullmatch(r"([^\[\]]*)((?:\[[^\[\]]*\])*)", segment)
        if not match:
            raise PathError("cannot parse a segment of the path")
        name, brackets = match.groups()
        if name:
            steps.append(("key", name))
        for inner in re.findall(r"\[([^\[\]]*)\]", brackets):
            if inner == "":
                steps.append(("each",))
            elif inner.isascii() and inner.isdigit():
                steps.append(("index", int(inner)))
            elif "=" in inner:
                left, _, value = inner.partition("=")
                keys = left.strip().split(".")
                if not all(keys):
                    raise PathError("empty key in a [key=value] filter")
                steps.append(("where", keys, value.strip()))
            else:
                raise PathError("unsupported bracket expression in path")
    return steps


def _scalar_text(value: Any) -> str | None:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None or isinstance(value, (dict, list)):
        return None
    return str(value)


def _dig(node: Any, keys: list[str]) -> Any:
    for key in keys:
        if isinstance(node, dict) and key in node:
            node = node[key]
        else:
            return None
    return node


def walk(
    node: Any,
    steps: list[Step],
    trail: str,
    deny: Deny | None,
    deny_filter: Deny | None = None,
) -> Iterator[tuple[str, Any]]:
    """Yield (concrete path, value) for every match of the steps below *node*.

    ``deny`` is checked on key steps; ``deny_filter`` on the left-hand keys of ``[key=value]`` filters,
    which would otherwise let a caller test guesses against a personal field.
    """
    if not steps:
        yield trail, node
        return
    step, rest = steps[0], steps[1:]
    kind = step[0]
    if kind == "key":
        name = step[1]
        if deny is not None and deny.search(name):
            raise DeniedKey(name)
        child_trail = f"{trail}.{name}" if trail else name
        if isinstance(node, dict):
            if name in node:
                yield from walk(node[name], rest, child_trail, deny, deny_filter)
        elif isinstance(node, list):  # implicit map over lists
            for index, item in enumerate(node):
                yield from walk(item, steps, f"{trail}[{index}]", deny, deny_filter)
    elif kind == "each":
        if isinstance(node, list):
            for index, item in enumerate(node):
                yield from walk(item, rest, f"{trail}[{index}]", deny, deny_filter)
    elif kind == "index":
        if isinstance(node, list) and step[1] < len(node):
            yield from walk(node[step[1]], rest, f"{trail}[{step[1]}]", deny, deny_filter)
    elif kind == "where":
        if deny_filter is not None:
            for key in step[1]:
                if deny_filter.search(key):
                    raise DeniedKey(key)
        if isinstance(node, list):
            for index, item in enumerate(node):
                if _scalar_text(_dig(item, step[1])) == step[2]:
                    label = f"{trail}[{index}:{'.'.join(step[1])}={step[2]}]"
                    yield from walk(item, rest, label, deny, deny_filter)


# ---------------------------------------------------------------------------
# Modes
# ---------------------------------------------------------------------------


def collect_show(data: Any, paths: list[str], deny: Deny) -> tuple[dict[str, str], list[str]]:
    """Return ({concrete path: value text}, [notes about what was withheld])."""
    shown: dict[str, str] = {}
    notes: list[str] = []
    for path in paths:
        label = safe_text(path, clip=False)
        try:
            matches = list(walk(data, parse_path(path), "", deny, deny))
        except DeniedKey as exc:
            notes.append(f"withheld {label!r}: key {safe_text(str(exc))!r} looks personal")
            continue
        if not matches:
            notes.append(f"no match for {label!r}")
        for trail, value in matches:
            if isinstance(value, (dict, list)):
                notes.append(f"{safe_text(trail or path, clip=False)!r} is a container; name a leaf path instead")
            else:
                shown[trail] = safe_text(value)
    return shown, notes


def collect_present(data: Any, paths: list[str], deny: Deny | None = None) -> tuple[dict[str, bool], list[str]]:
    """Return ({path: True/False}, notes): a non-empty value anywhere under the path. Never the value.

    Key steps may be personal-looking (that is the point: "is there a tracking number?"), but a
    ``[key=value]`` filter on a personal-looking key is refused.
    """
    result: dict[str, bool] = {}
    notes: list[str] = []
    deny_filter = deny or Deny()
    for path in paths:
        try:
            matches = list(walk(data, parse_path(path), "", None, deny_filter))
        except DeniedKey as exc:
            notes.append(f"withheld {safe_text(path, clip=False)!r}: filter key {safe_text(str(exc))!r} looks personal")
            continue
        result[path] = any(value not in (None, "", [], {}) for _, value in matches)
    return result, notes


def shape(data: Any, deny: Deny) -> list[dict[str, Any]]:
    """Describe paths, types, counts and string lengths. Contains no values.

    Dict keys that look like data are collapsed to ``{key}``.
    """
    stats: dict[str, dict[str, Any]] = {}

    def entry(path: str, personal: bool) -> dict[str, Any]:
        return stats.setdefault(
            path,
            {"path": path, "seen": 0, "types": set(), "min": None, "max": None, "personal": personal},
        )

    def structural(key: str, sibling_count: int) -> bool:
        return (
            sibling_count <= MAX_SHAPE_KEYS
            and STRUCTURAL_KEY.fullmatch(key) is not None
            and sum(char.isdigit() for char in key) <= 2
        )

    def visit(node: Any, path: str, personal: bool) -> None:
        item = entry(path or "$", personal)
        item["seen"] += 1
        if isinstance(node, dict):
            item["types"].add("object")
            for key, child in node.items():
                label = key if structural(key, len(node)) else "{key}"
                visit(child, f"{path}.{label}" if path else label, label != "{key}" and deny.search(key))
        elif isinstance(node, list):
            item["types"].add("list")
            for child in node:
                visit(child, f"{path}[]", personal)
        else:
            item["types"].add("null" if node is None else type(node).__name__)
            if isinstance(node, str):
                item["min"] = len(node) if item["min"] is None else min(item["min"], len(node))
                item["max"] = len(node) if item["max"] is None else max(item["max"], len(node))

    visit(data, "", False)
    return [
        {
            "path": item["path"],
            "seen": item["seen"],
            "types": sorted(item["types"]),
            "length": None if item["min"] is None else [item["min"], item["max"]],
            "personal_key": item["personal"],
        }
        for item in stats.values()
    ]


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def _group(shown: dict[str, str]) -> list[tuple[str, list[tuple[str, str]]]]:
    """Group results by their last list index so one list item prints on one line."""
    groups: dict[str, list[tuple[str, str]]] = {}
    for trail, value in shown.items():
        cut = trail.rfind("]")
        prefix = trail[: cut + 1] if cut != -1 else ""
        suffix = trail[cut + 1 :].lstrip(".") if cut != -1 else trail
        groups.setdefault(prefix, []).append((suffix, value))
    return list(groups.items())


def render_show(shown: dict[str, str], present: dict[str, bool], notes: list[str]) -> str:
    """Render shown values, presence flags and notes as plain text."""
    lines: list[str] = []
    for prefix, items in _group(shown):
        if prefix:
            body = "  ".join(f"{suffix}={value}" if suffix else value for suffix, value in items)
            lines.append(f"{prefix}: {body}")
        else:
            lines.extend(f"{suffix} = {value}" for suffix, value in items)
    lines.extend(f"present {safe_text(path, clip=False)}: {flag}" for path, flag in present.items())
    lines.extend(f"note: {note}" for note in notes)
    return "\n".join(lines)


def render_shape(rows: list[dict[str, Any]]) -> str:
    """Render the shape rows as plain text."""
    lines = ["shape only, no values shown (use --show PATH to see a value)"]
    for row in rows:
        extra = f"  len {row['length'][0]}-{row['length'][1]}" if row["length"] else ""
        flag = "  [personal-looking key: values never shown]" if row["personal_key"] else ""
        lines.append(f"{row['path']}  {'|'.join(row['types'])}  x{row['seen']}{extra}{flag}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _valid_preset(preset: Any) -> bool:
    return isinstance(preset, dict) and all(
        isinstance(preset.get(field, []), list) and all(isinstance(p, str) for p in preset.get(field, []))
        for field in ("show", "present")
    )


def load_presets() -> dict[str, dict[str, Any]]:
    """Built-in presets plus ``*.toml`` files in ~/.config/rogkit/jqsafe (a user file overrides a built-in)."""
    presets = dict(BUILTIN_PRESETS)
    if USER_PRESET_DIR.is_dir():
        for file in sorted(USER_PRESET_DIR.glob("*.toml")):
            loaded = tomllib.loads(file.read_text(encoding="utf-8"))
            if not _valid_preset(loaded):
                raise ValueError(f"preset {file.name} must have 'show' and 'present' as lists of strings")
            presets[file.stem] = loaded
    return presets


def load_json(source: str | None) -> Any:
    """Load JSON from a file (relative to the invoking directory) or stdin."""
    if source and source != "-":
        path = Path(source)
        path = path if path.is_absolute() else get_invoking_cwd() / path
        return json.loads(path.read_text(encoding="utf-8"))
    return json.load(sys.stdin)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Look inside JSON without printing values you did not ask for.",
        epilog="No options = shape only. Values appear only for paths you name. Personal-looking keys never do.",
    )
    parser.add_argument("file", nargs="?", help="JSON file, or - for stdin")
    parser.add_argument("--show", action="append", default=[], metavar="PATH", help="print values at this path")
    parser.add_argument("--present", action="append", default=[], metavar="PATH", help="print only True/False")
    parser.add_argument("--preset", metavar="NAME", help="use a saved set of --show/--present paths")
    parser.add_argument("--deny", metavar="REGEX", help="extra key pattern that must never be printed")
    parser.add_argument("--list-presets", action="store_true", help="list available presets and exit")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("-q", "--plain", action="store_true", help="accepted for consistency; output is always plain")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns 0 on success, 1 for unreadable input, 2 for bad arguments."""
    args = parse_args(argv)
    try:
        presets = load_presets()
        deny = Deny(args.deny)
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError, ValueError, re.error) as exc:
        print(f"error: {type(exc).__name__}: could not load presets or --deny pattern", file=sys.stderr)
        return 2
    if args.list_presets:
        for name, preset in sorted(presets.items()):
            print(f"{name}: {preset.get('description', '')}")
        return 0
    if not args.file and sys.stdin.isatty():
        print("error: give a JSON file, or - to read stdin (see --help)", file=sys.stderr)
        return 2

    show, present = list(args.show), list(args.present)
    if args.preset:
        if args.preset not in presets:
            print("error: unknown preset; try --list-presets", file=sys.stderr)
            return 2
        show += presets[args.preset].get("show", [])
        present += presets[args.preset].get("present", [])

    try:
        data = load_json(args.file)
    except FileNotFoundError:
        print("error: file not found", file=sys.stderr)
        return 1
    except (OSError, UnicodeDecodeError):
        print("error: file could not be read as UTF-8 text", file=sys.stderr)
        return 1
    except json.JSONDecodeError as exc:
        print(f"error: invalid JSON at line {exc.lineno} column {exc.colno}", file=sys.stderr)
        return 1

    try:
        if show or present:
            shown, notes = collect_show(data, show, deny)
            flags, present_notes = collect_present(data, present, deny)
            notes += present_notes
            if args.json:
                print(json.dumps({"shown": shown, "present": flags, "notes": notes}, ensure_ascii=False, indent=2))
            else:
                print(render_show(shown, flags, notes))
        else:
            rows = shape(data, deny)
            print(json.dumps(rows, indent=2) if args.json else render_shape(rows))
    except PathError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
