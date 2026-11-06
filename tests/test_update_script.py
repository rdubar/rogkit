"""Tests for the rogkit updater's self-update, run against throwaway git repos.

System package managers and uname are stubbed, so nothing real is upgraded and
the Debian path runs on any machine.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

UPDATE_SCRIPT = Path(__file__).parent.parent / "rogkit_package" / "bin" / "update"

STUBS = {
    "uname": "echo Linux",
    "sudo": "exit 0",
    "python3": "exit 0",
    "apt": 'if [ -n "$STUB_APT_UPGRADES" ] && [ "$1" = list ]; then echo "pkg/stable 2.0 arm64"; fi',
}


def _git(cwd: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)
    return result.stdout.strip()


def _commit(repo: Path, name: str, content: str) -> None:
    (repo / name).write_text(content)
    _git(repo, "add", name)
    _git(repo, "commit", "-m", f"change {name}")
    _git(repo, "push", "-q", "origin", "main")


class Sandbox:
    def __init__(self, root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        stubs = root / "stubs"
        stubs.mkdir()
        for name, body in STUBS.items():
            stub = stubs / name
            stub.write_text(f"#!/bin/sh\n{body}\n")
            stub.chmod(0o755)

        home = root / "home"
        home.mkdir()
        monkeypatch.setenv("PATH", f"{stubs}{os.pathsep}{os.environ['PATH']}")
        monkeypatch.setenv("HOME", str(home))
        monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
        monkeypatch.setenv("GIT_AUTHOR_NAME", "Test")
        monkeypatch.setenv("GIT_AUTHOR_EMAIL", "test@example.invalid")
        monkeypatch.setenv("GIT_COMMITTER_NAME", "Test")
        monkeypatch.setenv("GIT_COMMITTER_EMAIL", "test@example.invalid")
        monkeypatch.delenv("STUB_APT_UPGRADES", raising=False)

        origin = root / "origin.git"
        _git(root, "init", "-q", "--bare", "--initial-branch=main", str(origin))

        self.upstream = root / "upstream"
        _git(root, "clone", "-q", str(origin), str(self.upstream))
        _git(self.upstream, "checkout", "-q", "-B", "main")
        self.script = self.upstream / "rogkit_package" / "bin" / "update"
        self.script.parent.mkdir(parents=True)
        shutil.copy(UPDATE_SCRIPT, self.script)
        (self.upstream / "uv.lock").write_text("original\n")
        (self.upstream / ".gitignore").write_text("go/bin/\n")
        _git(self.upstream, "add", ".")
        _git(self.upstream, "commit", "-q", "-m", "initial")
        _git(self.upstream, "push", "-q", "-u", "origin", "main")

        self.checkout = root / "checkout"
        _git(root, "clone", "-q", str(origin), str(self.checkout))

    def incoming(self, name: str = "new.txt", content: str = "new\n") -> None:
        """Land a commit upstream that the checkout doesn't have yet."""
        _commit(self.upstream, name, content)

    def run(self, *args: str, answers: str | None = None) -> str:
        argv = ["bash", str(self.checkout / "rogkit_package" / "bin" / "update")]
        argv += list(args) if answers is not None else ["--yes", *args]
        result = subprocess.run(
            argv, input=answers or "", capture_output=True, text=True, check=True
        )
        return result.stdout + result.stderr

    def head(self) -> str:
        return _git(self.checkout, "rev-parse", "HEAD")

    def upstream_head(self) -> str:
        return _git(self.upstream, "rev-parse", "HEAD")


@pytest.fixture
def sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Sandbox:
    return Sandbox(tmp_path, monkeypatch)


def _attention(output: str) -> str:
    """The end-of-run summary, or "" if there wasn't one."""
    _, found, after = output.partition("==> Needs attention")
    return after if found else ""


def test_clean_checkout_pulls(sandbox: Sandbox) -> None:
    sandbox.incoming()
    output = sandbox.run()
    assert sandbox.head() == sandbox.upstream_head()
    assert _attention(output) == ""


def test_up_to_date_has_nothing_to_report(sandbox: Sandbox) -> None:
    output = sandbox.run()
    assert "(up to date)" in output
    assert _attention(output) == ""


def test_unrelated_local_change_does_not_block_pull(sandbox: Sandbox) -> None:
    """The bug: a stray uv.lock edit left the Pi 14 commits behind for weeks."""
    (sandbox.checkout / "uv.lock").write_text("bumped locally\n")
    sandbox.incoming()

    output = sandbox.run()

    assert sandbox.head() == sandbox.upstream_head()
    assert (sandbox.checkout / "new.txt").exists()
    assert (sandbox.checkout / "uv.lock").read_text() == "bumped locally\n"
    assert "Local changes (kept):" in output
    assert _attention(output) == ""


def test_conflicting_local_change_is_kept_and_reported_at_the_end(sandbox: Sandbox) -> None:
    (sandbox.checkout / "uv.lock").write_text("bumped locally\n")
    sandbox.incoming("uv.lock", "bumped upstream\n")
    before = sandbox.head()

    output = sandbox.run()

    assert sandbox.head() == before
    assert (sandbox.checkout / "uv.lock").read_text() == "bumped locally\n"
    assert "1 commit(s) behind: pull failed" in _attention(output)


def test_declined_pull_is_reported(sandbox: Sandbox) -> None:
    sandbox.incoming()
    before = sandbox.head()
    output = sandbox.run(answers="n\n")
    assert sandbox.head() == before
    assert "1 commit(s) behind: pull skipped" in _attention(output)


def test_summary_survives_aborting_the_package_upgrade(
    sandbox: Sandbox, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("STUB_APT_UPGRADES", "1")
    sandbox.incoming()
    output = sandbox.run(answers="n\nn\n")
    assert "Aborted." in output
    assert "pull skipped" in _attention(output)
