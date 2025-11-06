"""Shared path utilities for the rogkit package."""

from __future__ import annotations

import os
from pathlib import Path


_PACKAGE_DIR = Path(__file__).resolve().parent

# Backwards-compatible string paths (legacy callers still expect str)
script_dir = str(_PACKAGE_DIR)
root_dir = str(_PACKAGE_DIR.parent)
toml_sample_path = os.path.join(root_dir, 'rogkit_sample.toml')

# Top-level data directory (legacy use)
data_dir = os.path.join(root_dir, 'data')

# Package-scoped data directory used by newer tooling
package_data_dir = _PACKAGE_DIR / 'data'


def ensure_package_data_dir() -> Path:
    """Ensure the package data directory exists and return it."""
    package_data_dir.mkdir(parents=True, exist_ok=True)
    return package_data_dir