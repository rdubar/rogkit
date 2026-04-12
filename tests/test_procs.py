"""Tests for procs.py - process finder and manager."""

import sys

import pytest

from rogkit_package.bin.procs import ProcInfo, find_procs, kill_procs, render_procs


class FakeProc:
    """Simple stand-in for a psutil process with an info dict."""

    def __init__(self, info):
        self.info = info


def test_find_procs_filters_and_sorts(monkeypatch):
    fake_processes = [
        FakeProc(
            {
                "pid": 10,
                "name": "python",
                "status": "running",
                "cpu_percent": 12.0,
                "memory_percent": 5.5,
                "cmdline": ["python", "worker.py"],
            }
        ),
        FakeProc(
            {
                "pid": 20,
                "name": "node",
                "status": "sleeping",
                "cpu_percent": 42.0,
                "memory_percent": 3.0,
                "cmdline": ["node", "server.js"],
            }
        ),
    ]
    monkeypatch.setattr("rogkit_package.bin.procs.psutil.process_iter", lambda _attrs: fake_processes)

    results = find_procs("o")

    assert [proc.pid for proc in results] == [20, 10]
    assert results[0].cmdline == "node server.js"


def test_find_procs_ignores_access_errors(monkeypatch):
    class FakeErrorProcess:
        @property
        def info(self):
            raise pytest.importorskip("psutil").AccessDenied(pid=123)

    monkeypatch.setattr(
        "rogkit_package.bin.procs.psutil.process_iter",
        lambda _attrs: [FakeErrorProcess()],
    )

    assert find_procs() == []


def test_kill_procs_force_sends_sigkill(monkeypatch):
    sent = []
    monkeypatch.setattr("rogkit_package.bin.procs.os.kill", lambda pid, sig: sent.append((pid, sig)))

    count = kill_procs([ProcInfo(12, "python", "running", 1.0, 2.0, "python app.py")], force=True)

    assert count == 1
    assert sent


def test_kill_procs_confirms_before_sigterm(monkeypatch):
    sent = []
    monkeypatch.setattr("rogkit_package.bin.procs.os.kill", lambda pid, sig: sent.append((pid, sig)))
    monkeypatch.setattr("builtins.input", lambda _prompt: "y")

    count = kill_procs([ProcInfo(34, "node", "sleeping", 0.0, 1.0, "node server.js")], force=False)

    assert count == 1
    assert sent == [(34, sent[0][1])]


def test_render_procs_plain_outputs_rows(capsys):
    render_procs([ProcInfo(1, "python", "running", 10.0, 2.0, "python app.py")], plain=True)
    out = capsys.readouterr().out
    assert "python" in out
    assert "PID" in out


def _run_main(argv: list[str]) -> int:
    old = sys.argv
    sys.argv = ["procs"] + argv
    try:
        from rogkit_package.bin.procs import main as _main

        return _main()
    finally:
        sys.argv = old


def test_main_plain_output(monkeypatch, capsys):
    fake_results = [ProcInfo(10, "python", "running", 12.0, 5.0, "python worker.py")]
    monkeypatch.setattr("rogkit_package.bin.procs.find_procs", lambda pattern=None: fake_results)
    monkeypatch.setattr("rogkit_package.bin.procs.PSUTIL_AVAILABLE", True)

    rc = _run_main(["python", "--plain"])

    assert rc == 0
    assert "python" in capsys.readouterr().out
