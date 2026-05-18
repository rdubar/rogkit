"""Tests for _envsec.py - shared secret/placeholder helpers."""

from __future__ import annotations

from rogkit_package.bin._envsec import classify_value, is_secret_key, mask


def test_is_secret_key_obvious_names():
    assert is_secret_key("OPENAI_API_KEY")
    assert is_secret_key("STRIPE_SECRET_KEY")
    assert is_secret_key("DATABASE_URL")
    assert is_secret_key("JWT_SECRET")
    assert is_secret_key("GITHUB_TOKEN")
    assert is_secret_key("AWS_ACCESS_KEY_ID")
    assert is_secret_key("DB_PASSWORD")
    assert is_secret_key("PRIVATE_KEY")


def test_is_secret_key_case_insensitive():
    assert is_secret_key("openai_api_key")
    assert is_secret_key("Stripe_Secret_Key")


def test_is_secret_key_negative():
    assert not is_secret_key("PATH")
    assert not is_secret_key("HOME")
    assert not is_secret_key("EDITOR")
    assert not is_secret_key("SHELL")
    assert not is_secret_key("DEBUG")
    assert not is_secret_key("PORT")


def test_classify_empty():
    assert classify_value("") == "empty"


def test_classify_nullish():
    assert classify_value("null") == "placeholder"
    assert classify_value("NONE") == "placeholder"
    assert classify_value("nil") == "placeholder"


def test_classify_angle_brackets():
    assert classify_value("<your-key>") == "placeholder"
    assert classify_value("<changeme>") == "placeholder"


def test_classify_word_stubs():
    assert classify_value("xxx") == "placeholder"
    assert classify_value("changeme") == "placeholder"
    assert classify_value("your-api-key") == "placeholder"
    assert classify_value("TODO") == "placeholder"


def test_classify_real():
    assert classify_value("sk-abc123") == "set"
    assert classify_value("postgres://x:y@h/d") == "set"
    assert classify_value("8080") == "set"


def test_mask_returns_fixed_width():
    assert mask("anything") == "********"
    assert mask("a") == "********"


def test_mask_empty_stays_empty():
    assert mask("") == ""
