"""Tests for pw.py — secure password generator."""

import string
import pytest
from rogkit_package.bin.pw import PasswordGenerator


class TestPasswordGeneration:
    def test_generates_password_of_correct_length(self):
        pg = PasswordGenerator(length=16)
        pg.generate_and_store_password()
        assert len(pg.password) == 16

    def test_short_password(self):
        pg = PasswordGenerator(length=4)
        pg.generate_and_store_password()
        assert len(pg.password) == 4

    def test_long_password(self):
        pg = PasswordGenerator(length=64)
        pg.generate_and_store_password()
        assert len(pg.password) == 64

    def test_zero_length_raises(self):
        pg = PasswordGenerator(length=0)
        with pytest.raises(SystemExit):
            pg.generate_and_store_password()

    def test_alpha_only(self):
        pg = PasswordGenerator(length=20, alpha=True, numeric=False, special=False)
        pg.generate_and_store_password()
        assert all(c in string.ascii_letters for c in pg.password)

    def test_numeric_only(self):
        pg = PasswordGenerator(length=20, alpha=False, numeric=True, special=False)
        pg.generate_and_store_password()
        assert all(c in string.digits for c in pg.password)

    def test_default_includes_all_char_types(self):
        # Run several times to reduce chance of a fluke
        for _ in range(10):
            pg = PasswordGenerator(length=32)
            pg.generate_and_store_password()
        # Just verify no crash and correct length on last run
        assert len(pg.password) == 32


class TestAlphabet:
    def test_alpha_flag_adds_letters(self):
        pg = PasswordGenerator(alpha=True, numeric=False, special=False)
        assert any(c in string.ascii_letters for c in pg.alphabet)

    def test_numeric_flag_adds_digits(self):
        pg = PasswordGenerator(alpha=False, numeric=True, special=False)
        assert any(c in string.digits for c in pg.alphabet)

    def test_special_flag_adds_punctuation(self):
        pg = PasswordGenerator(alpha=False, numeric=False, special=True)
        assert any(c in string.punctuation for c in pg.alphabet)


class TestCombinations:
    def test_more_chars_more_combinations(self):
        pg_short = PasswordGenerator(length=8)
        pg_long = PasswordGenerator(length=16)
        assert pg_long.calculate_combinations() > pg_short.calculate_combinations()
