"""Tests for awake."""

import argparse
import json

import pytest

from rogkit_package.bin import awake
from rogkit_package.bin.awake import (
    Hold,
    annotate,
    fmt_seconds,
    main,
    parse_args,
    parse_duration,
    parse_logind_inhibitors,
    parse_pmset_assertions,
)

PMSET_SAMPLE = """\
2026-11-05 07:36:25 +0000
Assertion status system-wide:
   PreventUserIdleSystemSleep     1
Listed by owning process:
   pid 98337(caffeinate): [0x0007e6a200018844] 09:09:05 PreventUserIdleSystemSleep named: "caffeinate command-line tool"
\tDetails: caffeinate asserting forever
\tLocalized=THE CAFFEINATE TOOL IS PREVENTING SLEEP.
   pid 98337(caffeinate): [0x0007e6a200078845] 09:09:05 PreventSystemSleep named: "caffeinate command-line tool"
   pid 768(sharingd): [0x000866ba00019854] 00:02:33 PreventUserIdleSystemSleep named: "Handoff"
   pid 354(powerd): [0x0008656300019811] 00:08:16 PreventUserIdleSystemSleep named: "Powerd - Prevent sleep while display is on"
   pid 411(WindowServer): [0x0008656300099810] 00:00:09 UserIsActive named: "com.apple.iohideventsystem.queue.tickle"
\tTimeout will fire in 110 secs Action=TimeoutActionRelease
No kernel assertions.
"""


def test_awake_runs():
    """Smoke test: tool imports and main is callable."""
    assert callable(main)


def test_parse_pmset_assertions():
    rows = parse_pmset_assertions(PMSET_SAMPLE)
    assert [(r.pid, r.process, r.kind) for r in rows] == [
        (98337, "caffeinate", "PreventUserIdleSystemSleep"),
        (98337, "caffeinate", "PreventSystemSleep"),
        (768, "sharingd", "PreventUserIdleSystemSleep"),
        (354, "powerd", "PreventUserIdleSystemSleep"),
        (411, "WindowServer", "UserIsActive"),
    ]
    assert rows[0].age == "09:09:05"
    assert rows[0].details[0] == "Details: caffeinate asserting forever"
    assert rows[2].name == "Handoff"
    assert rows[4].blocking is False
    assert rows[0].blocking is True


def test_parse_logind_inhibitors():
    payload = {
        "type": "a(ssssuu)",
        "data": [
            [
                [
                    "sleep",
                    "NetworkManager",
                    "NM needs to turn off networks",
                    "delay",
                    0,
                    812,
                ],
                ["idle:sleep", "rogkit awake", "rsync", "block", 1000, 4242],
            ]
        ],
    }
    rows = parse_logind_inhibitors(json.dumps(payload))
    assert [(r.pid, r.blocking) for r in rows] == [(812, False), (4242, True)]
    assert parse_logind_inhibitors("not json") == []


def test_annotate_marks_ours_and_tty(monkeypatch):
    monkeypatch.setattr(awake, "proc_parent", lambda pid: "launched by test")
    rows = parse_pmset_assertions(PMSET_SAMPLE)
    rows.append(
        awake.Assertion(
            pid=1,
            process="powerd",
            kind="PreventUserIdleSystemSleep",
            name="com.apple.ttyassertion",
        )
    )
    hold = Hold(id="ab12", label="x", pid=98337, started=0)
    annotate(rows, [hold])
    assert rows[0].ours == "ab12" and rows[1].ours == "ab12"
    assert "SSH" in rows[-1].note
    assert "display is on" in rows[3].note


@pytest.mark.parametrize(
    ("text", "seconds"),
    [("90", 90), ("45m", 2700), ("2h", 7200), ("1h30m", 5400), ("1d", 86400)],
)
def test_parse_duration(text, seconds):
    assert parse_duration(text) == seconds


def test_parse_duration_rejects_junk():
    with pytest.raises(argparse.ArgumentTypeError):
        parse_duration("soon")


def test_fmt_seconds():
    assert fmt_seconds(42) == "42s"
    assert fmt_seconds(3900) == "1h05m"


def test_default_subcommand_is_list():
    assert parse_args([]).command == "list"
    assert parse_args(["-a"]).all is True
    args = parse_args(["run", "-l", "sync", "--", "rsync", "-a"])
    assert args.label == "sync" and args.argv[-2:] == ["rsync", "-a"]


def test_load_holds_prunes_dead(tmp_path, monkeypatch):
    monkeypatch.setattr(awake, "STATE_DIR", tmp_path)
    awake.save_hold(Hold(id="dead", label="gone", pid=999_999, started=0))
    monkeypatch.setattr(awake, "is_our_holder", lambda pid: False)
    assert awake.load_holds() == []
    assert not (tmp_path / "dead.json").exists()


def test_purge_refuses_without_tty_or_yes(monkeypatch):
    target = awake.Purgeable(
        pid=4242,
        user="me",
        command="caffeinate -i",
        ppid=1,
        parent="(detached)",
        children=[],
    )
    monkeypatch.setattr(awake, "load_holds", lambda: [])
    monkeypatch.setattr(awake, "find_purgeable", lambda holds: [target])
    monkeypatch.setattr(awake, "system_assertions", lambda: [])
    monkeypatch.setattr(awake, "_run", lambda cmd: "me\n")
    monkeypatch.setattr(awake.sys.stdin, "isatty", lambda: False)
    killed = []
    monkeypatch.setattr(awake.os, "kill", lambda pid, sig: killed.append(pid))
    with pytest.raises(SystemExit):
        awake.cmd_purge(argparse.Namespace(yes=False))
    assert killed == []


def test_purge_never_targets_other_users(monkeypatch):
    target = awake.Purgeable(
        pid=4242,
        user="root",
        command="caffeinate -i",
        ppid=1,
        parent="(detached)",
        children=[],
    )
    monkeypatch.setattr(awake, "load_holds", lambda: [])
    monkeypatch.setattr(awake, "find_purgeable", lambda holds: [target])
    monkeypatch.setattr(awake, "system_assertions", lambda: [])
    monkeypatch.setattr(awake, "_run", lambda cmd: "me\n")
    killed = []
    monkeypatch.setattr(awake.os, "kill", lambda pid, sig: killed.append(pid))
    assert awake.cmd_purge(argparse.Namespace(yes=True)) == 0
    assert killed == []


@pytest.mark.parametrize("reply", ["n", "", EOFError])
def test_purge_declined_kills_nothing(monkeypatch, reply):
    target = awake.Purgeable(
        pid=4242,
        user="me",
        command="caffeinate -i",
        ppid=1,
        parent="(detached)",
        children=[],
    )
    monkeypatch.setattr(awake, "load_holds", lambda: [])
    monkeypatch.setattr(awake, "find_purgeable", lambda holds: [target])
    monkeypatch.setattr(awake, "system_assertions", lambda: [])
    monkeypatch.setattr(awake, "_run", lambda cmd: "me\n")
    monkeypatch.setattr(awake.sys.stdin, "isatty", lambda: True)

    def fake_input(prompt):
        if reply is EOFError:
            raise EOFError
        return reply

    monkeypatch.setattr("builtins.input", fake_input)
    killed = []
    monkeypatch.setattr(awake.os, "kill", lambda pid, sig: killed.append(pid))
    assert awake.cmd_purge(argparse.Namespace(yes=False)) == 1
    assert killed == []
