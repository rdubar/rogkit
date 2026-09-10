"""Tests for tunnel.py -- SSH DB tunnel + live Vaultwarden credential manager."""

from __future__ import annotations

import argparse

from rogkit_package.bin import tunnel

ENTRIES = [
    {
        "system": "erp",
        "tier": "live",
        "bastion_user": "tunnel",
        "bastion_host": "bastion-live.example.internal",
        "host_ro": "example-live-pg-cluster.cluster-ro-abc123.eu-central-1.rds.amazonaws.com",
        "host_rw": "example-live-pg-cluster.cluster-abc123.eu-central-1.rds.amazonaws.com",
        "remote_port": 5432,
        "local_port": 5433,
        "db_name": "exampledb",
        "db_user": "example.user",
        "vaultwarden_item": "Example_DB_PW - Live",
    },
    {
        "system": "erp",
        "tier": "test",
        "bastion_user": "tunnel",
        "bastion_host": "bastion-test.example.internal",
        "host_rw": "example-test-pg-cluster.cluster-abc123.eu-central-1.rds.amazonaws.com",
        "remote_port": 5432,
        "local_port": 5434,
        "db_name": "exampledb",
        "db_user": "example.user",
        "vaultwarden_item": "",
    },
]


def test_find_entry_matches_system_and_tier(monkeypatch):
    monkeypatch.setattr(tunnel, "get_config_value", lambda group, key: ENTRIES)
    entry = tunnel._find_entry("erp", "live")
    assert entry is not None
    assert entry["local_port"] == 5433


def test_find_entry_missing_returns_none(monkeypatch):
    monkeypatch.setattr(tunnel, "get_config_value", lambda group, key: ENTRIES)
    assert tunnel._find_entry("odoo13-de", "live") is None


def test_entries_handles_non_list_config(monkeypatch):
    monkeypatch.setattr(tunnel, "get_config_value", lambda group, key: [])
    assert tunnel._entries() == []


def test_target_host_prefers_read_only_by_default():
    entry = ENTRIES[0]
    assert tunnel._target_host(entry, writer=False) == entry["host_ro"]


def test_target_host_uses_writer_flag():
    entry = ENTRIES[0]
    assert tunnel._target_host(entry, writer=True) == entry["host_rw"]


def test_target_host_falls_back_to_writer_when_no_reader():
    entry = ENTRIES[1]  # no host_ro
    assert tunnel._target_host(entry, writer=False) == entry["host_rw"]


def test_tunnel_target_parses_ssh_command_line(monkeypatch):
    cmdline = (
        "ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -f -N -T -M "
        "-L 127.0.0.1:5433:example-live-pg-cluster.cluster-ro-abc123.eu-central-1.rds.amazonaws.com:5432 "
        "tunnel@bastion-live.example.internal"
    )

    class FakeResult:
        stdout = cmdline

    monkeypatch.setattr(tunnel.subprocess, "run", lambda *a, **k: FakeResult())
    target = tunnel._tunnel_target(1234)
    assert target == "example-live-pg-cluster.cluster-ro-abc123.eu-central-1.rds.amazonaws.com"


def test_tunnel_target_returns_none_without_match(monkeypatch):
    class FakeResult:
        stdout = "some unrelated process"

    monkeypatch.setattr(tunnel.subprocess, "run", lambda *a, **k: FakeResult())
    assert tunnel._tunnel_target(1234) is None


def test_require_entry_prints_error_when_missing(monkeypatch, capsys):
    monkeypatch.setattr(tunnel, "get_config_value", lambda group, key: ENTRIES)
    monkeypatch.setattr(tunnel, "RICH_AVAILABLE", False)
    args = argparse.Namespace(system="odoo13-de", tier="live")
    assert tunnel._require_entry(args) is None
    assert "No registered entry" in capsys.readouterr().out


def test_entry_password_prefers_vaultwarden_item(monkeypatch):
    monkeypatch.setattr(tunnel, "_rbw_password", lambda item: f"from-rbw:{item}")
    entry = {"vaultwarden_item": "Some Item", "env_var": "SOME_PW"}
    assert tunnel._entry_password(entry) == "from-rbw:Some Item"


def test_entry_password_falls_back_to_env_var(monkeypatch):
    monkeypatch.setenv("SOME_PW", "from-env")
    entry = {"vaultwarden_item": "", "env_var": "SOME_PW"}
    assert tunnel._entry_password(entry) == "from-env"


def test_entry_password_reports_missing_env_var(monkeypatch, capsys):
    monkeypatch.setattr(tunnel, "RICH_AVAILABLE", False)
    monkeypatch.delenv("UNSET_PW", raising=False)
    entry = {"vaultwarden_item": "", "env_var": "UNSET_PW"}
    assert tunnel._entry_password(entry) is None
    assert "UNSET_PW" in capsys.readouterr().out


def test_entry_password_reports_nothing_configured(monkeypatch, capsys):
    monkeypatch.setattr(tunnel, "RICH_AVAILABLE", False)
    entry = {"vaultwarden_item": "", "env_var": ""}
    assert tunnel._entry_password(entry) is None
    assert "No vaultwarden_item or env_var" in capsys.readouterr().out


def test_rbw_password_returns_stripped_stdout(monkeypatch):
    class FakeResult:
        returncode = 0
        stdout = "s3cr3t\n"
        stderr = ""

    monkeypatch.setattr(tunnel.subprocess, "run", lambda *a, **k: FakeResult())
    assert tunnel._rbw_password("Some Item") == "s3cr3t"


def test_rbw_password_reports_failure(monkeypatch, capsys):
    class FakeResult:
        returncode = 1
        stdout = ""
        stderr = "locked"

    monkeypatch.setattr(tunnel, "RICH_AVAILABLE", False)
    monkeypatch.setattr(tunnel.subprocess, "run", lambda *a, **k: FakeResult())
    assert tunnel._rbw_password("Some Item") is None
    assert "rbw unlock" in capsys.readouterr().out
