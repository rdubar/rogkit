#!/usr/bin/env python3
"""See what is keeping this machine awake, and manage our own labelled keep-awake holds.

macOS uses ``pmset`` and ``caffeinate``. Linux uses systemd-logind (``busctl``/``systemd-inhibit``).

There is no daemon. Each hold we create is one ``caffeinate``/``systemd-inhibit`` process in its own
session, so it survives an SSH disconnect. A small JSON state file records it, and state files whose
process has gone are pruned on every call. System assertions are read live at query time.

``awake off`` only ever stops processes we started. It never puts the machine to sleep and never touches
other apps' assertions.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import secrets
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from ..settings import get_invoking_cwd

try:  # optional rich formatting
    from rich.console import Console
    from rich.table import Table
    from rich.text import Text

    console = Console()
    RICH_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover
    console = None  # type: ignore[assignment]
    RICH_AVAILABLE = False


STATE_DIR = Path.home() / ".local" / "state" / "rogkit" / "awake"
IS_MAC = platform.system() == "Darwin"
HOLDER_NAMES = {"caffeinate", "systemd-inhibit"}

# What each macOS assertion type does. Wording follows caffeinate(8)/pmset(1); no lid claims beyond them.
MAC_TYPE_EFFECT: dict[str, str] = {
    "PreventUserIdleSystemSleep": "blocks idle system sleep",
    "PreventSystemSleep": "blocks system sleep (AC power only)",
    "PreventUserIdleDisplaySleep": "keeps display on (and so the system)",
    "UserIsActive": "user activity, short-lived",
    "NetworkClientActive": "network client, background",
    "BackgroundTask": "background task",
    "ApplePushServiceTask": "push service, background",
    "SoftwareUpdateTask": "software update, background",
    "ExternalMedia": "external media mounted",
}
MAC_BLOCKING_TYPES = {
    "PreventUserIdleSystemSleep",
    "PreventSystemSleep",
    "PreventUserIdleDisplaySleep",
}


def _print_message(message: str, *, style: str | None = None) -> None:
    """Print with optional rich styling, fallback to plain print."""
    if RICH_AVAILABLE:
        console.print(Text(message, style=style) if style else message)
    else:
        print(message)


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------


@dataclass
class Hold:
    """A keep-awake hold created by this tool."""

    id: str
    label: str
    pid: int
    started: float
    expires: float | None = None
    while_pid: int | None = None
    display: bool = False
    command: str | None = None  # set for ``awake run``
    host: str = field(default_factory=platform.node)


@dataclass
class Assertion:
    """A sleep assertion/inhibitor reported by the OS."""

    pid: int
    process: str
    kind: str
    name: str
    age: str = ""
    details: list[str] = field(default_factory=list)
    blocking: bool = True
    ours: str | None = None  # hold id when this is one of ours
    note: str = ""


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


_DURATION_RE = re.compile(r"(\d+)\s*([dhms])")


def parse_duration(text: str) -> int:
    """Parse ``90``, ``45m``, ``2h``, ``1h30m`` or ``1d`` into seconds."""
    text = text.strip().lower()
    if text.isdigit():
        return int(text)
    parts = _DURATION_RE.findall(text)
    if not parts or _DURATION_RE.sub("", text).strip():
        raise argparse.ArgumentTypeError(f"bad duration {text!r} (try 30m, 2h, 1h30m)")
    mult = {"d": 86400, "h": 3600, "m": 60, "s": 1}
    return sum(int(n) * mult[u] for n, u in parts)


def fmt_seconds(seconds: float) -> str:
    """Format seconds compactly, e.g. ``1h05m`` or ``42s``."""
    seconds = int(max(seconds, 0))
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    mins, secs = divmod(rem, 60)
    if days:
        return f"{days}d{hours:02d}h"
    if hours:
        return f"{hours}h{mins:02d}m"
    if mins:
        return f"{mins}m{secs:02d}s"
    return f"{secs}s"


def _run(cmd: list[str]) -> str:
    """Run a command and return stdout, or empty string if it is missing or fails."""
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=10).stdout
    except OSError, subprocess.SubprocessError:
        return ""


def pid_alive(pid: int) -> bool:
    """Return True if a process with this PID exists."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def proc_comm(pid: int) -> str:
    """Return the short process name for a PID, or ''."""
    return Path(_run(["ps", "-o", "comm=", "-p", str(pid)]).strip()).name


