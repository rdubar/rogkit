"""
Open Interpreter integration for rogkit (temporarily suspended).

The upstream project currently depends on `tiktoken`, which lacks CPython 3.14
wheels. Rather than blocking the overall upgrade we pause this CLI until the
dependency is published.
"""
from __future__ import annotations

from textwrap import dedent
from typing import NoReturn

# TODO(tiktoken): Re-enable Open Interpreter once tiktoken publishes CPython 3.14 wheels.

SUSPENDED_MESSAGE = dedent(
    """
    🚫 Open Interpreter CLI temporarily suspended

    - Reason: `tiktoken` (a transitive Open Interpreter dependency) does not yet
      provide Python 3.14 wheels, so the package fails to install.
    - Impact: the `inter` command no longer launches Open Interpreter.
    - Workaround: use a Python 3.12 virtualenv and an older rogkit revision if
      you absolutely need this integration.

    Track upstream progress and revert this stub when tiktoken supports CPython 3.14.
    """
).strip()


def main() -> NoReturn:
    """Inform the user about the suspended feature and exit."""
    print(SUSPENDED_MESSAGE)
    raise SystemExit(1)


if __name__ == "__main__":
    main()
