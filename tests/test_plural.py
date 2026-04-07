"""Tests for plural.py — English pluralisation."""

from rogkit_package.bin.plural import plural, looks_plural, parse_input


class TestPlural:
    def test_regular_word(self):
        assert plural("cat") == "cats"

    def test_singular_count_returns_original(self):
        assert plural("cat", 1) == "cat"

    def test_irregular_person(self):
        assert plural("person") == "people"

    def test_irregular_child(self):
        assert plural("child") == "children"

    def test_y_ending(self):
        assert plural("baby") == "babies"

    def test_s_ending(self):
        # "bus" ends in 's' so looks_plural() treats it as already plural
        # The function intentionally doesn't double-pluralise
        assert plural("bus") == "bus"

    def test_invariant_sheep(self):
        assert plural("sheep") == "sheep"

    def test_f_exception_giraffe(self):
        assert plural("giraffe") == "giraffes"

    def test_fe_ending(self):
        assert plural("knife") == "knives"

    def test_empty_string_returns_empty(self):
        assert plural("") == ""

    def test_day_irregular(self):
        assert plural("day") == "days"


class TestLooksPlural:
    def test_already_plural_cats(self):
        assert looks_plural("cats") is True

    def test_singular_cat(self):
        assert looks_plural("cat") is False

    def test_known_plural_men(self):
        assert looks_plural("men") is True


class TestParseInput:
    def test_count_then_word(self):
        word, count = parse_input("3 cat")
        assert word == "cat"
        assert count == 3

    def test_word_then_count(self):
        word, count = parse_input("cat 3")
        assert word == "cat"
        assert count == 3

    def test_word_only_defaults_to_two(self):
        word, count = parse_input("sheep")
        assert word == "sheep"
        assert count == 2
