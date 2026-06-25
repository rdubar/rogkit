#!/usr/bin/env python3
"""Spin up a disposable Postgres in a container for quick, throwaway DB work.

Targets Apple ``container`` (per-container microVM) or Docker -- whichever is on
PATH (override with ``PGSCRATCH_RUNTIME``). Handy for validating SQL or oerplib
scripts against a clean slice without touching a local (Homebrew) Postgres:
load a dump, poke it, throw it away.

Subcommands::

    up      start a disposable Postgres, optionally restoring a dump
    down    stop and remove it
    psql    open psql against the running instance
    status  show whether it is running + the connection string
    run     start an ephemeral instance, run a command with PG* env set, tear down

The container is published on ``127.0.0.1:<port>`` (default 5433, to avoid a
Homebrew Postgres on 5432), so existing psql / oerplib tooling connects
unchanged. Dumps are restored through the container's own psql/pg_restore, so
the client version always matches the server.
"""

from __future__ import annotations

import argparse
import gzip
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

from ..settings import get_invoking_cwd

try:
    from rich.console import Console
    from rich.text import Text

    console = Console()
    RICH_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover
    console = None  # type: ignore[assignment]
    RICH_AVAILABLE = False


RUNTIMES = ("container", "docker")
DEFAULT_IMAGE = os.environ.get("PGSCRATCH_IMAGE", "postgres:17")
DEFAULT_PORT = int(os.environ.get("PGSCRATCH_PORT", "5433"))
DEFAULT_NAME = os.environ.get("PGSCRATCH_NAME", "pgscratch")
PG_USER = os.environ.get("PGSCRATCH_USER", "openerp_pets")
PG_PASSWORD = os.environ.get("PGSCRATCH_PASSWORD", "scratch")
PG_DB = os.environ.get("PGSCRATCH_DB", "scratch")
READY_TIMEOUT = int(os.environ.get("PGSCRATCH_READY_TIMEOUT", "60"))

RESTORE_SUFFIXES = (".dump", ".backup", ".pgdump")


def _msg(message: str, *, style: str | None = None) -> None:
    """Print to stdout with optional Rich styling and a plain fallback."""
    if RICH_AVAILABLE:
        console.print(Text(message, style=style) if style else message, highlight=False)
    else:
        print(message)


def resolve_runtime() -> str:
    """Return the container runtime to use ('container' or 'docker')."""
    chosen = os.environ.get("PGSCRATCH_RUNTIME")
    if chosen:
        if not shutil.which(chosen):
            raise SystemExit(f"PGSCRATCH_RUNTIME={chosen!r} not found on PATH")
        return chosen
    for runtime in RUNTIMES:
        if shutil.which(runtime):
            return runtime
    raise SystemExit("no container runtime found (need `container` or `docker` on PATH)")


