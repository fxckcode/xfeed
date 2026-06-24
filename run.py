"""Main entry point for the xfeed pipeline.

Orchestrates: config -> auth -> scrape -> filter -> enrich -> obsidian write -> state update.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

from playwright.async_api import async_playwright

from src.article_reader import process_articles
from src.auth import is_logged_in, load_session
from src.config import Config, load_config
from src.enrich import enrich_tweets
from src.filter import filter_tweets
from src.obsidian_writer import write_bookmark_note, write_feed_note
from src.scraper import (
    SessionExpiredError,
    Tweet,
    scrape_bookmarks,
    scrape_likes,
    scrape_timeline,
)
from src.state import load_state, mark_articles_processed, mark_projects_tested, save_state, update_state
from src.tester import process_tweet_projects

logger = logging.getLogger("xfeed")


def _setup_logging() -> None:
    """Configure structured logging to stderr at INFO level."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )


def _resolve_config_path() -> str:
    """Resolve config path: ``XFEED_CONFIG`` env var, or ``config.yaml``."""
    return os.environ.get("XFEED_CONFIG", "config.yaml")


async def _scrape_source(
    label: str,
    fn: Any,
    *args: Any,
    **kwargs: Any,
) -> list[Tweet]:
    """Wrap a single scrape call so failures log and return empty instead of crashing.

    Re-raises ``SessionExpiredError`` so the caller knows the session died.
    """
    try:
        return await fn(*args, **kwargs)
    except SessionExpiredError:
        logger.warning("Session expired during %s scrape", label)
        raise
    except Exception:
        logger.warning("Failed to scrape %s", label, exc_info=True)
        return []


