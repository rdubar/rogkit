"""Tests for ports.py - listening ports viewer."""

from __future__ import annotations

import socket
import sys
from types import SimpleNamespace

from rogkit_package.bin.ports import PortInfo, _parse_lsof_output, list_ports, render_ports


def _conn(ip: str, port: int, sock_type: int, *, pid: int | None, status: str) -> SimpleNamespace:
    return SimpleNamespace(
        laddr=SimpleNamespace(ip=ip, port=port),
        type=sock_type,
        pid=pid,
        status=status,
    )


def test_list_ports_returns_listening_tcp_and_udp(monkeypatch):
    fake_connections = [
        _conn("127.0.0.1", 8000, socket.SOCK_STREAM, pid=100, status="LISTEN"),
        _conn("0.0.0.0", 5353, socket.SOCK_DGRAM, pid=200, status="NONE"),
        _conn("127.0.0.1", 9000, socket.SOCK_STREAM, pid=300, status="ESTABLISHED"),
    ]
    monkeypatch.setattr("rogkit_package.bin.ports.psutil.net_connections", lambda kind="inet": fake_connections)
    monkeypatch.setattr(
        "rogkit_package.bin.ports.psutil.Process",
        lambda pid: SimpleNamespace(name=lambda: {100: "python", 200: "mdns"}[pid]),
    )

    results = list_ports()

    assert results == [
        PortInfo(port=5353, proto="udp", address="0.0.0.0", pid=200, process_name="mdns"),
        PortInfo(port=8000, proto="tcp", address="127.0.0.1", pid=100, process_name="python"),
    ]


def test_list_ports_filters_by_port(monkeypatch):
    fake_connections = [
        _conn("127.0.0.1", 8000, socket.SOCK_STREAM, pid=100, status="LISTEN"),
        _conn("127.0.0.1", 9000, socket.SOCK_STREAM, pid=200, status="LISTEN"),
    ]
    monkeypatch.setattr("rogkit_package.bin.ports.psutil.net_connections", lambda kind="inet": fake_connections)
    monkeypatch.setattr(
        "rogkit_package.bin.ports.psutil.Process",
        lambda pid: SimpleNamespace(name=lambda: {100: "python", 200: "node"}[pid]),
    )

    results = list_ports(port=9000)

    assert results == [PortInfo(port=9000, proto="tcp", address="127.0.0.1", pid=200, process_name="node")]


def test_list_ports_filters_by_process_name(monkeypatch):
    fake_connections = [
        _conn("127.0.0.1", 8000, socket.SOCK_STREAM, pid=100, status="LISTEN"),
        _conn("127.0.0.1", 9000, socket.SOCK_STREAM, pid=200, status="LISTEN"),
    ]
    monkeypatch.setattr("rogkit_package.bin.ports.psutil.net_connections", lambda kind="inet": fake_connections)
    monkeypatch.setattr(
        "rogkit_package.bin.ports.psutil.Process",
        lambda pid: SimpleNamespace(name=lambda: {100: "python", 200: "node"}[pid]),
    )

    results = list_ports(proc_filter="pyth")

    assert results == [PortInfo(port=8000, proto="tcp", address="127.0.0.1", pid=100, process_name="python")]


def test_parse_lsof_output_parses_tcp_and_udp():
    sample = """COMMAND   PID USER   FD   TYPE DEVICE SIZE/OFF NODE NAME
Python   123 me     7u  IPv4 0x1      0t0  TCP *:8501 (LISTEN)
Dropbox  456 me   141u  IPv4 0x2      0t0  UDP 127.0.0.1:17600
"""

    results = _parse_lsof_output(sample)

    assert results == [
        PortInfo(port=8501, proto="tcp", address="*", pid=123, process_name="Python"),
        PortInfo(port=17600, proto="udp", address="127.0.0.1", pid=456, process_name="Dropbox"),
    ]


def test_list_ports_falls_back_to_lsof_on_access_denied(monkeypatch):
    monkeypatch.setattr(
        "rogkit_package.bin.ports._list_ports_psutil",
        lambda **_kwargs: (_ for _ in ()).throw(PermissionError()),
    )
    monkeypatch.setattr(
        "rogkit_package.bin.ports._list_ports_lsof",
        lambda **_kwargs: [PortInfo(port=7000, proto="tcp", address="*", pid=111, process_name="ControlCenter")],
    )

    results = list_ports()

    assert results == [PortInfo(port=7000, proto="tcp", address="*", pid=111, process_name="ControlCenter")]


def test_render_ports_plain_outputs_rows(capsys):
    render_ports([PortInfo(port=8000, proto="tcp", address="127.0.0.1", pid=100, process_name="python")], plain=True)
    out = capsys.readouterr().out
    assert "8000" in out
    assert "python" in out


def _run_main(argv: list[str]) -> int:
    old = sys.argv
    sys.argv = ["ports"] + argv
    try:
        from rogkit_package.bin.ports import main as _main

        return _main()
    finally:
        sys.argv = old


def test_main_plain_output(monkeypatch, capsys):
    monkeypatch.setattr(
        "rogkit_package.bin.ports.list_ports",
        lambda port=None, proc_filter=None: [
            PortInfo(port=8000, proto="tcp", address="127.0.0.1", pid=100, process_name="python")
        ],
    )
    monkeypatch.setattr("rogkit_package.bin.ports.PSUTIL_AVAILABLE", True)

    rc = _run_main(["8000", "--plain"])

    assert rc == 0
    assert "8000" in capsys.readouterr().out
