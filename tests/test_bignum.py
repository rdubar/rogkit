"""Tests for bignum.py — large number formatting and conversion."""

from rogkit_package.bin.bignum import PrettyNumberFormatter, bignum, seconds_time


class TestPrettyNumber:
    def test_integer_with_commas(self):
        f = PrettyNumberFormatter()
        assert f.prettynumber(1234567) == "1,234,567"

    def test_string_digit_input(self):
        f = PrettyNumberFormatter()
        assert f.prettynumber("9999") == "9,999"

    def test_small_number_unchanged(self):
        f = PrettyNumberFormatter()
        assert f.prettynumber(42) == "42"


class TestZillions:
    def test_million(self):
        result = bignum(1_000_000)
        assert "million" in result

    def test_billion(self):
        result = bignum(1_000_000_000)
        assert "billion" in result

    def test_trillion(self):
        result = bignum(1e12)
        assert "trillion" in result

    def test_below_minimum_returns_input(self):
        # Default minimum is 1000 — numbers below that pass through unchanged
        result = bignum(500, minimum=1000)
        assert result == 500

    def test_scientific_notation_string(self):
        result = bignum("1e+12")
        assert "trillion" in result

    def test_zero_returns_none(self):
        f = PrettyNumberFormatter()
        assert f.zillions(0) is None

    def test_invalid_string_returns_input(self):
        result = bignum("not-a-number")
        assert result == "not-a-number"


class TestSecondsTime:
    def test_one_minute(self):
        result = seconds_time(60)
        assert "minute" in result

    def test_one_hour(self):
        result = seconds_time(3600)
        assert "hour" in result

    def test_one_day(self):
        result = seconds_time(86400)
        assert "day" in result

    def test_granularity_limits_parts(self):
        # 1 year + 1 month + 1 week + …  but granularity=1 should give just years
        result = seconds_time(365 * 86400 + 30 * 86400, granularity=1)
        assert "," not in result