async def main() -> None:
    _setup_logging()
    logger.info("xfeed pipeline starting")

    # ------------------------------------------------------------------
    # 1. Config
    # ------------------------------------------------------------------
    config_path = _resolve_config_path()
    try:
        config: Config = load_config(config_path)
    except FileNotFoundError:
        logger.error("Config file not found: %s", config_path)
        sys.exit(1)
    except ValueError as e:
        logger.error("Invalid config: %s", e)
        sys.exit(1)

    # ------------------------------------------------------------------
    # 2. State
    # ------------------------------------------------------------------
    state_path = "state.json"
    state = load_state(state_path)

    # ------------------------------------------------------------------
    # 3. Session cookies
    # ------------------------------------------------------------------
    cookies_path = Path("cookies/state.json")
    if not cookies_path.exists():
        logger.error(
            "Session cookies not found at %s — run auth.py --login first",
            cookies_path,
        )
        sys.exit(1)

    storage_state = await load_session(cookies_path)

    # ------------------------------------------------------------------
    # 4-12. Playwright pipeline
    # ------------------------------------------------------------------
    browser = None
    context = None

    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            context = await browser.new_context(
                storage_state=storage_state,
                viewport={"width": 1280, "height": 720},
            )

            # ----------------------------------------------------------
            # 5. Session verification
            # ----------------------------------------------------------
            session_page = await context.new_page()
            try:
                valid = await is_logged_in(session_page)
            finally:
                await session_page.close()

            if not valid:
                logger.error(
                    "X session is invalid — session may have expired. "
                    "Re-run auth.py --login to refresh."
                )
                sys.exit(1)

            logger.info("Session verified")

            # ----------------------------------------------------------
            # 6. Scrape timeline, bookmarks, likes in parallel
            # ----------------------------------------------------------
            timeline_tweets: list[Tweet] = []
            bookmark_tweets: list[Tweet] = []
            likes_tweets: list[Tweet] = []

            max_n = config.max_tweets_per_source
            results = await asyncio.gather(
                _scrape_source("timeline", scrape_timeline, context, max_n),
                _scrape_source("bookmarks", scrape_bookmarks, context, max_n),
                _scrape_source("likes", scrape_likes, context, config.x_handle, max_n),
                return_exceptions=True,
            )

            # Unpack results, handling partial failures
            for i, result in enumerate(results):
                if isinstance(result, SessionExpiredError):
                    logger.error("Session expired mid-scrape — cannot continue")
                    sys.exit(1)
                if isinstance(result, Exception):
                    continue  # already logged by _scrape_source

                if i == 0:
                    timeline_tweets = result
                elif i == 1:
                    bookmark_tweets = result
                else:
                    likes_tweets = result

            # Track which source each tweet came from (scraper JS doesn't set source field)
            feed_tweets: list[Tweet] = timeline_tweets + likes_tweets
            all_tweets: list[Tweet] = feed_tweets + bookmark_tweets

            n_scraped = len(all_tweets)
            logger.info(
                "Scraped %d tweets (timeline=%d, bookmarks=%d, likes=%d)",
                n_scraped,
                len(timeline_tweets),
                len(bookmark_tweets),
                len(likes_tweets),
            )

            if not all_tweets:
                logger.info("No tweets scraped from any source")
                state = update_state(state, [])
                save_state(state_path, state)
                return

            # Build source lookup keyed by tweet ID
            feed_ids: set[str] = {t.id for t in feed_tweets}
            bookmark_ids: set[str] = {t.id for t in bookmark_tweets}

            # ----------------------------------------------------------
            # 7. Filter: only NEW tweets not in seen_ids
            # ----------------------------------------------------------
            all_dicts: list[dict[str, Any]] = [asdict(t) for t in all_tweets]
            new_dicts: list[dict[str, Any]] = [
                d for d in all_dicts if d["id"] not in state["seen_ids"]
            ]
            n_new = len(new_dicts)

            if not new_dicts:
                logger.info("No new tweets found")
                state = update_state(state, all_tweets)
                save_state(state_path, state)
                return

            # Filter: only tech tweets matching keywords
            tech_dicts: list[dict[str, Any]] = filter_tweets(new_dicts, config.keywords)
            n_tech = len(tech_dicts)

            if not tech_dicts:
                logger.info("No tech tweets found among %d new tweets", n_new)
                state = update_state(state, all_tweets)
                save_state(state_path, state)
                return

            # ----------------------------------------------------------
            # 8. Enrich with Firecrawl
            # ----------------------------------------------------------
            logger.info("Enriching %d tech tweets with Firecrawl", n_tech)
            enriched: list[dict[str, Any]] = await enrich_tweets(tech_dicts, config.firecrawl_url)
            n_enriched = len(enriched)
            logger.info("Enriched %d tweets", n_enriched)

            # ----------------------------------------------------------
            # 9. Separate by source & write to Obsidian vault
            # ----------------------------------------------------------
            feed_write: list[dict[str, Any]] = [d for d in enriched if d["id"] in feed_ids]
            bookmark_write: list[dict[str, Any]] = [d for d in enriched if d["id"] in bookmark_ids]

            n_written = 0

            if feed_write:
                feed_path = write_feed_note(feed_write, config.vault_path, source="feed")
                logger.info("Wrote feed note: %s", feed_path)
                n_written += 1
            else:
                logger.info("No feed tweets to write")

            if bookmark_write:
                bm_path = write_bookmark_note(bookmark_write, config.vault_path)
                logger.info("Wrote bookmark note: %s", bm_path)
                n_written += 1
            else:
                logger.info("No bookmark tweets to write")

            # ----------------------------------------------------------
            # 10. Collect project & article data for cron prompt
            # ----------------------------------------------------------
            tested_before: set[str] = set(state.get("tested_projects", []))
            project_results = process_tweet_projects(
                enriched, config.vault_path, tested_before
            )
            n_tested = len(project_results)
            if project_results:
                tested_names = [r["project_name"] for r in project_results]
                state = mark_projects_tested(state, tested_names)

            # Collect article data
            article_urls_before: set[str] = set(
                state.get("processed_article_urls", [])
            )
            article_results = await process_articles(
                enriched,
                config.vault_path,
                config.firecrawl_url,
                article_urls_before,
            )
            n_articles = len(article_results)
            if article_results:
                new_urls = [r["url"] for r in article_results]
                state = mark_articles_processed(state, new_urls)

            # ----------------------------------------------------------
            # 11. Update & persist state

            # ----------------------------------------------------------
            # 12. Update & persist state
            # ----------------------------------------------------------
            state = update_state(state, all_tweets)
            save_state(state_path, state)

            # ----------------------------------------------------------
            # 13. Summary
            # ----------------------------------------------------------
            logger.info(
                "Summary: %d scraped, %d new, %d tech, "
                "%d enriched, %d written, "
                "%d projects tested, %d articles processed",
                n_scraped,
                n_new,
                n_tech,
                n_enriched,
                n_written,
                n_tested,
                n_articles,
            )

    finally:
        # ----------------------------------------------------------
        # 12. Always close browser (safe cleanup)
        # ----------------------------------------------------------
        if context is not None:
            try:
                await context.close()
            except Exception:
                pass
        if browser is not None:
            try:
                await browser.close()
            except Exception:
                pass


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(0)
