"""Tests for myip.py - local interface and external IP viewer."""

from __future__ import annotations

import socket
import sys
from types import SimpleNamespace

from rogkit_package.bin.myip import InterfaceInfo, fetch_external_ip, list_interfaces, render_interfaces


def _addr(family: int, address: str, netmask: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(family=family, address=address, netmask=netmask)


def test_list_interfaces_skips_loopback_by_default(monkeypatch):
    monkeypatch.setattr(
        "rogkit_package.bin.myip.psutil.net_if_addrs",
        lambda: {
            "lo0": [
                _addr(socket.AF_INET, "127.0.0.1", "255.0.0.0"),
                _addr(socket.AF_LINK, "00:00:00:00:00:00"),
            ],
            "en0": [
                _addr(socket.AF_INET, "192.168.1.10", "255.255.255.0"),
                _addr(socket.AF_LINK, "aa:bb:cc:dd:ee:ff"),
            ],
        },
    )
    monkeypatch.setattr("rogkit_package.bin.myip._default_interface", lambda: "en0")

    results = list_interfaces()

    assert results == [
        InterfaceInfo(
            name="en0",
            ipv4="192.168.1.10",
            netmask="255.255.255.0",
            mac="aa:bb:cc:dd:ee:ff",
            is_default=True,
        )
    ]


def test_list_interfaces_can_include_loopback(monkeypatch):
    monkeypatch.setattr(
        "rogkit_package.bin.myip.psutil.net_if_addrs",
        lambda: {
            "lo0": [
                _addr(socket.AF_INET, "127.0.0.1", "255.0.0.0"),
                _addr(socket.AF_LINK, "00:00:00:00:00:00"),
            ]
        },
    )
    monkeypatch.setattr("rogkit_package.bin.myip._default_interface", lambda: None)

    results = list_interfaces(include_loopback=True)

    assert results == [
        InterfaceInfo(
            name="lo0",
            ipv4="127.0.0.1",
            netmask="255.0.0.0",
            mac="00:00:00:00:00:00",
            is_default=False,
        )
    ]


def test_fetch_external_ip_returns_first_success(monkeypatch):
    class FakeResponse:
        def __init__(self, text: str):
            self._text = text

        def read(self) -> bytes:
            return self._text.encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(
        "rogkit_package.bin.myip.urlopen",
        lambda _url, timeout=2.0: FakeResponse("203.0.113.10\n"),
    )

    assert fetch_external_ip() == "203.0.113.10"


def test_render_interfaces_plain_outputs_rows(capsys):
    render_interfaces(
        [
            InterfaceInfo(
                name="en0",
                ipv4="192.168.1.10",
                netmask="255.255.255.0",
                mac="aa:bb:cc:dd:ee:ff",
                is_default=True,
            )
        ],
        plain=True,
    )
    out = capsys.readouterr().out
    assert "en0" in out
    assert "192.168.1.10" in out


def _run_main(argv: list[str]) -> int:
    old = sys.argv
    sys.argv = ["myip"] + argv
    try:
        from rogkit_package.bin.myip import main as _main

        return _main()
    finally:
        sys.argv = old


def test_main_plain_output(monkeypatch, capsys):
    monkeypatch.setattr(
        "rogkit_package.bin.myip.list_interfaces",
        lambda include_loopback=False: [
            InterfaceInfo(
                name="en0",
                ipv4="192.168.1.10",
                netmask="255.255.255.0",
                mac="aa:bb:cc:dd:ee:ff",
                is_default=True,
            )
        ],
    )
    monkeypatch.setattr("rogkit_package.bin.myip.fetch_external_ip", lambda timeout=2.0: "203.0.113.10")
    monkeypatch.setattr("rogkit_package.bin.myip.PSUTIL_AVAILABLE", True)

    rc = _run_main(["--plain"])

    assert rc == 0
    out = capsys.readouterr().out
    assert "en0" in out
    assert "External IP: 203.0.113.10" in out