def proc_parent(pid: int) -> str:
    """Return ``ppid command`` of a process's parent, for showing who launched an external holder."""
    ppid = _run(["ps", "-o", "ppid=", "-p", str(pid)]).strip()
    if not ppid or ppid in {"0", "1"}:
        return f"parent pid {ppid or '?'} (launchd/init: detached)" if ppid else ""
    cmd = _run(["ps", "-o", "command=", "-p", ppid]).strip()
    return f"launched by pid {ppid}: {cmd[:80]}" if cmd else f"launched by pid {ppid}"


def in_remote_session() -> bool:
    """Return True if this shell came in over SSH."""
    return bool(os.environ.get("SSH_CONNECTION") or os.environ.get("SSH_TTY"))


# ---------------------------------------------------------------------------
# Our holds (state files)
# ---------------------------------------------------------------------------


def _state_path(hold_id: str) -> Path:
    return STATE_DIR / f"{hold_id}.json"


def save_hold(hold: Hold) -> None:
    """Write a hold's state file."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    _state_path(hold.id).write_text(json.dumps(asdict(hold), indent=2))


def remove_hold(hold_id: str) -> None:
    """Delete a hold's state file if present."""
    _state_path(hold_id).unlink(missing_ok=True)


def is_our_holder(pid: int) -> bool:
    """True if PID is alive and still a caffeinate/systemd-inhibit (guards against PID reuse)."""
    return pid_alive(pid) and proc_comm(pid) in HOLDER_NAMES


def load_holds() -> list[Hold]:
    """Load live holds, pruning state files whose holder process has gone."""
    holds: list[Hold] = []
    if not STATE_DIR.is_dir():
        return holds
    for path in sorted(STATE_DIR.glob("*.json")):
        try:
            hold = Hold(**json.loads(path.read_text()))
        except ValueError, TypeError:
            path.unlink(missing_ok=True)
            continue
        if is_our_holder(hold.pid):
            holds.append(hold)
        else:
            path.unlink(missing_ok=True)
    return sorted(holds, key=lambda h: h.started)


def _holder_argv(
    label: str, *, seconds: int | None, while_pid: int | None, display: bool
) -> list[str]:
    """Build the command for a holder process on this OS."""
    if IS_MAC:
        argv = ["caffeinate", "-i", "-s"] + (["-d"] if display else [])
        if seconds:
            argv += ["-t", str(seconds)]
        if while_pid:
            argv += ["-w", str(while_pid)]
        return argv
    if not shutil.which("systemd-inhibit"):
        raise SystemExit(
            "awake: systemd-inhibit not found; only systemd Linux is supported"
        )
    if while_pid:
        waiter = ["tail", f"--pid={while_pid}", "-f", "/dev/null"]
    elif seconds:
        waiter = ["sleep", str(seconds)]
    else:
        waiter = ["sleep", "infinity"]
    return [
        "systemd-inhibit",
        "--what=idle:sleep",
        "--who=rogkit awake",
        f"--why={label}",
        "--mode=block",
        *waiter,
    ]