def container_exists(runtime: str, name: str) -> bool:
    """True if a container with this name exists (running or not)."""
    result = subprocess.run(
        [runtime, "inspect", name],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def is_running(runtime: str, name: str) -> bool:
    """True if the container is running (``exec`` only works on running containers)."""
    result = subprocess.run(
        [runtime, "exec", name, "true"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def uses_pg_restore(dump_name: str) -> bool:
    """True if the dump is a custom-format archive (restored with pg_restore, not psql)."""
    return dump_name.lower().endswith(RESTORE_SUFFIXES)


def connection_string(port: int) -> str:
    """Return a copy-pasteable psql connection line for the host."""
    return f"PGPASSWORD={PG_PASSWORD} psql -h 127.0.0.1 -p {port} -U {PG_USER} {PG_DB}"


def child_env(port: int) -> dict[str, str]:
    """Environment with PG* set so child processes reach the scratch DB."""
    env = dict(os.environ)
    env.update(
        PGHOST="127.0.0.1",
        PGPORT=str(port),
        PGUSER=PG_USER,
        PGPASSWORD=PG_PASSWORD,
        PGDATABASE=PG_DB,
    )
    return env


def start_container(runtime: str, name: str, port: int, image: str) -> None:
    """Start a detached Postgres container published on 127.0.0.1:<port>."""
    cmd = [
        runtime, "run", "--detach", "--rm", "--name", name,
        "--publish", f"127.0.0.1:{port}:5432",
        "--env", f"POSTGRES_USER={PG_USER}",
        "--env", f"POSTGRES_PASSWORD={PG_PASSWORD}",
        "--env", f"POSTGRES_DB={PG_DB}",
        image,
    ]
    # stderr is left inherited so the runtime's own error (e.g. "port is already
    # allocated", or Apple container's "XPC connection error") is visible.
    if subprocess.run(cmd, stdout=subprocess.DEVNULL).returncode != 0:
        raise SystemExit(
            f"failed to start container with `{runtime}` (see error above; "
            "if the port is already in use, pass --port)"
        )


def _container_pg_ready(runtime: str, name: str) -> bool:
    """True if Postgres accepts TCP connections *inside* the container.

    Force a TCP check (-h 127.0.0.1): the official image's init phase serves only
    on a unix socket, so a default pg_isready passes too early -- before the real
    server (and the published port) is listening.
    """
    return subprocess.run(
        [runtime, "exec", name, "pg_isready", "-h", "127.0.0.1", "-U", PG_USER, "-d", PG_DB],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ).returncode == 0


def _host_pg_ready(port: int) -> bool:
    """True if Postgres is reachable from the host on the published port.

    Prefers a real `pg_isready` probe when available (catches the cold-start
    'server closed the connection' half-state), else falls back to a TCP connect.
    """
    pg_isready = shutil.which("pg_isready")
    if pg_isready:
        return subprocess.run(
            [pg_isready, "-h", "127.0.0.1", "-p", str(port), "-U", PG_USER, "-d", PG_DB, "-q"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode == 0
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            return True
    except OSError:
        return False


def wait_ready(runtime: str, name: str, port: int, timeout: int = READY_TIMEOUT) -> None:
    """Block until Postgres is up in the container *and* reachable on the host port.

    Two phases: the in-container probe confirms the real server is listening; the
    host-side probe confirms the published port is actually forwarded -- Apple
    container can lag on port forwarding during a container's first boot.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _container_pg_ready(runtime, name):
            break
        time.sleep(0.3)
    else:
        raise SystemExit(f"Postgres did not start in the container after {timeout}s")

    while time.monotonic() < deadline:
        if _host_pg_ready(port):
            return
        time.sleep(0.3)
    raise SystemExit(f"Postgres not reachable on 127.0.0.1:{port} after {timeout}s")


def restore_dump(runtime: str, name: str, dump: Path) -> None:
    """Restore a dump into the scratch DB using the container's own tools.

    Custom-format dumps (``.dump`` / ``.backup`` / ``.pgdump``, i.e. ``pg_dump
    -Fc``) go through ``pg_restore``; everything else is treated as plain SQL
    (``.sql``, ``.sql.gz``) and piped to ``psql``. Streaming through the
    container keeps the client version in step with the server.
    """
    if not dump.exists():
        raise SystemExit(f"dump not found: {dump}")

    if uses_pg_restore(dump.name):
        inner = [runtime, "exec", "-i", name, "pg_restore",
                 "-U", PG_USER, "-d", PG_DB, "--no-owner", "--no-privileges"]
        opener = open
    else:
        inner = [runtime, "exec", "-i", name, "psql",
                 "-U", PG_USER, "-d", PG_DB, "-v", "ON_ERROR_STOP=1"]
        opener = gzip.open if dump.name.lower().endswith(".gz") else open

    # Stream the dump into the container's stdin (a GzipFile has no usable
    # fileno(), so pipe explicitly rather than handing the object to stdin=).
    proc = subprocess.Popen(inner, stdin=subprocess.PIPE)
    assert proc.stdin is not None
    try:
        with opener(dump, "rb") as handle:  # type: ignore[operator]
            shutil.copyfileobj(handle, proc.stdin)
    finally:
        proc.stdin.close()
    if proc.wait() != 0:
        raise SystemExit(f"dump restore failed ({dump.name})")
    _msg(f"restored {dump.name}", style="green")


def teardown(runtime: str, name: str) -> None:
    """Stop and remove a container (``--rm`` usually handles it; this is belt-and-braces).

    Use ``rm`` (not ``delete``) -- Docker only knows ``rm``; Apple container accepts both.
    """
    subprocess.run([runtime, "stop", name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run([runtime, "rm", name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def cmd_up(runtime: str, args: argparse.Namespace) -> int:
    if is_running(runtime, args.name):
        _msg(f"'{args.name}' already running.")
        _msg(connection_string(args.port))
        return 0
    if container_exists(runtime, args.name):
        teardown(runtime, args.name)  # clear a stopped leftover so the name is free
    _msg(f"starting '{args.name}' ({runtime}, {args.image}) on 127.0.0.1:{args.port} ...")
    start_container(runtime, args.name, args.port, args.image)
    wait_ready(runtime, args.name, args.port)
    if args.dump:
        restore_dump(runtime, args.name, args.dump)
    _msg("ready.", style="green")
    _msg(connection_string(args.port))
    return 0


def cmd_down(runtime: str, args: argparse.Namespace) -> int:
    if not container_exists(runtime, args.name):
        _msg(f"'{args.name}' is not running.")
        return 0
    teardown(runtime, args.name)
    _msg(f"removed '{args.name}'.", style="green")
    return 0


def cmd_status(runtime: str, args: argparse.Namespace) -> int:
    if is_running(runtime, args.name):
        _msg(f"'{args.name}' running ({runtime}).", style="green")
        _msg(connection_string(args.port))
    elif container_exists(runtime, args.name):
        _msg(f"'{args.name}' exists but is not running (try `pgscratch down`).")
    else:
        _msg(f"'{args.name}' not running.")
    return 0


def cmd_psql(runtime: str, args: argparse.Namespace) -> int:
    if not is_running(runtime, args.name):
        raise SystemExit(f"'{args.name}' is not running -- start it with `pgscratch up`")
    extra = args.psql_args[1:] if args.psql_args[:1] == ["--"] else args.psql_args
    tty = ["-t"] if sys.stdin.isatty() else []
    cmd = [runtime, "exec", "-i", *tty, args.name, "psql", "-U", PG_USER, "-d", PG_DB, *extra]
    return subprocess.run(cmd).returncode


def cmd_run(runtime: str, args: argparse.Namespace) -> int:
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        raise SystemExit("`pgscratch run` needs a command after `--`")
    name = f"{args.name}-run-{os.getpid()}"
    _msg(f"ephemeral '{name}' ({runtime}) on 127.0.0.1:{args.port} ...")
    start_container(runtime, name, args.port, args.image)
    try:
        wait_ready(runtime, name, args.port)
        if args.dump:
            restore_dump(runtime, name, args.dump)
        _msg(f"running: {' '.join(command)}", style="cyan")
        return subprocess.run(command, env=child_env(args.port)).returncode
    finally:
        teardown(runtime, name)
        _msg(f"torn down '{name}'.")


def _add_common(parser: argparse.ArgumentParser, *, dump: bool = False) -> None:
    parser.add_argument("--name", default=DEFAULT_NAME, help="container name (default: %(default)s)")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT,
                        help="host port to publish (default: %(default)s)")
    parser.add_argument("--image", default=DEFAULT_IMAGE, help="Postgres image (default: %(default)s)")
    if dump:
        parser.add_argument("--dump", help="dump to restore: .sql / .sql.gz (psql) or .dump (pg_restore)")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="pgscratch",
        description="Disposable Postgres in a container (Apple `container` or Docker).",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    _add_common(sub.add_parser("up", help="start a disposable Postgres"), dump=True)
    _add_common(sub.add_parser("down", help="stop and remove it"))
    _add_common(sub.add_parser("status", help="show running state + connection string"))

    p_psql = sub.add_parser("psql", help="open psql against the running instance")
    _add_common(p_psql)
    p_psql.add_argument("psql_args", nargs=argparse.REMAINDER, help="extra args after -- passed to psql")

    p_run = sub.add_parser("run", help="run a command with PG* set, then tear down")
    _add_common(p_run, dump=True)
    p_run.add_argument("command", nargs=argparse.REMAINDER, help="command after -- (e.g. -- ./script.py)")

    return parser.parse_args()


def main() -> int:
    """CLI entry point."""
    cwd = get_invoking_cwd()
    args = parse_args()
    runtime = resolve_runtime()

    dump = getattr(args, "dump", None)
    if dump:
        path = Path(dump)
        args.dump = path if path.is_absolute() else cwd / path

    dispatch = {
        "up": cmd_up,
        "down": cmd_down,
        "status": cmd_status,
        "psql": cmd_psql,
        "run": cmd_run,
    }
    try:
        return dispatch[args.cmd](runtime, args)
    except KeyboardInterrupt:  # pragma: no cover
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
