"""X/Twitter scraping via Playwright — timeline, bookmarks, and likes."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from playwright.async_api import BrowserContext, Page
from playwright.async_api import TimeoutError as PlaywrightTimeout

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PAGE_TIMEOUT_MS: int = 30_000
"""Default page-load timeout in milliseconds."""

SCROLL_PAUSE_SEC: float = 2.0
"""Seconds to wait after each scroll while loading more tweets."""

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class SessionExpiredError(Exception):
    """Raised when X redirects to the login page, indicating the session is no
    longer valid."""


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class Tweet:
    """A single tweet extracted from an X page."""

    id: str
    url: str
    author: str
    author_display: str
    text: str
    created_at: str
    source: str
    hashtags: list[str] = field(default_factory=list)
    mentions: list[str] = field(default_factory=list)
    links: list[str] = field(default_factory=list)
    is_reply: bool = False
    is_retweet: bool = False
    media_type: str = "none"


# ---------------------------------------------------------------------------
# DOM extraction (JavaScript)
# ---------------------------------------------------------------------------

_EXTRACT_TWEETS_JS: str = """
() => {
  const results = [];
  for (const article of document.querySelectorAll("article[data-testid='tweet']")) {
    try {
      const link = article.querySelector("a[href*='/status/']");
      const href = link ? link.getAttribute("href") : "";
      const m = href.match(/\\/status\\/(\\d+)/);
      const id = m ? m[1] : "";
      if (!id) continue;

      const parts = href.split("?");
      const url = "https://x.com" + parts[0];

      const userEls = article.querySelectorAll('[data-testid="User-Name"] span');
      const author = userEls.length > 1 ? userEls[userEls.length - 1].textContent.trim() : "";
      const author_display = userEls.length > 0 ? userEls[0].textContent.trim() : "";

      const textEl = article.querySelector('[data-testid="tweetText"]');
      const text = textEl ? textEl.textContent.trim() : "";

      const timeEl = article.querySelector("time");
      const created_at = timeEl ? timeEl.getAttribute("datetime") : "";

      let source = "";
      const sourceEl = article.querySelector("a[href*='/source/']");
      if (sourceEl) source = sourceEl.textContent.trim();

      const hashtags = [];
      const mentions = [];
      const links = [];
      for (const a of article.querySelectorAll("a[href]")) {
        const h = a.getAttribute("href") || "";
        const t = a.textContent.trim();
        if (h.startsWith("/hashtag/")) {
          hashtags.push(t);
        } else if (t.startsWith("@")) {
          mentions.push(t);
        } else if (h.startsWith("http") && !h.includes("x.com") && !h.includes("twitter.com")) {
          links.push(h);
        }
      }

      const hasPhoto = article.querySelector('[data-testid="tweetPhoto"]');
      const hasVideo = article.querySelector("video");
      const media_type = hasVideo ? "video" : hasPhoto ? "image" : "none";

      const is_reply = article.textContent.includes("Replying to");

      const socialCtx = article.querySelector('[data-testid="socialContext"]');
      const is_retweet = socialCtx ? socialCtx.textContent.includes("Reposted") : false;

      results.push({
        id, url, author, author_display, text, created_at, source,
        hashtags, mentions, links, is_reply, is_retweet, media_type
      });
    } catch (_) { /* skip malformed */ }
  }
  return results;
};
"""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _check_session(page: Page) -> None:
    """Check if the current page URL indicates a logged-out session.

    Raises:
        SessionExpiredError: If the URL contains ``x.com/login`` or the page
            text contains "Sign in to X" (both signals the session is dead).
    """
    url = page.url
    if "x.com/login" in url:
        raise SessionExpiredError(
            "Redirected to login page — session has expired, call auth.login() again"
        )

    body_text = await page.evaluate("() => document.body?.innerText?.slice(0, 500) ?? ''")
    if "Sign in to X" in body_text and "x.com" in url and "/login" not in url:
        raise SessionExpiredError("Page shows 'Sign in to X' prompt — session has expired")


async def _extract_tweets(page: Page) -> list[dict[str, Any]]:
    """Run the extraction JS on the current page and return raw dicts."""
    raw: list[dict[str, Any]] = await page.evaluate(_EXTRACT_TWEETS_JS)
    return raw


def _deduplicate(raw: list[dict[str, Any]], seen: set[str]) -> list[dict[str, Any]]:
    """Filter out tweets whose ``id`` is already in *seen*, updating *seen*.

    Args:
        raw: Raw tweet dicts returned by the extraction JS.
        seen: Mutable set of IDs already collected.

    Returns:
        New tweets (those with unseen IDs).
    """
    new: list[dict[str, Any]] = []
    for t in raw:
        if t["id"] not in seen:
            seen.add(t["id"])
            new.append(t)
    return new


async def _scrape_page(
    page: Page,
    url: str,
    max_count: int,
    *,
    verify_fn: bool = True,
) -> list[Tweet]:
    """Shared scroll-and-extract loop used by all three scrape functions.

    Args:
        page: An active Playwright page (already authenticated).
        url: The X URL to navigate to.
        max_count: Stop once this many tweets have been collected.
        verify_fn: If True, run ``_check_session()`` after navigation
            (skipped for the likes page since the handle itself may be part of the URL).

    Returns:
        A list of deduplicated ``Tweet`` instances in DOM order.
    """
    await page.goto(url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT_MS)

    if verify_fn:
        await _check_session(page)

    # Wait for at least one tweet to render.
    try:
        await page.wait_for_selector(
            "article[data-testid='tweet']",
            timeout=PAGE_TIMEOUT_MS,
        )
    except PlaywrightTimeout:
        # No tweets on the page at all — return empty.
        return []

    seen: set[str] = set()
    all_tweets: list[Tweet] = []
    consecutive_empty_scrolls = 0
    max_empty_scrolls = 5

    while len(all_tweets) < max_count:
        raw = await _extract_tweets(page)
        new = _deduplicate(raw, seen)

        for d in new:
            all_tweets.append(Tweet(**d))
            if len(all_tweets) >= max_count:
                break

        if not new:
            consecutive_empty_scrolls += 1
        else:
            consecutive_empty_scrolls = 0

        if consecutive_empty_scrolls >= max_empty_scrolls:
            break

        # Scroll to bottom and wait.
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(SCROLL_PAUSE_SEC)

        await _check_session(page)

    return all_tweets[:max_count]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def verify_session(context: BrowserContext) -> bool:
    """Check whether the current *context* has an active X session.

    Navigates to ``x.com/home`` and looks for at least one tweet article.
    Returns ``True`` if tweets are visible, ``False`` otherwise.
    """
    page = await context.new_page()
    try:
        await page.goto(
            "https://x.com/home", wait_until="domcontentloaded", timeout=PAGE_TIMEOUT_MS
        )

        try:
            await page.wait_for_selector(
                "article[data-testid='tweet']",
                timeout=PAGE_TIMEOUT_MS,
            )
            return True
        except PlaywrightTimeout:
            return False
    finally:
        await page.close()


async def scrape_timeline(
    context: BrowserContext,
    max_count: int = 20,
) -> list[Tweet]:
    """Scrape the authenticated user's home timeline.

    Navigates to ``https://x.com/home`` and scrolls to load up to
    *max_count* tweets.

    Args:
        context: An authenticated Playwright browser context.
        max_count: Maximum number of tweets to return (default 20).

    Returns:
        A list of deduplicated ``Tweet`` instances.

    Raises:
        SessionExpiredError: If the session is no longer valid.
    """
    page = await context.new_page()
    try:
        return await _scrape_page(page, "https://x.com/home", max_count)
    finally:
        await page.close()


async def scrape_bookmarks(
    context: BrowserContext,
    max_count: int = 20,
) -> list[Tweet]:
    """Scrape the authenticated user's bookmarks.

    Navigates to ``https://x.com/i/bookmarks`` and scrolls to load up to
    *max_count* tweets.

    Args:
        context: An authenticated Playwright browser context.
        max_count: Maximum number of tweets to return (default 20).

    Returns:
        A list of deduplicated ``Tweet`` instances.

    Raises:
        SessionExpiredError: If the session is no longer valid.
    """
    page = await context.new_page()
    try:
        return await _scrape_page(page, "https://x.com/i/bookmarks", max_count)
    finally:
        await page.close()


async def scrape_likes(
    context: BrowserContext,
    handle: str,
    max_count: int = 20,
) -> list[Tweet]:
    """Scrape the likes timeline for the user *handle*.

    Navigates to ``https://x.com/{handle}/likes`` and scrolls to load up to
    *max_count* tweets.

    Args:
        context: An authenticated Playwright browser context.
        handle: X handle (with or without leading ``@``).
        max_count: Maximum number of tweets to return (default 20).

    Returns:
        A list of deduplicated ``Tweet`` instances.

    Raises:
        SessionExpiredError: If the session is no longer valid.
    """
    clean_handle = handle.lstrip("@")
    page = await context.new_page()
    try:
        return await _scrape_page(
            page,
            f"https://x.com/{clean_handle}/likes",
            max_count,
        )
    finally:
        await page.close()
