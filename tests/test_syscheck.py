import builtins

from rogkit_package.bin import syscheck


def _stub_metrics(monkeypatch):
    monkeypatch.setattr(syscheck, "get_uptime", lambda _platform_type: 0.0)
    monkeypatch.setattr(syscheck, "get_load_averages", lambda _platform_type: (0.0, 0.0, 0.0))
    monkeypatch.setattr(
        syscheck,
        "get_memory_info",
        lambda _platform_type: {
            "total_mem": 1,
            "used_mem": 0,
            "free_mem": 1,
            "total_swap": 1,
            "used_swap": 0,
        },
    )
    monkeypatch.setattr(syscheck, "needrestart_status", lambda: None)
    monkeypatch.setattr(syscheck, "kernel_update_status", lambda _platform_type: None)
    monkeypatch.setattr(syscheck, "last_boot", lambda: None)
    monkeypatch.setattr(syscheck, "render_report", lambda _data: None)


def test_free_does_not_execute_without_confirm_non_interactive(monkeypatch):
    calls = {"free": 0}

    _stub_metrics(monkeypatch)
    monkeypatch.setattr(syscheck, "get_platform", lambda: "linux")
    monkeypatch.setattr(syscheck, "free_system_resources", lambda _platform_type: calls.__setitem__("free", calls["free"] + 1))
    monkeypatch.setattr(syscheck.sys.stdin, "isatty", lambda: False)
    monkeypatch.setattr(syscheck.argparse.ArgumentParser, "parse_args", lambda _self: syscheck.argparse.Namespace(free=True, confirm=False, json=False))

    syscheck.main()

    assert calls["free"] == 0


def test_free_executes_with_confirm(monkeypatch):
    calls = {"free": 0}

    _stub_metrics(monkeypatch)
    monkeypatch.setattr(syscheck, "get_platform", lambda: "linux")
    monkeypatch.setattr(syscheck, "free_system_resources", lambda _platform_type: calls.__setitem__("free", calls["free"] + 1))
    monkeypatch.setattr(syscheck.argparse.ArgumentParser, "parse_args", lambda _self: syscheck.argparse.Namespace(free=True, confirm=True, json=False))

    syscheck.main()

    assert calls["free"] == 1


def test_free_executes_when_prompt_confirmed(monkeypatch):
    calls = {"free": 0}

    _stub_metrics(monkeypatch)
    monkeypatch.setattr(syscheck, "get_platform", lambda: "linux")
    monkeypatch.setattr(syscheck, "free_system_resources", lambda _platform_type: calls.__setitem__("free", calls["free"] + 1))
    monkeypatch.setattr(syscheck.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(builtins, "input", lambda _prompt: "y")
    monkeypatch.setattr(syscheck.argparse.ArgumentParser, "parse_args", lambda _self: syscheck.argparse.Namespace(free=True, confirm=False, json=False))

    syscheck.main()

    assert calls["free"] == 1
