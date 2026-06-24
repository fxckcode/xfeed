"""Article processing for xfeed — scrape, summarize, and tag relevance.

When a tweet links to an article (blog, docs, X thread, etc.), scrape the
content with Firecrawl, extract key points, detect which tools in the user's
stack (Hermes, Claude, OpenCode, Codex) are relevant, and write a structured
note in the Obsidian vault under ``X/Articles/``.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

logger = logging.getLogger("xfeed.articles")

# ---------------------------------------------------------------------------
# Tool relevance keywords
# ---------------------------------------------------------------------------

TOOL_KEYWORDS: dict[str, list[str]] = {
    "Hermes": [
        "hermes", "hermes agent", "gentle ai", "nous research",
        "agent harness", "mcp", "model context protocol",
    ],
    "Claude": [
        "claude", "anthropic", "sonnet", "haiku", "opus",
        "claude code", "claude desktop", "artifacts",
    ],
    "OpenCode": [
        "opencode", "open code", "coding agent", "acp",
        "agent communication protocol",
    ],
    "Codex": [
        "codex", "openai codex", "codex cli",
    ],
    "AI / LLM": [
        "llm", "large language model", "gpt", "ai agent",
        "autonomous agent", "agentic", "rag", "retrieval",
        "fine.tune", "embedding", "vector database",
        "prompt engineering", "chain of thought",
    ],
    "Dev Tools": [
        "playwright", "puppeteer", "docker", "kubernetes",
        "github actions", "ci/cd", "devops", "terraform",
        "vs code", "neovim", "lazyvim", "tmux", "zellij",
    ],
}

# ---------------------------------------------------------------------------
# URL classification for articles
# ---------------------------------------------------------------------------

ARTICLE_DOMAINS: set[str] = {
    "medium.com", "dev.to", "hashnode.com", "blog.google",
    "openai.com", "anthropic.com", "github.blog",
    "stackoverflow.blog", "news.ycombinator.com",
    "towardsdatascience.com", "analyticsvidhya.com",
    "arxiv.org", " paperswithcode.com",
    "docs.github.com", "docs.docker.com", "learn.microsoft.com",
}

THREAD_DOMAINS: set[str] = {"x.com", "twitter.com"}


def _is_project_url(url: str) -> bool:
    """Return ``True`` when *url* looks like a project (GitHub/npm/PyPI)."""
    return any(
        d in url
        for d in ("github.com", "npmjs.com/package", "pypi.org/project")
    )


def _is_article_url(url: str) -> bool:
    """Return ``True`` when *url* looks like an article worth reading."""
    if _is_project_url(url):
        return False
    try:
        netloc = urlparse(url).netloc
        path = urlparse(url).path
    except ValueError:
        return False

    netloc = netloc.lower()

    # Known article/blog domains
    if any(d in netloc for d in ARTICLE_DOMAINS):
        return True

    # X.com threads (single tweet or thread URLs)
    if any(d in netloc for d in THREAD_DOMAINS):
        if "/status/" in path or "/i/web/" in path:
            return True

    # General blog/article detection: URL paths that look like content
    blog_patterns = re.compile(
        r"/(blog|news|article|post|docs|guide|tutorial|learn|"
        r"how-to|what-is|understanding|deep-dive|introducing)/",
        re.IGNORECASE,
    )
    if blog_patterns.search(path):
        return True

    # Simple fallback: if it's not a project URL and has readable path
    if path and path != "/" and len(path) > 15:
        return True

    return False


# ---------------------------------------------------------------------------
# Scraping
# ---------------------------------------------------------------------------


async def scrape_article(
    url: str, firecrawl_url: str
) -> dict[str, Any] | None:
    """Scrape an article URL via Firecrawl and return markdown + metadata.

    Returns ``None`` on any error (logged, not raised).
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{firecrawl_url.rstrip('/')}/v1/scrape",
                json={"url": url, "formats": ["markdown"]},
            )
            resp.raise_for_status()
            data = resp.json()
            markdown = (data.get("data") or {}).get("markdown", "")
            meta = (data.get("data") or {}).get("metadata", {})
            return {"url": url, "markdown": markdown, "metadata": meta}
    except Exception as exc:
        logger.warning("Failed to scrape article %s: %s", url, exc)
        return None


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------


def _extract_key_points(markdown: str) -> list[str]:
    """Extract key points from markdown content."""
    points: list[str] = []
    for line in markdown.split("\n"):
        stripped = line.strip()
        # Grab headings (## or ###) as section titles
        if stripped.startswith("## ") or stripped.startswith("### "):
            points.append(stripped.lstrip("#").strip())
        # Grab the first non-empty paragraph after a heading
        elif stripped and not stripped.startswith(("#", "-", "*", ">", "```")):
            if len(points) < 10 and len(stripped) > 40:
                points.append(stripped[:150])
    return points[:10]


