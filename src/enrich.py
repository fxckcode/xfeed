"""Enrich tweets by scraping their links via Firecrawl."""

from __future__ import annotations

from typing import Any

import httpx


async def enrich_links(tweet_data: dict[str, Any], firecrawl_url: str) -> dict[str, Any]:
    """Scrape each link in *tweet_data* via Firecrawl and attach summaries.

    Sends a POST request for every URL in ``tweet_data["links"]`` to
    ``{firecrawl_url}/v1/scrape``, requesting markdown output. Extracts the
    page title and first content section from the response.

    If any request fails (network error, non-200, timeout) the entire
    enrichment for that tweet gracefully falls back to an empty
    ``link_summaries`` list.

    Args:
        tweet_data: A tweet dict containing a ``links`` key (list of URLs).
        firecrawl_url: Base URL of the Firecrawl instance (e.g.
            ``http://localhost:3002``).

    Returns:
        The same *tweet_data* dict with an added ``link_summaries`` field:
        a list of ``{"url": str, "title": str, "summary": str}`` dicts.
    """
    links: list[str] = tweet_data.get("links", [])
    if not links:
        tweet_data["link_summaries"] = []
        return tweet_data

    summaries: list[dict[str, str]] = []
    async with httpx.AsyncClient(timeout=15.0) as client:
        for url in links:
            try:
                resp = await client.post(
                    f"{firecrawl_url.rstrip('/')}/v1/scrape",
                    json={"url": url, "formats": ["markdown"]},
                )
                resp.raise_for_status()
                data = resp.json()

                markdown = (data.get("data") or {}).get("markdown", "")
                title = ""
                summary = ""
                if markdown:
                    lines = markdown.split("\n")
                    title = lines[0].strip().lstrip("#").strip() if lines else ""
                    content_lines = [
                        line for line in lines[1:]
                        if line.strip() and not line.startswith("#")
                        and not line.startswith("---")
                    ]
                    summary = content_lines[0].strip()[:500] if content_lines else ""

                summaries.append({"url": url, "title": title, "summary": summary})
            except (httpx.HTTPError, httpx.TimeoutException, KeyError, IndexError):
                tweet_data["link_summaries"] = []
                return tweet_data

    tweet_data["link_summaries"] = summaries
    return tweet_data


async def enrich_tweets(
    tweets: list[dict[str, Any]],
    firecrawl_url: str,
) -> list[dict[str, Any]]:
    """Enrich every tweet in *tweets* by scraping their links via Firecrawl.

    Iterates over the list and calls :func:`enrich_links` on each item.
    Failures are handled per-tweet, so one broken tweet doesn't affect the
    rest.

    Args:
        tweets: List of tweet dicts, each expected to have a ``links`` key.
        firecrawl_url: Base URL of the Firecrawl instance.

    Returns:
        List of enriched tweet dicts (each has an added ``link_summaries``
        field).
    """
    results: list[dict[str, Any]] = []
    for t in tweets:
        enriched = await enrich_links(t, firecrawl_url)
        results.append(enriched)
    return results
