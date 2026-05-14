"""Tests for clipboard.py."""

from rogkit_package.bin import clipboard


def test_copy_to_clipboard_returns_false_when_pyclip_missing(monkeypatch, capsys):
    monkeypatch.setattr(clipboard, "PYCLIP_AVAILABLE", False)

    assert clipboard.copy_to_clipboard("secret", verbose=True) is False

    output = capsys.readouterr().out
    assert "pyclip not installed" in output
    assert "secret" in output


def test_copy_to_clipboard_returns_true_on_success(monkeypatch):
    copied = []

    class FakePyclip:
        @staticmethod
        def copy(text: str) -> None:
            copied.append(text)

    monkeypatch.setattr(clipboard, "PYCLIP_AVAILABLE", True)
    monkeypatch.setattr(clipboard, "pyclip", FakePyclip)

    assert clipboard.copy_to_clipboard("secret", verbose=False) is True
    assert copied == ["secret"]


def test_copy_to_clipboard_returns_false_on_backend_failure(monkeypatch, capsys):
    class FakePyclip:
        @staticmethod
        def copy(text: str) -> None:
            raise RuntimeError("Could not setup clipboard")

    monkeypatch.setattr(clipboard, "PYCLIP_AVAILABLE", True)
    monkeypatch.setattr(clipboard, "pyclip", FakePyclip)
    monkeypatch.setattr(clipboard.sys, "platform", "linux")

    assert clipboard.copy_to_clipboard("secret", verbose=False) is False

    output = capsys.readouterr().out
    assert "Could not copy to clipboard" in output
    assert "wl-clipboard" in output
