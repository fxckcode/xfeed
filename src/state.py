"""Application state persistence and helpers."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.scraper import Tweet

DEFAULT_STATE: dict[str, Any] = {
    "last_run": None,
    "seen_ids": [],
    "last_timeline_id": None,
    "last_bookmark_id": None,
    "last_like_id": None,
}


def load_state(path_str: str) -> dict[str, Any]:
    """Load JSON state from *path_str*, returning *DEFAULT_STATE* if missing."""
    path = Path(path_str)
    if not path.exists():
        return dict(DEFAULT_STATE)
    with path.open("r") as f:
        data: dict[str, Any] = json.load(f)
    return data


def save_state(path_str: str, state: dict[str, Any]) -> None:
    """Write *state* as pretty-printed JSON to *path_str*."""
    path = Path(path_str)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        json.dump(state, f, indent=2)
        f.write("\n")


def is_new(tweet_id: str, state: dict[str, Any]) -> bool:
    """Return ``True`` when *tweet_id* has not been seen yet."""
    return tweet_id not in state["seen_ids"]


def update_state(state: dict[str, Any], tweets: list[Tweet]) -> dict[str, Any]:
    """Merge *tweets* into *state* and return the updated copy.

    New tweet IDs are appended to ``seen_ids``, ``last_*_id`` values are
    updated per source, and ``last_run`` is set to the current UTC time.
    """
    seen: set[str] = set(state["seen_ids"])
    new_state = dict(state)

    for tweet in tweets:
        seen.add(tweet.id)
        source_key = f"last_{tweet.source}_id"
        if source_key in new_state:
            new_state[source_key] = tweet.id

    new_state["seen_ids"] = list(seen)

    new_state["last_run"] = datetime.now(UTC).isoformat()

    return new_state


def count_new_tweets(state: dict[str, Any]) -> int:
    """Return the total number of seen tweets (quick stats)."""
    return len(state["seen_ids"])