def start_hold(
    label: str,
    *,
    seconds: int | None = None,
    while_pid: int | None = None,
    display: bool = False,
    command: str | None = None,
) -> Hold:
    """Start a detached holder process and record it."""
    hold_id = secrets.token_hex(2)
    argv = _holder_argv(label, seconds=seconds, while_pid=while_pid, display=display)
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    err_path = STATE_DIR / f"{hold_id}.err"
    with err_path.open("w") as err:
        proc = subprocess.Popen(
            argv,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=err,
            start_new_session=True,  # survives SSH disconnect / terminal close
        )
    time.sleep(0.3)
    if proc.poll() is not None:
        msg = err_path.read_text().strip() or f"exit code {proc.returncode}"
        err_path.unlink(missing_ok=True)
        raise SystemExit(f"awake: holder failed to start: {msg}")
    err_path.unlink(missing_ok=True)
    now = time.time()
    hold = Hold(
        id=hold_id,
        label=label,
        pid=proc.pid,
        started=now,
        expires=now + seconds if seconds else None,
        while_pid=while_pid,
        display=display,
        command=command,
    )
    save_hold(hold)
    return hold


def stop_hold(hold: Hold) -> bool:
    """Stop one of our holds. Returns True if a process was signalled."""
    signalled = False
    if is_our_holder(hold.pid):
        try:
            os.kill(hold.pid, signal.SIGTERM)
            signalled = True
        except ProcessLookupError:
            pass
    remove_hold(hold.id)
    return signalled


# ---------------------------------------------------------------------------
# System assertions
# ---------------------------------------------------------------------------


_MAC_LINE = re.compile(
    r"^\s*pid (\d+)\((.+?)\): \[[^\]]*\] (\S+(?: day[s]?)?(?: \S+)?) (\w+) named: \"(.*)\"\s*$"
)


def parse_pmset_assertions(text: str) -> list[Assertion]:
    """Parse the 'Listed by owning process' section of ``pmset -g assertions``."""
    result: list[Assertion] = []
    in_section = False
    current: Assertion | None = None
    for line in text.splitlines():
        if line.startswith("Listed by owning process"):
            in_section = True
            continue
        if not in_section:
            continue
        if line.startswith(("No kernel assertions", "Kernel Assertions")):
            break
        match = _MAC_LINE.match(line)
        if match:
            pid, proc, age, kind, name = match.groups()
            current = Assertion(
                pid=int(pid),
                process=proc,
                kind=kind,
                name=name,
                age=age,
                blocking=kind in MAC_BLOCKING_TYPES,
            )
            result.append(current)
        elif current and line.strip():
            current.details.append(line.strip())
    return result


def parse_logind_inhibitors(text: str) -> list[Assertion]:
    """Parse ``busctl --json=short call ... ListInhibitors`` output."""
    try:
        rows = json.loads(text)["data"][0]
    except ValueError, KeyError, IndexError, TypeError:
        return []
    result: list[Assertion] = []
    for what, who, why, mode, _uid, pid in rows:
        result.append(
            Assertion(
                pid=int(pid),
                process=who,
                kind=what,
                name=why,
                blocking=mode == "block"
                and any(w in what.split(":") for w in ("sleep", "idle")),
                details=[f"mode={mode}"],
            )
        )
    return result


def system_assertions() -> list[Assertion]:
    """Return every sleep assertion/inhibitor the OS reports right now."""
    if IS_MAC:
        return parse_pmset_assertions(_run(["pmset", "-g", "assertions"]))
    out = _run(
        [
            "busctl",
            "--json=short",
            "call",
            "org.freedesktop.login1",
            "/org/freedesktop/login1",
            "org.freedesktop.login1.Manager",
            "ListInhibitors",
        ]
    )
    return parse_logind_inhibitors(out)


def annotate(assertions: list[Assertion], holds: list[Hold]) -> None:
    """Mark ours, explain remote-session and external caffeinate assertions."""
    by_pid = {h.pid: h for h in holds}
    for a in assertions:
        # On Linux systemd-inhibit's PID is the inhibitor's pid; on macOS it is caffeinate's.
        if a.pid in by_pid:
            a.ours = by_pid[a.pid].id
            continue
        low = f"{a.name} {' '.join(a.details)}".lower()
        if "tty" in low or a.process in {"sshd", "sshd-session"}:
            a.note = "terminal/SSH session: held while that session is connected"
        elif a.process in HOLDER_NAMES or "caffeinate" in low:
            a.note = proc_parent(a.pid)
        elif a.process == "powerd" and "display is on" in low:
            a.note = "display is on; goes away when the display sleeps"


