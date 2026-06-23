"""Tests for state persistence and helpers."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from src.scraper import Tweet
from src.state import (
    DEFAULT_STATE,
    count_new_tweets,
    is_new,
    load_state,
    save_state,
    update_state,
)


def test_load_state_existing_file(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    data = {"last_run": "2026-01-01T00:00:00", "seen_ids": ["1", "2"], "last_timeline_id": "2"}
    with open(state_path, "w") as f:
        json.dump(data, f)

    state = load_state(str(state_path))
    assert state["last_run"] == "2026-01-01T00:00:00"
    assert state["seen_ids"] == ["1", "2"]


def test_load_state_missing_file_returns_default(tmp_path: Path) -> None:
    state_path = tmp_path / "nonexistent.json"
    state = load_state(str(state_path))
    assert state == DEFAULT_STATE


def test_is_new_with_unseen_id() -> None:
    state: dict = {"seen_ids": ["1", "2", "3"]}
    assert is_new("4", state)
    assert is_new("999", state)


def test_is_new_with_seen_id() -> None:
    state: dict = {"seen_ids": ["1", "2", "3"]}
    assert not is_new("1", state)
    assert not is_new("3", state)


def test_update_state_adds_new_ids() -> None:
    state: dict = {"seen_ids": ["1"], "last_timeline_id": None, "last_run": None}
    tweets = [
        Tweet(
            id="2",
            url="https://x.com/u/2",
            author="u2",
            author_display="User 2",
            text="Hello",
            created_at="2026-06-23T10:00:00Z",
            source="timeline",
        ),
        Tweet(
            id="3",
            url="https://x.com/u/3",
            author="u3",
            author_display="User 3",
            text="World",
            created_at="2026-06-23T11:00:00Z",
            source="timeline",
        ),
    ]

    new_state = update_state(state, tweets)

    assert "1" in new_state["seen_ids"]
    assert "2" in new_state["seen_ids"]
    assert "3" in new_state["seen_ids"]
    assert new_state["last_timeline_id"] == "3"


def test_update_state_updates_timestamps() -> None:
    state: dict = {"seen_ids": [], "last_run": None, "last_timeline_id": None}
    tweets = [
        Tweet(
            id="1",
            url="https://x.com/u/1",
            author="u",
            author_display="U",
            text="hi",
            created_at="2026-06-23T10:00:00Z",
            source="timeline",
        ),
    ]

    new_state = update_state(state, tweets)
    assert new_state["last_run"] is not None
    # Valid ISO timestamp should parse without error
    datetime.fromisoformat(new_state["last_run"])


def test_save_state_writes_valid_json(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    state: dict = {
        "seen_ids": ["a", "b"],
        "last_run": "2026-06-23T12:00:00+00:00",
        "last_timeline_id": "b",
    }

    save_state(str(state_path), state)

    assert state_path.exists()
    with open(state_path) as f:
        loaded = json.load(f)
    assert loaded == state


def test_count_new_tweets_returns_length() -> None:
    state: dict = {"seen_ids": ["1", "2", "3"]}
    assert count_new_tweets(state) == 3
