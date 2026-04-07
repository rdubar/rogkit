"""Tests for rounder.py — decimal rounding with minimal trailing zeros."""

from rogkit_package.bin.rounder import round_decimals


def test_integer_value_returns_no_decimal():
    assert round_decimals(5.0, 2) == "5"


def test_rounds_to_max_decimals():
    assert round_decimals(3.14159, 2) == "3.14"


def test_strips_trailing_zeros():
    assert round_decimals(1.50, 2) == "1.5"


def test_exact_zero_decimals_stripped():
    assert round_decimals(2.00, 3) == "2"


def test_negative_handled():
    # round_decimals uses int(value) check; -3.0 == -3 so it strips decimals
    assert round_decimals(-3.0, 2) == "-3"


def test_small_fraction():
    assert round_decimals(0.125, 3) == "0.125"


def test_large_max_decimals_still_strips():
    assert round_decimals(1.1, 5) == "1.1"