# ---------------------------------------------------------------------------
# Power / lid
# ---------------------------------------------------------------------------


def mac_power() -> tuple[str, bool]:
    """Return (power source, has internal battery) on macOS."""
    out = _run(["pmset", "-g", "batt"])
    source = (
        "AC Power"
        if "'AC Power'" in out
        else ("Battery Power" if "'Battery Power'" in out else "unknown")
    )
    return source, "InternalBattery" in out


def lid_warnings() -> list[str]:
    """Lid/power caveats, limited to what caffeinate(8) documents."""
    if not IS_MAC:
        return []
    source, laptop = mac_power()
    if not laptop:
        return []
    if source == "Battery Power":
        return [
            "On battery: PreventSystemSleep (caffeinate -s) is ignored, per caffeinate(8). "
            "Closing the lid will sleep this Mac whatever is listed here."
        ]
    return [
        "On AC power: holds use caffeinate -s, documented as 'prevent the system from sleeping' on AC. "
        "Closing the lid is not specifically documented; test it before relying on it."
    ]


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _hold_rows(holds: list[Hold]) -> list[tuple[str, str, str, str, str]]:
    now = time.time()
    rows = []
    for h in holds:
        if h.expires:
            left = f"{fmt_seconds(h.expires - now)} left"
        elif h.while_pid:
            left = f"while pid {h.while_pid}"
        elif h.command:
            left = f"while: {h.command[:40]}"
        else:
            left = "until awake off"
        started = datetime.fromtimestamp(h.started).strftime("%H:%M")
        label = h.label + (" +display" if h.display else "")
        rows.append(
            (
                h.id,
                label,
                str(h.pid),
                f"{started} ({fmt_seconds(now - h.started)})",
                left,
            )
        )
    return rows


def render_holds(holds: list[Hold]) -> None:
    """Print our holds."""
    if not holds:
        _print_message("Our holds: none", style="dim")
        return
    rows = _hold_rows(holds)
    if RICH_AVAILABLE:
        table = Table(
            title="Our holds (awake)", title_justify="left", header_style="bold cyan"
        )
        for col in ("id", "label", "pid", "started", "ends"):
            table.add_column(col)
        for row in rows:
            table.add_row(*row)
        console.print(table)
    else:
        print("Our holds (awake):")
        for row in rows:
            print("  " + "  ".join(row))


def render_assertions(assertions: list[Assertion], *, show_all: bool) -> None:
    """Print external assertions (ours are shown in the holds table)."""
    external = [a for a in assertions if not a.ours and (show_all or a.blocking)]
    hidden = sum(
        1 for a in assertions if not a.ours and not a.blocking and not show_all
    )
    title = "Other assertions" if show_all else "Other things keeping it awake"
    if not external:
        _print_message(
            f"{title}: none" + (f" ({hidden} background, see --all)" if hidden else ""),
            style="dim",
        )
        return
    if RICH_AVAILABLE:
        table = Table(title=title, title_justify="left", header_style="bold cyan")
        for col in ("pid", "process", "age", "type", "name / note"):
            table.add_column(col, overflow="fold")
        for a in external:
            effect = MAC_TYPE_EFFECT.get(a.kind, a.kind) if IS_MAC else a.kind
            detail = a.name + (f"\n[dim]{a.note}[/dim]" if a.note else "")
            style = None if a.blocking else "dim"
            table.add_row(str(a.pid), a.process, a.age, effect, detail, style=style)
        console.print(table)
    else:
        print(f"{title}:")
        for a in external:
            print(
                f"  {a.pid:>6} {a.process:<16} {a.age:>9} {a.kind}  {a.name}"
                + (f"  [{a.note}]" if a.note else "")
            )
    if hidden:
        _print_message(
            f"  ({hidden} background/short-lived assertions hidden, see --all)",
            style="dim",
        )


