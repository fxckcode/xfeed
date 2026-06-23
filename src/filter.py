"""Keyword-based tweet filtering."""

from __future__ import annotations

from typing import Any


def is_tech_tweet(tweet_text: str, keywords: list[str]) -> bool:
    """Check if *tweet_text* contains any of the given *keywords* (case-insensitive).

    Args:
        tweet_text: The tweet's text content.
        keywords: Case-insensitive keywords to match against.

    Returns:
        True if at least one keyword appears in the text.
    """
    lowered = tweet_text.lower()
    return any(kw.lower() in lowered for kw in keywords)


def filter_tweets(tweets: list[dict[str, Any]], keywords: list[str]) -> list[dict[str, Any]]:
    """Return only tweets whose ``text`` field matches at least one *keyword*.

    Args:
        tweets: List of tweet dictionaries (must have a ``text`` key).
        keywords: Keywords to filter by (case-insensitive).

    Returns:
        Filtered list of matching tweet dicts.
    """
    return [t for t in tweets if is_tech_tweet(t["text"], keywords)]
