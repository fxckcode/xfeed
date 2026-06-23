"""Tests for keyword-based tweet filtering."""

from __future__ import annotations

from src.filter import is_tech_tweet


def test_normal_tech_tweet_returns_true() -> None:
    assert is_tech_tweet("Check out this new AI tool!", ["AI", "machine learning"])


def test_non_tech_tweet_returns_false() -> None:
    assert not is_tech_tweet("I just ate a great sandwich for lunch", ["AI", "tech", "startup"])


def test_case_insensitive() -> None:
    assert is_tech_tweet("I love AI tools", ["ai"])
    assert is_tech_tweet("I love ai tools", ["AI"])
    assert is_tech_tweet("MACHINE LEARNING is the future", ["Machine Learning"])


def test_empty_keywords_returns_false() -> None:
    assert not is_tech_tweet("This is a tech tweet", [])


def test_multiple_keywords_match_first() -> None:
    assert is_tech_tweet("Python is great for data science", ["AI", "Python", "Rust"])


def test_special_characters() -> None:
    assert is_tech_tweet("C++ is faster than Python?", ["C++"])
    assert is_tech_tweet("Check out $STONKS 📈", ["$STONKS"])
    assert is_tech_tweet("Elixir/Phoenix is 🔥", ["Phoenix"])