def render_status(
    holds: list[Hold], assertions: list[Assertion], *, show_all: bool
) -> None:
    """Full picture: our holds, other blockers, power and lid caveats."""
    render_holds(holds)
    render_assertions(assertions, show_all=show_all)
    if IS_MAC:
        source, _ = mac_power()
        _print_message(f"Power: {source}", style="dim")
    for warning in lid_warnings():
        _print_message(f"! {warning}", style="yellow")
    if in_remote_session():
        _print_message(
            "! You are in an SSH session. macOS keeps a tty assertion while a remote terminal is connected; "
            "it ends when you disconnect, so don't count on it once you log out.",
            style="yellow",
        )


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def _find_holds(holds: list[Hold], keys: list[str]) -> list[Hold]:
    picked = [h for h in holds if h.id in keys or h.label in keys]
    missing = [k for k in keys if not any(k in (h.id, h.label) for h in holds)]
    for key in missing:
        _print_message(f"No hold of ours matches {key!r}", style="yellow")
    return picked


def cmd_list(args: argparse.Namespace) -> int:
    holds = load_holds()
    assertions = system_assertions()
    annotate(assertions, holds)
    if args.json:
        print(
            json.dumps(
                {
                    "holds": [asdict(h) for h in holds],
                    "assertions": [asdict(a) for a in assertions],
                },
                indent=2,
            )
        )
        return 0
    if args.command == "status":
        render_status(holds, assertions, show_all=args.all)
    else:
        render_holds(holds)
        render_assertions(assertions, show_all=args.all)
    return 0


def cmd_on(args: argparse.Namespace) -> int:
    if args.for_ and args.while_pid:
        raise SystemExit("awake: use either --for or --while, not both (yet)")
    if args.while_pid and not pid_alive(args.while_pid):
        raise SystemExit(f"awake: pid {args.while_pid} is not running")
    hold = start_hold(
        args.label, seconds=args.for_, while_pid=args.while_pid, display=args.display
    )
    ends = (
        f"for {fmt_seconds(args.for_)}"
        if args.for_
        else (
            f"while pid {args.while_pid} runs"
            if args.while_pid
            else "until `awake off`"
        )
    )
    _print_message(
        f"Holding awake [{hold.id}] {hold.label!r} {ends} (pid {hold.pid}).",
        style="green",
    )
    for warning in lid_warnings():
        _print_message(f"! {warning}", style="yellow")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    argv = args.argv[1:] if args.argv[:1] == ["--"] else args.argv
    if not argv:
        raise SystemExit(
            "awake run: give a command, e.g. awake run --label sync -- rsync ..."
        )
    label = args.label or Path(argv[0]).name
    child = subprocess.Popen(argv, cwd=get_invoking_cwd())
    hold = start_hold(
        label, while_pid=child.pid, display=args.display, command=" ".join(argv)
    )
    _print_message(
        f"awake [{hold.id}] holding while {label!r} runs (pid {child.pid})", style="dim"
    )
    try:
        code = child.wait()
    except KeyboardInterrupt:
        code = child.wait()
    finally:
        stop_hold(hold)
    return code


def cmd_off(args: argparse.Namespace) -> int:
    holds = load_holds()
    if args.all:
        targets = holds
    elif args.keys:
        targets = _find_holds(holds, args.keys)
    else:
        raise SystemExit(
            "awake off: give hold ids/labels, or --all for all of OUR holds"
        )
    for hold in targets:
        stop_hold(hold)
        _print_message(f"Released [{hold.id}] {hold.label!r}", style="green")
    if not targets:
        _print_message("Nothing of ours to release.", style="dim")
    # Releasing our holds does not mean the machine will sleep: show what is left.
    _show_remaining()
    return 0


