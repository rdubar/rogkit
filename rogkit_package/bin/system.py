"""
Enhanced system snapshot utility.

Displays Python runtime details, OS info, and architecture summary with a
colorful, human-friendly layout.
"""
from __future__ import annotations

import os
import platform
import subprocess
import sys

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text

    console = Console()
    RICH_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    console = None
    RICH_AVAILABLE = False


def _python_info() -> dict[str, str]:
    version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    executable = sys.executable
    implementation = platform.python_implementation()
    compiler = platform.python_compiler()
    return {
        "Version": version,
        "Implementation": implementation,
        "Executable": executable,
        "Compiler": compiler,
    }


def _arch_info() -> dict[str, str]:
    platform_architecture = platform.architecture()

    process = subprocess.Popen(["arch"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, _ = process.communicate()
    architecture = stdout.strip().decode("utf-8") if isinstance(stdout, bytes) else stdout.strip()

    friendly_arch_map = {
        "i386": "Intel 32-bit (likely Rosetta)",
        "x86_64": "Intel 64-bit",
        "arm64": "Apple Silicon (ARM64)",
    }
    friendly_arch = friendly_arch_map.get(architecture, "Unknown Architecture")

    return {
        "Python Arch": f"{platform_architecture[0]} ({platform_architecture[1]})",
        "System Arch": architecture,
        "Friendly": friendly_arch,
        "Rosetta": "yes" if _is_rosetta() else "no",
    }


def _os_info() -> dict[str, str]:
    return {
        "Platform": sys.platform,
        "OS": f"{platform.system()} {platform.release()}",
        "Version": platform.version(),
        "Machine": platform.machine(),
    }


def _shell_info() -> dict[str, str]:
    shell = os.environ.get("SHELL", "unknown")
    rosetta = "yes" if _is_rosetta() else "no"
    env = os.environ.get("VIRTUAL_ENV") or os.environ.get("CONDA_PREFIX") or "system interpreter"
    if env != "system interpreter":
        env = os.path.relpath(env, os.getcwd()) if env.startswith(os.getcwd()) else env
    return {
        "Shell": shell,
        "Running under Rosetta": rosetta,
        "Python env": env,
    }


def _is_rosetta() -> bool:
    if platform.system() != "Darwin":
        return False
    try:
        result = subprocess.run(
            ["sysctl", "-in", "sysctl.proc_translated"],
            capture_output=True,
            text=True,
            check=False,
        )
        return result.stdout.strip() == "1"
    except Exception:
        return False


def render_report() -> None:
    if not RICH_AVAILABLE:
        print("Roger's Python System Report")
        print("----------------------------")
        sections = [
            ("Python", _python_info()),
            ("Operating System", _os_info()),
            ("Architecture", _arch_info()),
        ]
        for title, data in sections:
            print(f"\n[{title}]")
            for key, value in data.items():
                print(f"{key}: {value}")
        return

    header = Text("Roger's Python System Report", style="bold cyan")
    console.print(Panel(header, border_style="cyan", padding=(1, 2)))

    sections = [
        ("Python", _python_info()),
        ("Operating System", _os_info()),
        ("Shell & Environment", _shell_info()),
        ("Architecture", _arch_info()),
    ]

    for title, data in sections:
        table = Table(show_header=False, box=None, pad_edge=False)
        table.add_column(justify="right", style="bold magenta")
        table.add_column(style="white")
        for key, value in data.items():
            table.add_row(f"{key}:", value)
        console.print(Panel(table, title=title, border_style="blue", padding=(0, 1)))


def main() -> None:
    render_report()


if __name__ == "__main__":
    main()
