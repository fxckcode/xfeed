"""Tests for Obsidian markdown note generation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.obsidian_writer import write_feed_note

TweetList = list[dict[str, Any]]


def test_write_feed_note_creates_file(
    tmp_path: Path, sample_tweets: TweetList
) -> None:
    result = write_feed_note(sample_tweets, str(tmp_path), date_str="2026-06-23")
    expected_path = tmp_path / "X" / "Feed" / "2026-06-23.md"
    assert result == str(expected_path)
    assert expected_path.exists()


def test_frontmatter_has_required_fields(
    tmp_path: Path, sample_tweets: TweetList
) -> None:
    result_path = write_feed_note(sample_tweets, str(tmp_path), date_str="2026-06-23")
    content = Path(result_path).read_text()
    lines = content.split("\n")
    assert lines[0] == "---"
    end_idx = lines.index("---", 1)
    frontmatter = "\n".join(lines[1:end_idx])
    assert "title:" in frontmatter
    assert "tags:" in frontmatter
    assert "xfeed" in frontmatter
    assert "feed" in frontmatter


def test_tweet_entries_formatted_properly(
    tmp_path: Path, sample_tweets: TweetList
) -> None:
    result_path = write_feed_note(sample_tweets, str(tmp_path), date_str="2026-06-23")
    content = Path(result_path).read_text()
    assert "@testuser" in content
    assert "Test User" in content
    assert "Check out this new AI tool!" in content
    assert "https://x.com/test/123" in content


def test_empty_tweet_list_returns_path_but_minimal_content(
    tmp_path: Path,
) -> None:
    result = write_feed_note([], str(tmp_path), date_str="2026-06-23")
    expected_path = tmp_path / "X" / "Feed" / "2026-06-23.md"
    assert result == str(expected_path)
    assert expected_path.exists()
    content = expected_path.read_text()
    assert content.startswith("---")
    assert "0 tweets collected" in content
    assert "> [!note]" in content


def test_bookmark_source_uses_correct_tag_and_path(
    tmp_path: Path, sample_tweets: TweetList
) -> None:
    result_path = write_feed_note(
        sample_tweets, str(tmp_path), date_str="2026-06-23", source="bookmark"
    )
    content = Path(result_path).read_text()
    assert "bookmark" in content
    assert "/Bookmarks/" in str(result_path)


def test_format_follows_kepano_conventions(
    tmp_path: Path, sample_tweets: TweetList
) -> None:
    result_path = write_feed_note(sample_tweets, str(tmp_path), date_str="2026-06-23")
    content = Path(result_path).read_text()
    assert content.startswith("---")
    second_sep = content.find("---", 3)
    assert second_sep > 0
    assert "> [!note]" in content or "> [!quote]" in content
    assert "xfeed" in content
    assert "[[" in content
    assert "]]" in content