@dataclass
class Purgeable:
    """A caffeinate/systemd-inhibit process that `awake purge` may kill."""

    pid: int
    user: str
    command: str
    ppid: int
    parent: str
    children: list[str]
    ours: str | None = None

    @property
    def parent_alive(self) -> bool:
        return self.ppid > 1 and pid_alive(self.ppid)


def find_purgeable(holds: list[Hold]) -> list[Purgeable]:
    """Every caffeinate/systemd-inhibit process on the machine, with who launched it and what it wraps."""
    by_pid = {h.pid: h.id for h in holds}
    found: list[Purgeable] = []
    for name in sorted(HOLDER_NAMES):
        for pid_text in _run(["pgrep", "-x", name]).split():
            pid = int(pid_text)
            info = (
                _run(["ps", "-o", "user=,ppid=,command=", "-p", pid_text])
                .strip()
                .split(None, 2)
            )
            if len(info) < 3:
                continue
            user, ppid, command = info[0], int(info[1]), info[2]
            parent = (
                _run(["ps", "-o", "command=", "-p", str(ppid)]).strip()
                if ppid > 1
                else "(detached)"
            )
            children = [
                _run(["ps", "-o", "command=", "-p", c]).strip()
                for c in _run(["pgrep", "-P", pid_text]).split()
            ]
            found.append(
                Purgeable(
                    pid,
                    user,
                    command,
                    ppid,
                    parent,
                    [c for c in children if c],
                    by_pid.get(pid),
                )
            )
    return found


def _show_remaining() -> None:
    """After releasing holds, show whatever still keeps the machine awake."""
    assertions = system_assertions()
    remaining = load_holds()
    annotate(assertions, remaining)
    if remaining or any(a.blocking and not a.ours for a in assertions):
        _print_message("Still keeping it awake:", style="bold")
        if remaining:
            render_holds(remaining)
        render_assertions(assertions, show_all=False)
    else:
        _print_message("Nothing else is blocking idle sleep.", style="dim")


def cmd_purge(args: argparse.Namespace) -> int:
    holds = load_holds()
    targets = find_purgeable(holds)
    me = _run(["id", "-un"]).strip()
    killable = [t for t in targets if t.user == me]
    foreign = [t for t in targets if t.user != me]

    # Things purge will never kill: apps and system services holding assertions.
    others = [
        a for a in system_assertions() if a.blocking and a.process not in HOLDER_NAMES
    ]
    others_by_proc = sorted({f"{a.process} (pid {a.pid})" for a in others})

    if not targets:
        _print_message("No caffeinate/systemd-inhibit processes running.", style="dim")
    for t in killable:
        tag = f"ours [{t.ours}]" if t.ours else "external"
        _print_message(f"  {t.pid:>6}  {tag:<12} {t.command}", style="bold")
        _print_message(f"          launched by: {t.parent[:90]}", style="dim")
        if t.ours is None and t.parent_alive and t.ppid > 1:
            _print_message(
                "          ! parent is still running and may start a new one",
                style="yellow",
            )
        if t.children and t.ours is None:
            _print_message(
                f"          ! wraps a running command, which will carry on unheld: {t.children[0][:80]}",
                style="yellow",
            )
    for t in foreign:
        _print_message(
            f"  {t.pid:>6}  owned by {t.user}: {t.command}  -> run yourself: sudo kill {t.pid}",
            style="yellow",
        )
    if others_by_proc:
        _print_message(
            f"Not touched (apps/system services): {', '.join(others_by_proc)}",
            style="dim",
        )

    if not killable:
        return 0
    if not args.yes:
        if not sys.stdin.isatty():
            raise SystemExit("awake purge: not a terminal; re-run with -y to confirm")
        try:
            answer = (
                input(f"Kill {len(killable)} keep-awake process(es)? [y/N] ")
                .strip()
                .lower()
            )
        except EOFError, KeyboardInterrupt:
            answer = ""
            print()
        if answer not in {"y", "yes"}:
            _print_message("Nothing killed.", style="dim")
            return 1
    for t in killable:
        try:
            os.kill(t.pid, signal.SIGTERM)
            _print_message(f"Killed {t.pid}", style="green")
        except ProcessLookupError:
            pass
        except PermissionError:
            _print_message(
                f"Permission denied for {t.pid}: sudo kill {t.pid}", style="red"
            )
        if t.ours:
            remove_hold(t.ours)
    time.sleep(0.3)
    _show_remaining()
    return 0


