"""Tests for bytes.py — human-readable byte size conversion."""

import pytest
from rogkit_package.bin.bytes import byte_size


class TestAutoUnit:
    def test_gigabytes(self):
        assert byte_size(1_234_567_890) == "1.23 GB"

    def test_megabytes(self):
        assert byte_size(1_234_567) == "1.23 MB"

    def test_kilobytes(self):
        assert byte_size(1_234) == "1.23 KB"

    def test_bytes_singular(self):
        assert byte_size(1) == "1 byte"

    def test_bytes_plural(self):
        assert byte_size(500) == "500 bytes"


class TestForcedUnit:
    def test_force_mb(self):
        result = byte_size(1_234_567_890, unit="MB")
        assert "MB" in result

    def test_force_gib_binary(self):
        result = byte_size(1_234_567_890, base=1024, unit="GiB")
        assert "GiB" in result

    def test_unknown_unit_raises(self):
        with pytest.raises(ValueError):
            byte_size(1000, unit="XB")


class TestBase:
    def test_base_1024_uses_gib_label(self):
        # Forcing GiB unit should show GiB label
        result = byte_size(1_073_741_824, base=1024, unit="GiB")
        assert "GiB" in result
        # 1 GiB (1024^3) should show as exactly 1.00
        value = float(result.split()[0].replace(",", ""))
        assert value == pytest.approx(1.0, rel=0.01)

    def test_invalid_base_raises(self):
        with pytest.raises(ValueError):
            byte_size(1000, base=512)
