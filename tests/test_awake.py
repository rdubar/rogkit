"""Tests for awake."""

import argparse
import json
import os
import signal
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

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
    with pytest.raises(awake.AwakeError):
        parse_logind_inhibitors("not json")


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


@pytest.mark.parametrize(
    "argv",
    [
        ["on", "--for", "0"],
        ["on", "--for", "0h0m"],
        ["on", "--while", "0"],
        ["on", "--while", "-1"],
    ],
)
def test_rejects_nonpositive_limits(argv: list[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        parse_args(argv)
    assert exc.value.code == 2


def test_limits_are_mutually_exclusive(monkeypatch) -> None:
    start = Mock()
    monkeypatch.setattr(awake, "start_hold", start)
    with pytest.raises(SystemExit, match="either"):
        awake.cmd_on(parse_args(["on", "--for", "1m", "--while", "123"]))
    start.assert_not_called()


@pytest.fixture
def recorded_hold() -> Hold:
    return Hold(
        id="ab12",
        label="test",
        pid=4242,
        started=0,
        boot_id="boot-a",
        process_start="start-a",
    )


@pytest.mark.parametrize("code, expected", [(0, 0), (7, 7), (-15, 143)])
def test_run_holds_before_launch_and_preserves_exit(
    monkeypatch,
    recorded_hold: Hold,
    code: int,
    expected: int,
) -> None:
    events = []

    def start(label: str, **kwargs) -> Hold:
        assert kwargs["while_pid"] == os.getpid()
        events.append("hold")
        return recorded_hold

    child = Mock(pid=123, wait=Mock(return_value=code))

    def launch(argv, **kwargs):
        events.append("command")
        return child

    monkeypatch.setattr(awake, "start_hold", start)
    monkeypatch.setattr(awake.subprocess, "Popen", launch)
    monkeypatch.setattr(awake, "stop_hold", lambda hold: events.append("release"))
    assert awake.cmd_run(parse_args(["run", "--", "example"])) == expected
    assert events == ["hold", "command", "release"]


def test_run_does_not_launch_without_hold(monkeypatch) -> None:
    monkeypatch.setattr(
        awake, "start_hold", Mock(side_effect=awake.AwakeError("no inhibitor"))
    )
    launch = Mock()
    monkeypatch.setattr(awake.subprocess, "Popen", launch)
    with pytest.raises(awake.AwakeError):
        awake.cmd_run(parse_args(["run", "--", "example"]))
    launch.assert_not_called()


def test_run_releases_hold_if_command_missing(monkeypatch, recorded_hold: Hold) -> None:
    monkeypatch.setattr(awake, "start_hold", lambda *a, **kw: recorded_hold)
    monkeypatch.setattr(
        awake.subprocess, "Popen", Mock(side_effect=FileNotFoundError("example"))
    )
    stop = Mock()
    monkeypatch.setattr(awake, "stop_hold", stop)
    with pytest.raises(FileNotFoundError):
        awake.cmd_run(parse_args(["run", "--", "example"]))
    stop.assert_called_once_with(recorded_hold)


def test_run_forwards_termination_before_releasing(
    monkeypatch, recorded_hold: Hold
) -> None:
    events = []
    handlers = {}

    def handler(sig, callback):
        previous = handlers.get(sig)
        handlers[sig] = callback
        return previous

    child = Mock(pid=123)

    def wait() -> int:
        handlers[signal.SIGTERM](signal.SIGTERM, None)
        events.append("exited")
        return -signal.SIGTERM

    child.wait.side_effect = wait
    child.send_signal.side_effect = lambda sig: events.append(sig)
    monkeypatch.setattr(awake.signal, "signal", handler)
    monkeypatch.setattr(awake, "start_hold", lambda *a, **kw: recorded_hold)
    monkeypatch.setattr(awake.subprocess, "Popen", lambda *a, **kw: child)
    monkeypatch.setattr(awake, "stop_hold", lambda hold: events.append("release"))
    assert awake.cmd_run(parse_args(["run", "--", "example"])) == 143
    assert events == [signal.SIGTERM, "exited", "release"]


def test_start_cleans_up_if_state_write_fails(tmp_path, monkeypatch) -> None:
    proc = Mock(pid=4242, poll=Mock(return_value=None))
    monkeypatch.setattr(awake, "STATE_DIR", tmp_path)
    monkeypatch.setattr(awake, "_holder_argv", lambda *a, **kw: ["holder"])
    monkeypatch.setattr(awake.subprocess, "Popen", lambda *a, **kw: proc)
    monkeypatch.setattr(awake.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(awake, "process_identity", lambda pid: ("boot", "start"))
    monkeypatch.setattr(awake, "save_hold", Mock(side_effect=OSError("disk full")))
    with pytest.raises(OSError, match="disk full"):
        awake.start_hold("test")
    proc.terminate.assert_called_once()
    proc.wait.assert_called_once()
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "payload",
    [
        {"data": [None]},
        {"data": [[[]]]},
        {"data": [[[None, "who", "why", "block", 0, 1]]]},
    ],
)
def test_malformed_inhibitor_response_is_not_empty(payload) -> None:
    with pytest.raises(awake.AwakeError):
        awake.parse_logind_inhibitors(json.dumps(payload))


def test_linux_identity_handles_process_names_with_parentheses(monkeypatch) -> None:
    monkeypatch.setattr(awake, "IS_MAC", False)
    monkeypatch.setattr(awake, "pid_alive", lambda pid: True)
    fields = ["S"] + ["0"] * 18 + ["123456"] + ["0"] * 10

    def read(path, *args, **kwargs) -> str:
        if path.name == "boot_id":
            return "boot-linux\n"
        return "4242 (holder (test)) " + " ".join(fields)

    monkeypatch.setattr(Path, "read_text", read)
    assert awake.process_identity(4242) == ("boot-linux", "123456")


def test_linux_holder_watches_pid(monkeypatch) -> None:
    monkeypatch.setattr(awake, "IS_MAC", False)
    monkeypatch.setattr(awake.shutil, "which", lambda name: "/usr/bin/" + name)
    argv = awake._holder_argv("test", seconds=None, while_pid=4242, display=False)
    assert argv[-4:] == ["tail", "--pid=4242", "-f", "/dev/null"]
    assert "--what=idle:sleep" in argv


@pytest.mark.skipif(not awake.IS_MAC, reason="native macOS lifecycle check")
def test_native_detached_hold_can_be_found_and_released(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(awake, "STATE_DIR", tmp_path)
    hold = awake.start_hold("native lifecycle test", seconds=5)
    try:
        assert awake.load_holds() == [hold]
        assertions = awake.system_assertions()
        awake.annotate(assertions, [hold])
        assert any(a.ours == hold.id for a in assertions)
    finally:
        assert awake.stop_hold(hold)
    assert list(tmp_path.iterdir()) == []


def test_atomic_state_write_keeps_old_record_visible(
    tmp_path, monkeypatch, recorded_hold: Hold
) -> None:
    monkeypatch.setattr(awake, "STATE_DIR", tmp_path)
    monkeypatch.setattr(awake, "is_our_holder", lambda hold: True)
    awake.save_hold(recorded_hold)
    replace = os.replace

    def observe(source, destination) -> None:
        assert awake.load_holds()[0].label == "test"
        assert json.loads(Path(source).read_text())["label"] == "updated"
        replace(source, destination)

    monkeypatch.setattr(awake.os, "replace", observe)
    recorded_hold.label = "updated"
    awake.save_hold(recorded_hold)
    assert awake.load_holds()[0].label == "updated"
    assert len(list(tmp_path.iterdir())) == 1


def test_load_tolerates_concurrent_removal(
    tmp_path, monkeypatch, recorded_hold: Hold
) -> None:
    monkeypatch.setattr(awake, "STATE_DIR", tmp_path)
    awake.save_hold(recorded_hold)
    monkeypatch.setattr(Path, "read_text", Mock(side_effect=FileNotFoundError))
    assert awake.load_holds() == []


@pytest.mark.parametrize(
    "identity", [("boot-b", "start-a"), ("boot-a", "start-b"), None]
)
def test_off_never_signals_reused_pid(
    monkeypatch, tmp_path, recorded_hold: Hold, identity
) -> None:
    monkeypatch.setattr(awake, "STATE_DIR", tmp_path)
    monkeypatch.setattr(awake, "process_identity", lambda pid: identity)
    monkeypatch.setattr(awake, "proc_comm", lambda pid: "caffeinate")
    kill = Mock()
    monkeypatch.setattr(awake.os, "kill", kill)
    assert awake.stop_hold(recorded_hold) is False
    kill.assert_not_called()


def test_off_signals_matching_identity(
    monkeypatch, tmp_path, recorded_hold: Hold
) -> None:
    monkeypatch.setattr(awake, "STATE_DIR", tmp_path)
    monkeypatch.setattr(awake, "process_identity", lambda pid: ("boot-a", "start-a"))
    monkeypatch.setattr(awake, "proc_comm", lambda pid: "caffeinate")
    kill = Mock()
    monkeypatch.setattr(awake.os, "kill", kill)
    assert awake.stop_hold(recorded_hold) is True
    kill.assert_called_once_with(recorded_hold.pid, signal.SIGTERM)


def test_legacy_records_are_not_claimed(monkeypatch) -> None:
    monkeypatch.setattr(awake, "proc_comm", lambda pid: "caffeinate")
    assert not awake.is_our_holder(Hold(id="old", label="legacy", pid=4242, started=0))


@pytest.mark.parametrize("json_output", [True, False])
def test_failed_queries_report_unknown(monkeypatch, capsys, json_output: bool) -> None:
    monkeypatch.setattr(awake, "load_holds", lambda: [])
    monkeypatch.setattr(
        awake,
        "system_assertions",
        Mock(side_effect=awake.AwakeError("bus unavailable")),
    )
    argv = ["status", "--json"] if json_output else ["status"]
    assert awake.cmd_list(parse_args(argv)) == 1
    output = capsys.readouterr().out
    if json_output:
        payload = json.loads(output)
        assert payload["assertions"] is None
        assert payload["error"] == "bus unavailable"
    else:
        assert "Unable to query" in output
        assert "none" not in output.lower().replace("our holds: none", "")


def test_remaining_does_not_claim_sleep_is_unblocked_on_failure(
    monkeypatch, capsys
) -> None:
    monkeypatch.setattr(
        awake, "system_assertions", Mock(side_effect=awake.AwakeError("query failed"))
    )
    with pytest.raises(awake.AwakeError):
        awake._show_remaining()
    assert "Nothing else" not in capsys.readouterr().out


@pytest.mark.parametrize(
    "failure",
    [
        subprocess.CompletedProcess(["busctl"], 1, "", "bus unavailable"),
        FileNotFoundError("busctl"),
        subprocess.TimeoutExpired("busctl", 10),
    ],
)
def test_required_queries_propagate_failures(monkeypatch, failure) -> None:
    run = Mock()
    if isinstance(failure, Exception):
        run.side_effect = failure
    else:
        run.return_value = failure
    monkeypatch.setattr(awake.subprocess, "run", run)
    with pytest.raises(awake.AwakeError):
        awake._run(["busctl"], required=True)


def test_purge_rechecks_identity_after_confirmation(monkeypatch) -> None:
    target = awake.Purgeable(
        4242, "me", "caffeinate -i", 1, "detached", [], identity=("boot", "old")
    )
    monkeypatch.setattr(awake, "load_holds", lambda: [])
    monkeypatch.setattr(awake, "find_purgeable", lambda holds: [target])
    monkeypatch.setattr(awake, "system_assertions", lambda: [])
    monkeypatch.setattr(awake, "_run", lambda cmd: "me\n")
    monkeypatch.setattr(awake, "process_identity", lambda pid: ("boot", "new"))
    monkeypatch.setattr(awake.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(awake.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda prompt: "yes")
    kill = Mock()
    monkeypatch.setattr(awake.os, "kill", kill)
    assert awake.cmd_purge(argparse.Namespace(yes=False)) == 0
    kill.assert_not_called()


@pytest.mark.skipif(not awake.IS_MAC, reason="native macOS lifecycle check")
@pytest.mark.parametrize("code", [0, 7])
def test_native_short_command_and_hold_cleanup(
    tmp_path, monkeypatch, code: int
) -> None:
    monkeypatch.setattr(awake, "STATE_DIR", tmp_path)
    assert (
        awake.cmd_run(
            parse_args(["run", "--", sys.executable, "-c", f"raise SystemExit({code})"])
        )
        == code
    )
    assert list(tmp_path.iterdir()) == []
