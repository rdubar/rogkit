"""Tests for generations.py — genealogy calculator."""

import pytest
from rogkit_package.bin.generations import calculate_dna_shared, parent_name


class TestCalculateDnaShared:
    def test_first_generation_fifty_percent(self):
        percentages = calculate_dna_shared(1)
        assert percentages[0] == pytest.approx(50.0)

    def test_second_generation_twenty_five_percent(self):
        percentages = calculate_dna_shared(2)
        assert percentages[1] == pytest.approx(25.0)

    def test_halves_each_generation(self):
        percentages = calculate_dna_shared(5)
        for i in range(1, len(percentages)):
            assert percentages[i] == pytest.approx(percentages[i - 1] / 2)

    def test_returns_correct_count(self):
        percentages = calculate_dna_shared(10)
        assert len(percentages) == 10


class TestParentName:
    def test_generation_1_is_parent(self):
        assert parent_name(1) == "Parent"

    def test_generation_2_is_grandparent(self):
        assert parent_name(2) == "Grandparent"

    def test_generation_3_is_great_1_grandparent(self):
        assert "Great" in parent_name(3)

    def test_generation_4_is_great_2_grandparent(self):
        name = parent_name(4)
        assert "Great-2" in name
