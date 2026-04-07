"""Tests for catyears.py — cat age to human years conversion."""

from rogkit_package.bin.catyears import cat_age_to_human


def test_first_year_scales_linearly():
    # 12 months = 15 human years
    assert cat_age_to_human(1, 0) == 15


def test_six_months():
    # 6 months = 6/12 * 15 = 7.5 human years
    assert cat_age_to_human(0, 6) == 7.5


def test_two_years():
    # 2 years = 15 + 9 = 24 human years
    assert cat_age_to_human(2, 0) == 24


def test_three_years():
    # 3 years = 24 + 4 = 28 human years
    assert cat_age_to_human(3, 0) == 28


def test_ten_years():
    # 10 years = 24 + (8 * 4) = 56 human years
    assert cat_age_to_human(10, 0) == 56


def test_years_and_months_combined():
    # 2 years 6 months = 24 + (6/12 * 4) = 26 human years
    assert cat_age_to_human(2, 6) == 26


def test_integer_result_returned_as_int():
    result = cat_age_to_human(1, 0)
    assert isinstance(result, int)
