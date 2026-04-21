from __future__ import annotations

from pathlib import Path

from rogkit_package.bin import setup


def test_default_profile_for_shell(monkeypatch, tmp_path):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    assert setup._default_profile_for_shell("zsh") == tmp_path / ".zshrc"
    assert setup._default_profile_for_shell("bash") == tmp_path / ".bashrc"
    assert setup._default_profile_for_shell("fish") is None


def test_profile_sources_aliases_accepts_rogkit_path(tmp_path):
    profile = tmp_path / ".zshrc"
    profile.write_text('source "/Users/rdubar/dev/rogkit/aliases"\n', encoding="utf-8")

    assert setup._profile_sources_aliases(profile) is True


def test_ensure_config_preview(monkeypatch, tmp_path):
    config_path = tmp_path / "config.toml"
    secrets_path = tmp_path / "secrets.toml"
    monkeypatch.setattr(setup, "get_rogkit_toml_path", lambda: config_path)
    monkeypatch.setattr(setup, "get_rogkit_secrets_path", lambda: secrets_path)

    result = setup._ensure_config(apply=False)

    assert result.status == "warn"
    assert "would be created" in result.summary.lower()


def test_ensure_config_apply(monkeypatch, tmp_path):
    config_path = tmp_path / "config.toml"
    secrets_path = tmp_path / "secrets.toml"
    calls = {"created": 0}
    monkeypatch.setattr(setup, "get_rogkit_toml_path", lambda: config_path)
    monkeypatch.setattr(setup, "get_rogkit_secrets_path", lambda: secrets_path)

    def _create():
        calls["created"] += 1
        config_path.write_text("[demo]\nvalue='x'\n", encoding="utf-8")

    monkeypatch.setattr(setup, "setup_rogkit_toml", _create)

    result = setup._ensure_config(apply=True)

    assert calls["created"] == 1
    assert result.status == "changed"
    assert config_path.exists()


def test_ensure_shell_profile_preview(monkeypatch, tmp_path):
    profile_path = tmp_path / ".zshrc"
    monkeypatch.setattr(setup, "ALIASES_PATH", tmp_path / "aliases")

    result = setup._ensure_shell_profile(
        apply=False,
        explicit_profile=profile_path,
        shell_name="zsh",
    )

    assert result.status == "warn"
    assert "would be updated" in result.summary.lower()


def test_ensure_shell_profile_apply_is_idempotent(monkeypatch, tmp_path):
    profile_path = tmp_path / ".zshrc"
    aliases_path = tmp_path / "aliases"
    aliases_path.write_text("# aliases\n", encoding="utf-8")
    monkeypatch.setattr(setup, "ALIASES_PATH", aliases_path)

    first = setup._ensure_shell_profile(
        apply=True,
        explicit_profile=profile_path,
        shell_name="zsh",
    )
    second = setup._ensure_shell_profile(
        apply=True,
        explicit_profile=profile_path,
        shell_name="zsh",
    )

    content = profile_path.read_text(encoding="utf-8")
    assert first.status == "changed"
    assert second.status == "ok"
    assert content.count(str(aliases_path)) == 1


def test_run_setup_can_skip_sections():
    args = setup.argparse.Namespace(
        apply=False,
        shell_profile=None,
        skip_shell=True,
        skip_config=True,
    )

    assert setup.run_setup(args) == []
