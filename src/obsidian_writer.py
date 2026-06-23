"""Obsidian Flavored Markdown note generation for X feed data.

Generates dated vault notes following kepano/obsidian-skills conventions
(Inter font, wikilinks, callouts). Writes to ``X/Feed/``, ``X/Bookmarks/``,
or ``X/Daily/`` under the vault root.
"""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _format_tweet_entry(tweet: dict[str, Any], date_str: str) -> str:
    """Format a single tweet as an Obsidian markdown section.

    Returns a ``## @author — Display`` heading, the tweet body (truncated
    at 500 chars), and a ``> [!quote]`` callout with metadata (link,
    timestamp, hashtags, external links, flags).
    """
    # --- safe field access ---
    text: str = (tweet.get("text") or "").strip()
    author: str = tweet.get("author", "unknown")
    author_display: str = tweet.get("author_display", author) or author
    url: str = tweet.get("url", "")
    created_at: str = tweet.get("created_at", "")
    hashtags: list[str] = tweet.get("hashtags", []) or []
    links: list[str] = tweet.get("links", []) or []
    is_reply: bool = bool(tweet.get("is_reply", False))
    is_retweet: bool = bool(tweet.get("is_retweet", False))
    media_type: str = tweet.get("media_type", "none") or "none"

    # --- text body ---
    if not text:
        text = "*[No text]*"
    elif len(text) > 500:
        text = text[:500] + " [...]"

    lines: list[str] = [
        f"## @{author} — {author_display}",
        "",
        text,
        "",
    ]

    # --- metadata callout ---
    meta: list[str] = []

    if url:
        meta.append(f"🔗 [View on X]({url})")
    if created_at:
        meta.append(f"🕐 {created_at}")
    if hashtags:
        meta.append("🏷 " + " ".join(f"#{h}" for h in hashtags if h))
    for link in links[:3]:
        meta.append(f"🌐 {link}")
    if len(links) > 3:
        meta.append(f"📎 *+{len(links) - 3} more links*")

    flags: list[str] = []
    if is_reply:
        flags.append("💬 reply")
    if is_retweet:
        flags.append("🔁 repost")
    if media_type == "image":
        flags.append("🖼 media")
    elif media_type == "video":
        flags.append("🎬 video")
    if flags:
        meta.append(" | ".join(flags))

    if meta:
        block = "\n".join(f"> {m}" for m in meta)
        lines.append("> [!quote]")
        lines.append(block)
        lines.append("")

    return "\n".join(lines)


def _ensure_dir(path: str) -> None:
    """Create directory at *path* if it doesn't exist (mkdir -p)."""
    Path(path).mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Public API — single-source notes
# ---------------------------------------------------------------------------


def write_feed_note(
    tweets: list[dict[str, Any]],
    vault_path: str,
    date_str: str | None = None,
    source: str = "feed",
) -> str:
    """Write a dated Obsidian note for a feed or bookmarks batch.

    Args:
        tweets: Raw tweet dictionaries (keys match the ``Tweet`` dataclass).
        vault_path: Root path of the Obsidian vault.
        date_str: ISO date string (defaults to today).
        source: ``"feed"`` (default) or ``"bookmark"`` — controls directory,
            frontmatter emoji, and tag.

    Returns:
        Absolute path to the written ``.md`` file.
    """
    if date_str is None:
        date_str = datetime.date.today().isoformat()

    source_path = "Bookmarks" if source == "bookmark" else "Feed"
    emoji = "🔖" if source == "bookmark" else "📡"
    tag = "bookmark" if source == "bookmark" else "feed"

    note_dir = Path(vault_path) / "X" / source_path
    _ensure_dir(str(note_dir))
    file_path = note_dir / f"{date_str}.md"

    # Navigation: previous / next day wikilinks.
    dt = datetime.date.fromisoformat(date_str)
    prev_date = (dt - datetime.timedelta(days=1)).isoformat()
    next_date = (dt + datetime.timedelta(days=1)).isoformat()

    title = f"{emoji} X {'Bookmarks' if source == 'bookmark' else 'Feed'} — {date_str}"

    sections: list[str] = [
        "---",
        f"title: {title!r}",
        f"tags: [xfeed, {tag}]",
        "---",
        "",
        f"← [[X/{source_path}/{prev_date}]] | [[X/{source_path}/{next_date}]] →",
        "",
        f"> [!note] {title}",
        f"> {len(tweets)} tweet{'s' if len(tweets) != 1 else ''} collected",
        "",
    ]

    for tweet in tweets:
        sections.append(_format_tweet_entry(tweet, date_str))

    content = "\n".join(sections).rstrip() + "\n"
    file_path.write_text(content, encoding="utf-8")
    return str(file_path)