def cmd_blank(args: argparse.Namespace) -> int:
    if not IS_MAC:
        raise SystemExit("awake blank: only macOS is supported in v1")
    subprocess.run(["pmset", "displaysleepnow"], check=False)
    blockers = [a for a in system_assertions() if a.blocking]
    if load_holds() or blockers:
        _print_message(
            "Display off. The machine is still awake (holds/assertions active).",
            style="dim",
        )
    else:
        _print_message(
            "Display off. Nothing is holding the machine awake, so it may idle-sleep per Energy settings.",
            style="yellow",
        )
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="awake",
        description="See what keeps this machine awake; manage our own labelled keep-awake holds.",
    )
    sub = parser.add_subparsers(dest="command")

    for name, help_text in (
        ("list", "our holds + other assertions blocking sleep (default)"),
        ("status", "list + power, lid and SSH caveats"),
    ):
        p = sub.add_parser(name, help=help_text)
        p.add_argument(
            "-a",
            "--all",
            action="store_true",
            help="include background/short-lived assertions",
        )
        p.add_argument("--json", action="store_true", help="machine-readable output")
        p.set_defaults(func=cmd_list)

    p = sub.add_parser("on", help="start a detached hold (survives SSH disconnect)")
    p.add_argument("label", nargs="?", default="manual", help="what this hold is for")
    p.add_argument(
        "--for",
        dest="for_",
        type=parse_duration,
        metavar="DUR",
        help="auto-release after e.g. 2h, 45m",
    )
    p.add_argument(
        "--while",
        dest="while_pid",
        type=int,
        metavar="PID",
        help="release when PID exits",
    )
    p.add_argument(
        "-d", "--display", action="store_true", help="keep the display on too (macOS)"
    )
    p.set_defaults(func=cmd_on)

    p = sub.add_parser(
        "run", help="hold awake while a command runs: awake run [-l LABEL] -- cmd ..."
    )
    p.add_argument("-l", "--label", help="label (default: command name)")
    p.add_argument(
        "-d", "--display", action="store_true", help="keep the display on too (macOS)"
    )
    p.add_argument("argv", nargs=argparse.REMAINDER)
    p.set_defaults(func=cmd_run)

    p = sub.add_parser(
        "off",
        help="release OUR holds (never touches other apps; does not sleep the machine)",
    )
    p.add_argument("keys", nargs="*", help="hold ids or labels")
    p.add_argument("--all", action="store_true", help="release all of our holds")
    p.set_defaults(func=cmd_off)

    p = sub.add_parser(
        "purge",
        help="kill ALL caffeinate/systemd-inhibit processes (ours and others'), after a y/N confirm; never apps or system services",
    )
    p.add_argument("-y", "--yes", action="store_true", help="don't ask")
    p.set_defaults(func=cmd_purge)

    p = sub.add_parser(
        "blank",
        help="turn the display off now (macOS); the machine stays as awake as before",
    )
    p.set_defaults(func=cmd_blank)

    argv = sys.argv[1:] if argv is None else argv
    if not argv or (argv[0] not in sub.choices and argv[0] not in {"-h", "--help"}):
        argv = ["list", *argv]
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """CLI entry point."""
    args = parse_args(argv)
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
