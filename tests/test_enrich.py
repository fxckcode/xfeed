"""Tests for Firecrawl link enrichment using ``pytest-httpx``."""

from __future__ import annotations

from typing import Any

import httpx
import pytest
import pytest_httpx

from src.enrich import enrich_links


@pytest.mark.asyncio
async def test_enrich_links_success(httpx_mock: pytest_httpx.HTTPXMock) -> None:
    tweet_data: dict[str, Any] = {
        "id": "123",
        "links": ["https://example.com/tool"],
    }
    httpx_mock.add_response(
        url="http://localhost:3002/v1/scrape",
        method="POST",
        json={
            "data": {
                "markdown": "# My Tool Page\n\nThis tool helps you build AI apps faster.",
            },
        },
    )

    result = await enrich_links(tweet_data, "http://localhost:3002")

    assert "link_summaries" in result
    assert len(result["link_summaries"]) == 1
    assert result["link_summaries"][0]["url"] == "https://example.com/tool"
    assert result["link_summaries"][0]["title"] == "My Tool Page"
    assert "AI apps faster" in result["link_summaries"][0]["summary"]


@pytest.mark.asyncio
async def test_enrich_links_no_links() -> None:
    tweet_data: dict[str, Any] = {"id": "123", "links": []}

    result = await enrich_links(tweet_data, "http://localhost:3002")
    assert result["link_summaries"] == []


@pytest.mark.asyncio
async def test_enrich_links_http_error_fallback(httpx_mock: pytest_httpx.HTTPXMock) -> None:
    tweet_data: dict[str, Any] = {
        "id": "123",
        "links": ["https://example.com/tool"],
    }
    httpx_mock.add_response(
        url="http://localhost:3002/v1/scrape",
        method="POST",
        status_code=500,
    )

    result = await enrich_links(tweet_data, "http://localhost:3002")
    assert result["link_summaries"] == []


@pytest.mark.asyncio
async def test_enrich_links_unexpected_json(httpx_mock: pytest_httpx.HTTPXMock) -> None:
    """When Firecrawl returns unexpected JSON, enrich falls back gracefully."""
    tweet_data: dict[str, Any] = {
        "id": "456",
        "links": ["https://example.com/other"],
    }
    httpx_mock.add_response(
        url="http://localhost:3002/v1/scrape",
        method="POST",
        json={"data": {}},  # valid response but missing markdown
    )

    result = await enrich_links(tweet_data, "http://localhost:3002")
    # data["data"] = {}, so .get("markdown", "") = ""
    # Title and summary are empty but entry exists (no crash)
    assert len(result["link_summaries"]) == 1
    assert result["link_summaries"][0]["url"] == "https://example.com/other"
    assert result["link_summaries"][0]["title"] == ""
    assert result["link_summaries"][0]["summary"] == ""


@pytest.mark.asyncio
async def test_enrich_links_timeout_fallback(httpx_mock: pytest_httpx.HTTPXMock) -> None:
    """Simulate a timeout — enrich should return empty summaries."""
    tweet_data: dict[str, Any] = {
        "id": "789",
        "links": ["https://example.com/slow"],
    }
    # httpx raises ReadTimeout when the client's timeout fires
    httpx_mock.add_exception(
        url="http://localhost:3002/v1/scrape",
        exception=httpx.ReadTimeout("Connection timed out"),
    )

    result = await enrich_links(tweet_data, "http://localhost:3002")
    assert result["link_summaries"] == []
