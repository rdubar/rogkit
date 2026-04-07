"""Tests for strike.py — Unicode strikethrough formatter."""

from rogkit_package.bin.strike import strikethru


def test_every_char_has_combining_mark():
    result = strikethru("hello")
    # Each character is preceded by U+0336 COMBINING LONG STROKE OVERLAY
    assert result.count("\u0336") == len("hello")


def test_output_contains_original_chars():
    result = strikethru("abc")
    for char in "abc":
        assert char in result


def test_empty_string():
    assert strikethru("") == ""


def test_spaces_handled():
    result = strikethru("a b")
    assert "\u0336" in result
    assert "a" in result
    assert "b" in result


def test_length_is_double():
    # Each input char produces 2 output chars (combiner + char)
    text = "hello"
    result = strikethru(text)
    assert len(result) == len(text) * 2
