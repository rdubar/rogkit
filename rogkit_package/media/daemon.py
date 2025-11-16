"""Helpers for running a background daemon process."""

from __future__ import annotations

import contextlib
import json
import os
import sys
import socket
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, Optional, Sequence, Tuple


def _remove_stale_socket(path: Path) -> None:
    if path.exists():
        try:
            path.unlink()
        except OSError:
            pass


@contextlib.contextmanager
def daemon_env_guard(env_flag: str) -> Iterator[None]:
    """Context manager to temporarily set an environment variable to enable a daemon."""
    previous = os.environ.get(env_flag)
    os.environ[env_flag] = "1"
    try:
        yield
    finally:
        if previous is None:
            with contextlib.suppress(KeyError):
                del os.environ[env_flag]
        else:
            os.environ[env_flag] = previous


def connect_to_daemon(socket_path: Path, *, timeout: float = 1.0) -> socket.socket:
    """Connect to a daemon over a Unix socket."""
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    sock.connect(str(socket_path))
    return sock


def send_daemon_message(
    socket_path: Path, payload: Dict[str, Any], *, timeout: float
) -> Dict[str, Any]:
    """Send a message to a daemon and return the response."""
    sock = connect_to_daemon(socket_path, timeout=timeout)
    try:
        message = json.dumps(payload) + "\n"
        sock.sendall(message.encode("utf-8"))
        sock.shutdown(socket.SHUT_WR)
        with sock.makefile("r", encoding="utf-8") as response_stream:
            response_line = response_stream.readline()
        if not response_line:
            print(f"Daemon closed connection without response: {response_line} - try running again.")
            sys.exit(1)
            # raise RuntimeError("Daemon closed connection without response")
        return json.loads(response_line)
    finally:
        sock.close()


def spawn_daemon_process(
    python_executable: str,
    module: str,
    env_flag: str,
    *,
    extra_env: Optional[Dict[str, str]] = None,
) -> bool:
    """Spawn a daemon process with an optional extra environment."""
    if os.environ.get(env_flag) == "1":
        return False

    env = os.environ.copy()
    env.pop(env_flag, None)
    if extra_env:
        env.update(extra_env)

    try:
        subprocess.Popen(
            [python_executable, "-m", module, "--daemon"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            env=env,
        )
    except OSError:
        return False
    return True


def ping_daemon(socket_path: Path, *, timeout: float = 1.0) -> bool:
    """Ping the daemon and return True if it is running."""
    try:
        response = send_daemon_message(
            socket_path,
            {"action": "ping"},
            timeout=timeout,
        )
    except (FileNotFoundError, ConnectionError, OSError, socket.timeout):
        return False
    return response.get("status") == "ok"


def wait_for_daemon_startup(socket_path: Path, *, timeout: float) -> bool:
    """Wait for the daemon to start and return True if it is running."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if ping_daemon(socket_path, timeout=1.0):
            return True
        time.sleep(0.1)
    return False


def request_daemon_shutdown(socket_path: Path, *, timeout: float) -> bool:
    """Request the daemon to shut down and return True if it is successful."""
    try:
        response = send_daemon_message(
            socket_path,
            {"action": "shutdown"},
            timeout=timeout,
        )
    except (FileNotFoundError, ConnectionError, OSError, socket.timeout):
        return False
    return response.get("status") == "ok"


class MediaDaemon:
    """Foreground daemon that serves media CLI requests over a Unix socket."""

    def __init__(
        self,
        socket_path: Path,
        executor: Callable[[Sequence[str]], Tuple[int, str, str]],
    ):
        self.socket_path = socket_path
        self._executor = executor
        self._stop_event = threading.Event()
        self._server_socket: Optional[socket.socket] = None

    def serve_forever(self) -> None:
        """Serve the daemon forever."""
        _remove_stale_socket(self.socket_path)
        server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server_socket.bind(str(self.socket_path))
        server_socket.listen(8)
        server_socket.settimeout(1.0)
        os.chmod(str(self.socket_path), 0o600)
        self._server_socket = server_socket
        print(f"Media daemon listening on {self.socket_path}")
        try:
            while not self._stop_event.is_set():
                try:
                    client, _ = server_socket.accept()
                except socket.timeout:
                    continue
                except OSError as exc:
                    if self._stop_event.is_set():
                        break
                    raise exc
                thread = threading.Thread(
                    target=self._handle_client,
                    args=(client,),
                    daemon=True,
                )
                thread.start()
        finally:
            self._shutdown_socket()
            _remove_stale_socket(self.socket_path)
            print("Media daemon stopped.")

    def stop(self) -> None:
        """Stop the daemon."""
        self._stop_event.set()

    def _shutdown_socket(self) -> None:
        """Shutdown the server socket."""
        if self._server_socket is not None:
            try:
                self._server_socket.close()
            finally:
                self._server_socket = None

    def _handle_client(self, client_socket: socket.socket) -> None:
        """Handle a client connection."""
        with client_socket:
            try:
                data = b""
                while True:
                    chunk = client_socket.recv(65536)
                    if not chunk:
                        break
                    data += chunk
                    if b"\n" in chunk:
                        break
                if not data:
                    return
                line = data.split(b"\n", 1)[0]
                payload = json.loads(line.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError, ValueError, OSError) as exc:
                error_payload = {"status": "error", "error": f"Invalid request: {exc}"}
                client_socket.sendall((json.dumps(error_payload) + "\n").encode("utf-8"))
                return

            action = payload.get("action", "execute")
            response: Dict[str, Any]
            if action == "ping":
                response = {"status": "ok"}
            elif action == "shutdown":
                self.stop()
                response = {"status": "ok", "message": "Shutting down"}
            elif action == "execute":
                argv = [str(arg) for arg in payload.get("argv", [])]
                if any(flag in argv for flag in ("--daemon", "--stop-daemon")):
                    response = {
                        "status": "error",
                        "error": "Nested daemon commands are not supported inside the daemon.",
                        "exit_code": 2,
                    }
                else:
                    exit_code, stdout_text, stderr_text = self._executor(argv)
                    response = {
                        "status": "ok",
                        "exit_code": exit_code,
                        "stdout": stdout_text,
                        "stderr": stderr_text,
                    }
            else:
                response = {"status": "error", "error": f"Unknown action {action!r}"}

            client_socket.sendall((json.dumps(response) + "\n").encode("utf-8"))
