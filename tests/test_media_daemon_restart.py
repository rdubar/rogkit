"""Tests for restarting the media daemon (used by `rogkit update`)."""

from __future__ import annotations

import pytest

from rogkit_package.media import media


@pytest.fixture
def daemon(monkeypatch, tmp_path):
    """Stub the daemon helpers; the socket is a real file so removal can be simulated."""
    sock = tmp_path / "media_daemon.sock"
    sock.touch()
    calls: list[str] = []
    state = {"shutdown_removes_socket": True, "spawn_ok": True, "ready": True}

    def shutdown():
        calls.append("shutdown")
        if state["shutdown_removes_socket"]:
            sock.unlink()
        return True

    monkeypatch.setattr(media, "_daemon_socket_path", lambda: sock)
    monkeypatch.setattr(media, "_daemon_ping", lambda path: path.exists())
    monkeypatch.setattr(media, "_request_daemon_shutdown", shutdown)
    monkeypatch.setattr(
        media, "_spawn_daemon_process", lambda: calls.append("spawn") or state["spawn_ok"]
    )
    monkeypatch.setattr(media, "_wait_for_daemon_startup", lambda deadline: state["ready"])
    monkeypatch.setattr(media, "DAEMON_STARTUP_TIMEOUT_SECONDS", 0.2)
    return sock, calls, state


def test_restart_is_noop_when_not_running(daemon, capsys):
    sock, calls, _ = daemon
    sock.unlink()

    assert media._restart_daemon_if_running() == 0
    assert calls == []
    assert "nothing to restart" in capsys.readouterr().out


def test_restart_stops_then_spawns(daemon, capsys):
    _, calls, _ = daemon

    assert media._restart_daemon_if_running() == 0
    assert calls == ["shutdown", "spawn"]
    assert "Restarted media daemon." in capsys.readouterr().out


def test_restart_refuses_to_spawn_while_old_socket_remains(daemon):
    _, calls, state = daemon
    state["shutdown_removes_socket"] = False

    assert media._restart_daemon_if_running() == 1
    assert "spawn" not in calls


def test_restart_reports_spawn_failure(daemon):
    _, _, state = daemon
    state["spawn_ok"] = False

    assert media._restart_daemon_if_running() == 1


def test_restart_reports_daemon_not_ready(daemon):
    _, _, state = daemon
    state["ready"] = False

    assert media._restart_daemon_if_running() == 1