def _detect_tool_relevance(
    markdown: str, text: str
) -> dict[str, list[str]]:
    """Detect which tools from the user's stack are relevant.

    Returns dict mapping tool name -> list of matched keywords.
    """
    combined = (markdown + " " + text).lower()
    relevance: dict[str, list[str]] = {}
    for tool, keywords in TOOL_KEYWORDS.items():
        matches = [kw for kw in keywords if kw in combined]
        if matches:
            relevance[tool] = matches
    return relevance


def analyze_article(
    article_data: dict[str, Any],
) -> dict[str, Any]:
    """Analyze scraped article content: extract points and detect relevance.

    Returns a dict with keys: ``url``, ``title``, ``key_points``,
    ``tool_relevance``, ``word_count``.
    """
    markdown = article_data.get("markdown", "")
    meta = article_data.get("metadata", {})
    title = meta.get("title", "") or ""
    if not title and markdown:
        first_line = markdown.split("\n")[0].strip().lstrip("#").strip()
        title = first_line

    key_points = _extract_key_points(markdown)
    tool_relevance = _detect_tool_relevance(markdown, title)
    word_count = len(markdown.split())

    return {
        "url": article_data["url"],
        "title": title,
        "key_points": key_points,
        "tool_relevance": tool_relevance,
        "word_count": word_count,
    }


# ---------------------------------------------------------------------------
# Obsidian note writer
# ---------------------------------------------------------------------------


def _slugify(text: str) -> str:
    """Turn a title into a filesystem-safe slug."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:60] or "article"


def write_article_note(
    analysis: dict[str, Any], vault_path: str
) -> str:
    """Write a structured Obsidian note for an analyzed article.

    File: ``{vault_path}/X/Articles/{slug}.md``

    Returns the absolute path written.
    """
    vault = Path(vault_path)
    articles_dir = vault / "X" / "Articles"
    articles_dir.mkdir(parents=True, exist_ok=True)

    slug = _slugify(analysis.get("title", "untitled"))
    file_path = articles_dir / f"{slug}.md"

    tags = ["xfeed", "article"]
    relevance = analysis.get("tool_relevance", {})
    for tool in relevance:
        tags.append(tool.lower().replace(" ", "-").replace("/", "-"))
    tags_str = ", ".join(tags)

    key_points = analysis.get("key_points", [])
    points_md = "\n".join(f"- {p}" for p in key_points[:5]) if key_points else "- *(could not extract points)*"

    relevance_md = ""
    if relevance:
        for tool, matches in relevance.items():
            relevance_md += f"> [!tip] Relevant to **{tool}**\n> Matched: {', '.join(matches)}\n>\n"

    # Truncate long titles for frontmatter
    title = analysis.get("title", "Untitled")[:80]

    content = f"""---
title: '{title}'
date: {datetime.date.today().isoformat()}
tags: [{tags_str}]
---

# {title}

> [!info] Source
> {analysis['url']}

## Key Points

{points_md}

## Tool Relevance

{relevance_md or "> [!info] General reference — no direct tool match found"}

## Metadata
- **Words**: {analysis.get('word_count', 0)}
- **Link**: [{analysis['url'][:60]}...]({analysis['url']})

---
_Auto-imported by xfeed_
"""

    file_path.write_text(content.strip() + "\n")
    logger.info("Wrote article note: %s", file_path)
    return str(file_path)


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def detect_articles(tweets: list[dict]) -> list[dict]:
    """Scan tweets for article-like links, return deduplicated list.

    Each result: ``{"url": str, "tweet_text": str, "source": str}``
    """
    seen: set[str] = set()
    articles: list[dict[str, Any]] = []

    for tweet in tweets:
        links: list[str] = tweet.get("links", []) or []
        for link in links:
            if not _is_article_url(link):
                continue
            if link in seen:
                continue
            seen.add(link)
            articles.append({
                "url": link,
                "tweet_text": tweet.get("text", ""),
                "source": tweet.get("source", ""),
            })

    return articles


async def process_articles(
    tweets: list[dict],
    vault_path: str,
    firecrawl_url: str,
    processed_urls: set[str] | None = None,
) -> list[dict]:
    """Detect articles in tweets, scrape, analyze, write notes.

    Returns list of result dicts with keys: ``url``, ``title``, ``status``,
    ``note_path``.
    """
    if processed_urls is None:
        processed_urls = set()

    detected = detect_articles(tweets)
    results: list[dict[str, Any]] = []

    for article in detected:
        url = article["url"]
        if url in processed_urls:
            continue

        logger.info("Scraping article: %s", url)
        scraped = await scrape_article(url, firecrawl_url)
        if scraped is None:
            results.append({
                "url": url,
                "title": "",
                "status": "scrape_failed",
                "note_path": "",
            })
            continue

        analysis = analyze_article(scraped)
        results.append({
            "url": url,
            "title": analysis.get("title", ""),
            "analysis": analysis,
            "scraped_markdown": scraped.get("markdown", ""),
            "status": "ok",
        })

    return results


# Need datetime for the write function
import datetime  # noqa: E402