def write_bookmark_note(
    tweets: list[dict[str, Any]],
    vault_path: str,
    date_str: str | None = None,
) -> str:
    """Convenience wrapper: writes to ``X/Bookmarks/``.

    Identical to ``write_feed_note`` with ``source='bookmark'``.

    Returns:
        Absolute path to the written ``.md`` file.
    """
    return write_feed_note(tweets, vault_path, date_str, source="bookmark")


# ---------------------------------------------------------------------------
# Public API — daily digest (combined)
# ---------------------------------------------------------------------------


def write_daily_digest(
    feed_tweets: list[dict[str, Any]],
    bookmark_tweets: list[dict[str, Any]],
    vault_path: str,
    date_str: str | None = None,
) -> str:
    """Write a combined daily digest note at ``X/Daily/{date_str}.md``.

    Includes a ``> [!abstract]`` summary callout at the top and two
    top-level sections: ``## 📡 Feed`` and ``## 🔖 Bookmarks``.

    Args:
        feed_tweets: Tweets from the timeline feed.
        bookmark_tweets: Tweets from bookmarks.
        vault_path: Root of the Obsidian vault.
        date_str: ISO date string (defaults to today).

    Returns:
        Absolute path to the written ``.md`` file.
    """
    if date_str is None:
        date_str = datetime.date.today().isoformat()

    note_dir = Path(vault_path) / "X" / "Daily"
    _ensure_dir(str(note_dir))
    file_path = note_dir / f"{date_str}.md"

    dt = datetime.date.fromisoformat(date_str)
    prev_date = (dt - datetime.timedelta(days=1)).isoformat()
    next_date = (dt + datetime.timedelta(days=1)).isoformat()

    total = len(feed_tweets) + len(bookmark_tweets)
    title = f"📋 X Daily Digest — {date_str}"

    sections: list[str] = [
        "---",
        f"title: {title!r}",
        "tags: [xfeed, daily]",
        "---",
        "",
        f"← [[X/Daily/{prev_date}]] | [[X/Daily/{next_date}]] →",
        "",
        "> [!abstract] Summary",
        f"> 📡 **Feed**: {len(feed_tweets)} tweets",
        f"> 🔖 **Bookmarks**: {len(bookmark_tweets)} tweets",
        f"> 📊 **Total**: {total} tweet{'s' if total != 1 else ''}",
        "",
    ]

    sections.append("## 📡 Feed")
    sections.append("")
    if feed_tweets:
        for tweet in feed_tweets:
            sections.append(_format_tweet_entry(tweet, date_str))
    else:
        sections.append("*No feed tweets collected.*")
        sections.append("")

    sections.append("## 🔖 Bookmarks")
    sections.append("")
    if bookmark_tweets:
        for tweet in bookmark_tweets:
            sections.append(_format_tweet_entry(tweet, date_str))
    else:
        sections.append("*No bookmarks collected.*")
        sections.append("")

    content = "\n".join(sections).rstrip() + "\n"
    file_path.write_text(content, encoding="utf-8")
    return str(file_path)
