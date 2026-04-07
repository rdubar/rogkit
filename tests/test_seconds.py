"""Tests for seconds.py — time conversion utilities."""

from rogkit_package.bin.seconds import hms_string, convert_seconds, time_ago_in_words


class TestHmsString:
    def test_one_hour(self):
        assert hms_string(3600) == "01:00:00"

    def test_one_minute(self):
        assert hms_string(60) == "00:01:00"

    def test_mixed(self):
        assert hms_string(3665) == "01:01:05"

    def test_zero(self):
        assert hms_string(0) == "00:00:00"


class TestConvertSeconds:
    def test_below_minimum_returns_fractional_seconds(self):
        result = convert_seconds(1, minimum=2)
        assert "second" in result

    def test_one_minute(self):
        result = convert_seconds(60)
        assert "minute" in result

    def test_one_hour(self):
        result = convert_seconds(3600)
        assert "hour" in result

    def test_one_day(self):
        result = convert_seconds(86400)
        assert "day" in result

    def test_one_year(self):
        result = convert_seconds(31_557_600)
        assert "year" in result

    def test_compound_duration(self):
        result = convert_seconds(3665)
        assert "hour" in result
        assert "minute" in result

    def test_zero_below_minimum_returns_fractional(self):
        # 0 is below the default minimum of 2, so it shows as "0.000000 seconds"
        result = convert_seconds(0)
        assert "second" in result

    def test_no_commas_flag(self):
        result = convert_seconds(3600 * 1000, no_commas=True)
        assert "," not in result


class TestTimeAgoInWords:
    def test_one_minute_ago(self):
        result = time_ago_in_words(60)
        assert "ago" in result
        assert "minute" in result

    def test_negative_raises(self):
        import pytest
        with pytest.raises(ValueError):
            time_ago_in_words(-1)
