"""Tests for primer.py - cold-start machine briefing."""

from __future__ import annotations

import subprocess

from rogkit_package.bin.primer import (
    _repo_status,
    _run_json,
    collect_disk,
    collect_notes,
    collect_repos,
    collect_media_mounts,
    collect_services,
    main,
)


def test_main_is_callable():
    assert callable(main)


def test_collect_disk_has_expected_keys():
    disk = collect_disk()
    assert {"total_bytes", "used_bytes", "free_bytes", "usage_pct"} <= disk.keys()
    assert disk["total_bytes"] > 0


def test_collect_repos_empty_when_root_missing(tmp_path):
    missing = tmp_path / "does-not-exist"
    assert collect_repos(root=missing) == []


def test_collect_repos_skips_clean_repos(tmp_path, monkeypatch):
    repo = tmp_path / "clean-repo"
    (repo / ".git").mkdir(parents=True)

    def fake_run(cmd, **kwargs):
        if "status" in cmd:
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="")

    monkeypatch.setattr("rogkit_package.bin.primer.subprocess.run", fake_run)
    assert collect_repos(root=tmp_path) == []


def test_repo_status_counts_dirty_files(tmp_path, monkeypatch):
    repo = tmp_path / "dirty-repo"
    repo.mkdir()

    def fake_run(cmd, **kwargs):
        if "status" in cmd:
            return subprocess.CompletedProcess(cmd, 0, stdout=" M a.py\n?? b.py\n", stderr="")
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="")

    monkeypatch.setattr("rogkit_package.bin.primer.subprocess.run", fake_run)
    info = _repo_status("dirty-repo", repo)
    assert info == {"name": "dirty-repo", "dirty": 2, "ahead": 0}


def test_collect_notes_empty_when_no_file(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "rogkit_package.bin.primer._get_notes_file", lambda: tmp_path / "notes.md"
    )
    assert collect_notes() == []


def test_run_json_returns_none_when_binary_missing(monkeypatch):
    monkeypatch.setattr("rogkit_package.bin.primer._sibling_binary", lambda name: None)
    assert _run_json("nonexistent-tool") is None


def test_run_json_returns_none_on_invalid_output(tmp_path, monkeypatch):
    monkeypatch.setattr("rogkit_package.bin.primer._sibling_binary", lambda name: "/bin/echo")
    monkeypatch.setattr(
        "rogkit_package.bin.primer.subprocess.run",
        lambda *a, **k: subprocess.CompletedProcess(a, 0, stdout="not json", stderr=""),
    )
    assert _run_json("echo") is None


def test_collect_services_reports_systemd_states(monkeypatch):
    monkeypatch.setattr("rogkit_package.bin.primer.platform.system", lambda: "Linux")
    monkeypatch.setattr("rogkit_package.bin.primer.shutil.which", lambda name: "/usr/bin/systemctl")

    def fake_run(cmd, **kwargs):
        status = "active\n" if cmd[-1] == "plexmediaserver" else "inactive\n"
        return subprocess.CompletedProcess(cmd, 0, stdout=status, stderr="")

    monkeypatch.setattr("rogkit_package.bin.primer.subprocess.run", fake_run)
    services = collect_services()
    assert services[0] == {"name": "plexmediaserver", "status": "active"}
    assert services[1]["status"] == "inactive"


def test_collect_media_mounts_includes_unmounted_targets(monkeypatch):
    monkeypatch.setattr("rogkit_package.bin.primer.platform.system", lambda: "Linux")
    monkeypatch.setattr("rogkit_package.bin.primer.shutil.which", lambda name: "/usr/bin/findmnt")
    monkeypatch.setattr(
        "rogkit_package.bin.primer.subprocess.run",
        lambda *a, **k: subprocess.CompletedProcess(
            a, 0, stdout="/mnt/media1 /dev/sda1 exfat rw,uid=1000\n", stderr=""
        ),
    )
    mounts = collect_media_mounts()
    assert mounts[0]["mounted"] is True
    assert mounts[0]["fstype"] == "exfat"
    assert mounts[1] == {"target": "/mnt/media2", "mounted": False}
