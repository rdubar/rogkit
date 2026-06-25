"""Tests for pgscratch.py -- disposable Postgres container helper."""

from __future__ import annotations

import pytest

from rogkit_package.bin import pgscratch


def test_uses_pg_restore_custom_formats():
    assert pgscratch.uses_pg_restore("db.dump")
    assert pgscratch.uses_pg_restore("DB.Backup")
    assert pgscratch.uses_pg_restore("snapshot.pgdump")


def test_uses_pg_restore_plain_sql():
    assert not pgscratch.uses_pg_restore("db.sql")
    assert not pgscratch.uses_pg_restore("db.sql.gz")
    assert not pgscratch.uses_pg_restore("dump.txt")


def test_connection_string_uses_port_and_creds():
    line = pgscratch.connection_string(5499)
    assert "-p 5499" in line
    assert f"-U {pgscratch.PG_USER}" in line
    assert line.endswith(pgscratch.PG_DB)


def test_child_env_sets_pg_vars():
    env = pgscratch.child_env(5501)
    assert env["PGHOST"] == "127.0.0.1"
    assert env["PGPORT"] == "5501"
    assert env["PGUSER"] == pgscratch.PG_USER
    assert env["PGPASSWORD"] == pgscratch.PG_PASSWORD
    assert env["PGDATABASE"] == pgscratch.PG_DB


def test_child_env_preserves_existing(monkeypatch):
    monkeypatch.setenv("PGSCRATCH_KEEPME", "yes")
    assert pgscratch.child_env(5502)["PGSCRATCH_KEEPME"] == "yes"


def test_resolve_runtime_explicit(monkeypatch):
    monkeypatch.setenv("PGSCRATCH_RUNTIME", "docker")
    monkeypatch.setattr(pgscratch.shutil, "which", lambda name: "/bin/docker" if name == "docker" else None)
    assert pgscratch.resolve_runtime() == "docker"


def test_resolve_runtime_explicit_missing(monkeypatch):
    monkeypatch.setenv("PGSCRATCH_RUNTIME", "nope")
    monkeypatch.setattr(pgscratch.shutil, "which", lambda name: None)
    with pytest.raises(SystemExit):
        pgscratch.resolve_runtime()


def test_resolve_runtime_prefers_container(monkeypatch):
    monkeypatch.delenv("PGSCRATCH_RUNTIME", raising=False)
    monkeypatch.setattr(pgscratch.shutil, "which", lambda name: "/x" if name in ("container", "docker") else None)
    assert pgscratch.resolve_runtime() == "container"


def test_resolve_runtime_falls_back_to_docker(monkeypatch):
    monkeypatch.delenv("PGSCRATCH_RUNTIME", raising=False)
    monkeypatch.setattr(pgscratch.shutil, "which", lambda name: "/x" if name == "docker" else None)
    assert pgscratch.resolve_runtime() == "docker"


def test_resolve_runtime_none_available(monkeypatch):
    monkeypatch.delenv("PGSCRATCH_RUNTIME", raising=False)
    monkeypatch.setattr(pgscratch.shutil, "which", lambda name: None)
    with pytest.raises(SystemExit):
        pgscratch.resolve_runtime()
