"""Shared secret-detection and value-classification helpers for env tools.

Used by both `envr` (OS environment) and `enver` (.env files) so they agree
on what counts as a secret key, what counts as a placeholder value, and how
to mask values when hiding them from output.
"""

from __future__ import annotations

import re
from typing import Literal

ValueClass = Literal["set", "empty", "placeholder"]


# Keys whose VALUE typically holds a secret, identified by name patterns.
_SECRET_KEY_PATTERN = re.compile(
    r"(?:^|_)("
    r"SECRET|PASSWORD|PASSWD|PWD|"
    r"TOKEN|"
    r"APIKEY|API_KEY|"
    r"PRIVATEKEY|PRIVATE_KEY|"
    r"CREDENTIAL|CREDENTIALS|"
    r"ACCESS_KEY|SESSION_TOKEN|"
    r"AUTH_TOKEN|BEARER"
    r")(?:$|_)",
    re.IGNORECASE,
)

# Specific keys whose values commonly contain embedded credentials.
_SECRET_KEY_NAMES = frozenset(
    {
        "DATABASE_URL",
        "DB_URL",
        "MONGO_URL",
        "MONGODB_URL",
        "MONGODB_URI",
        "REDIS_URL",
        "POSTGRES_URL",
        "POSTGRESQL_URL",
        "MYSQL_URL",
        "DSN",
        "SENTRY_DSN",
        "JWT_SECRET",
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
    }
)

# Common placeholder words found in template .env files.
_PLACEHOLDER_WORDS = re.compile(
    r"^("
    r"x{2,}|"
    r"your[-_ ]?[a-z0-9_-]*|"
    r"change[-_ ]?me|"
    r"todo|fixme|"
    r"replace[-_ ]?(me|this)?|"
    r"placeholder|example|sample|"
    r"secret[-_ ]?here|"
    r"insert[-_ ]?[a-z0-9_-]*|"
    r"my[-_ ]?(secret|password|key|token)"
    r")$",
    re.IGNORECASE,
)

_NULLISH_VALUES = frozenset({"null", "none", "nil", "undefined", "~"})

_MASK = "********"


def is_secret_key(key: str) -> bool:
    """Return True if the key name suggests it holds a secret value."""
    upper = key.upper()
    if upper in _SECRET_KEY_NAMES:
        return True
    if upper.endswith("_KEY") or upper == "KEY":
        return True
    return bool(_SECRET_KEY_PATTERN.search(upper))


def classify_value(value: str) -> ValueClass:
    """Classify a value as set, empty, or placeholder.

    Empty string and nullish words → empty.
    `<...>` wrapping, common stub words, `xxx`, `changeme`, etc. → placeholder.
    Anything else → set.
    """
    if value == "":
        return "empty"
    if value.lower() in _NULLISH_VALUES:
        return "placeholder"
    if value.startswith("<") and value.endswith(">"):
        return "placeholder"
    if _PLACEHOLDER_WORDS.match(value):
        return "placeholder"
    return "set"


def mask(value: str) -> str:
    """Return a fixed-width mask for a secret value (empty stays empty)."""
    return _MASK if value else ""
