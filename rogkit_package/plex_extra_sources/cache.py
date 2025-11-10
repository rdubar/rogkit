"""Helpers for reading and writing additional media caches for Plex."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from rogkit_package.bin.plex_db_cache import CACHE_DIR, CACHE_SQLITE_PATH, write_cache_pickle as _write_pickle


EXTRAS_CACHE_PATH = CACHE_DIR / "extras_tmdb.json"


def ensure_cache_table(db_path: Optional[Path] = None) -> Path:
    """Ensure the Plex SQLite cache exists and return its path."""

    cache_path = db_path or CACHE_SQLITE_PATH
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    return cache_path


def write_cache_pickle() -> None:
    """Rebuild the Plex cache pickle by delegating to the main cache module."""

    _write_pickle()


def write_extras_cache(records: List[Dict[str, Any]], path: Optional[Path] = None) -> Path:
    """Write a list of extra media records to JSON and return the path."""

    cache_path = path or EXTRAS_CACHE_PATH
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with cache_path.open("w", encoding="utf-8") as fh:
        json.dump(records, fh, ensure_ascii=False, indent=2)
    return cache_path


def load_extras_cache(path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Load extra media records from JSON if available."""

    cache_path = path or EXTRAS_CACHE_PATH
    if not cache_path.exists():
        return []
    with cache_path.open("r", encoding="utf-8") as fh:
        return json.load(fh)
