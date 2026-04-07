"""Tests for dice.py — dice rolling utility."""

from rogkit_package.bin.dice import throw_dice


def test_returns_list():
    result = throw_dice(1, 6)
    assert isinstance(result, list)


def test_correct_number_of_dice():
    result = throw_dice(3, 6)
    assert len(result) == 3


def test_values_in_range():
    for _ in range(100):
        result = throw_dice(1, 6)
        assert 1 <= result[0] <= 6


def test_custom_sides():
    for _ in range(50):
        result = throw_dice(1, 20)
        assert 1 <= result[0] <= 20


def test_single_side_always_returns_one():
    result = throw_dice(5, 1)
    assert all(v == 1 for v in result)


def test_many_dice():
    result = throw_dice(10, 6)
    assert len(result) == 10
    assert all(1 <= v <= 6 for v in result)
