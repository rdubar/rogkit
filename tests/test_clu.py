"""Tests for clu."""

from rogkit_package.bin.clu import main, TokenTotals, _print_table


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


def test_print_table_plain_outputs_no_box_drawing(capsys):
    totals = TokenTotals()
    totals.add({"input_tokens": 10, "output_tokens": 5})
    _print_table("Today's usage", totals, "cyan", plain=True)
    out = capsys.readouterr().out
    assert "Input" in out
    assert "10" in out
    assert "─" not in out
