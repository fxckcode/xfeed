"""Shared fixtures for xfeed tests."""

from __future__ import annotations

from typing import Any

import pytest


@pytest.fixture
def sample_tweets() -> list[dict[str, Any]]:
    return [
        {
            "id": "123",
            "author": "testuser",
            "text": "Check out this new AI tool!",
            "hashtags": ["#AI"],
            "links": ["https://example.com/tool"],
            "source": "timeline",
            "created_at": "2026-06-23T10:00:00Z",
            "url": "https://x.com/test/123",
            "author_display": "Test User",
            "mentions": [],
            "is_reply": False,
            "is_retweet": False,
            "media_type": None,
        },
    ]
