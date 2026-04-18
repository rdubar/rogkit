"""Tests for clu."""

from rogkit_package.bin.clu import main, TokenTotals


def test_clu_runs():
    """Smoke test: tool imports and main is callable."""
    assert callable(main)


def test_token_totals_add():
    t = TokenTotals()
    t.add({"input_tokens": 10, "output_tokens": 5, "cache_read_input_tokens": 100, "cache_creation_input_tokens": 20})
    assert t.input == 10
    assert t.output == 5
    assert t.cache_read == 100
    assert t.cache_write == 20
    assert t.total == 135
    assert t.messages == 1


def test_token_totals_missing_keys():
    t = TokenTotals()
    t.add({})
    assert t.total == 0
