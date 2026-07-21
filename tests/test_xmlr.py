"""Tests for xmlr.py."""

from __future__ import annotations

from pathlib import Path

import pytest

from rogkit_package.bin import xmlr


def test_load_config_reports_missing_setup(tmp_path, monkeypatch):
    monkeypatch.setattr(xmlr, "load_rogkit_toml", lambda section: (_ for _ in ()).throw(KeyError(section)))
    monkeypatch.setattr(xmlr, "get_invoking_cwd", lambda: tmp_path)
    monkeypatch.setattr(xmlr, "get_rogkit_toml_path", lambda: tmp_path / "config.toml")

    with pytest.raises(xmlr.XmlrConfigError) as exc_info:
        xmlr.Config.load_config("test")

    message = str(exc_info.value)
    assert "Missing XML-RPC configuration for [erp-test]" in message
    assert "url, db, username, password" in message
    assert "[erp-test]" in message


def test_load_config_uses_invoking_cwd_dotenv(tmp_path, monkeypatch):
    monkeypatch.setattr(xmlr, "load_rogkit_toml", lambda section: (_ for _ in ()).throw(KeyError(section)))
    monkeypatch.setattr(xmlr, "get_invoking_cwd", lambda: tmp_path)
    (tmp_path / ".env").write_text(
        "\n".join(
            [
                "url=https://odoo.example.test",
                "db=example",
                "username=roger",
                "password=secret",
            ]
        ),
        encoding="utf-8",
    )

    config = xmlr.Config.load_config("test")

    assert config.url == "https://odoo.example.test"
    assert config.db == "example"
    assert config.username == "roger"
    assert config.password == "secret"
    assert config.environment == "test"


def test_main_returns_config_error_without_traceback(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(xmlr.Config, "load_config", lambda env: (_ for _ in ()).throw(xmlr.XmlrConfigError("missing setup")))
    monkeypatch.setattr("sys.argv", ["xmlr"])

    assert xmlr.main() == 2
    assert capsys.readouterr().err == "missing setup\n"


def test_load_dotenv_ignores_comments_and_quotes(tmp_path):
    path = Path(tmp_path / ".env")
    path.write_text(
        '# comment\nurl="https://odoo.example.test"\ndb=example\nusername=roger\npassword=\'secret\'\n',
        encoding="utf-8",
    )

    assert xmlr._load_dotenv_config(path) == {
        "url": "https://odoo.example.test",
        "db": "example",
        "username": "roger",
        "password": "secret",
    }
