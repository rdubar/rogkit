"""Media tooling suite built around the daemon-backed Plex database cache."""

from importlib import import_module
from types import ModuleType
from typing import Any

__all__ = ["main", "main_timer", "run_daemon"]


def __getattr__(name: str) -> Any:
    if name in __all__:
        module: ModuleType = import_module("rogkit_package.media.media")
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(list(globals().keys()) + __all__))
