"""X/Twitter authentication via Playwright — manual login session management."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from playwright.async_api import Page, async_playwright

COOKIES_PATH: Path = Path("cookies/state.json")


async def _wait_for_login(page: Page, timeout: int = 120) -> None:
    """Poll page URL every 2s until the user reaches x.com/home or x.com/."""
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        await asyncio.sleep(2)
        try:
            url = page.url
        except Exception:
            continue
        if url.rstrip("/").endswith(("x.com/home", "x.com/")):
            print("Login detected, saving session...")
            return
    raise TimeoutError("Login not detected within 120s timeout")


async def login(cookies_dir: Path) -> None:
    """Open headed Playwright browser for manual X login, then persist session."""
    cookies_dir.mkdir(parents=True, exist_ok=True)
    state_path = cookies_dir / "state.json"

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto("https://x.com", wait_until="domcontentloaded")

        await _wait_for_login(page)
        await context.storage_state(path=str(state_path))
        await browser.close()


async def load_session(cookies_path: Path) -> dict[str, Any]:
    """Load a saved Playwright storage state from disk."""
    if not cookies_path.exists():
        raise FileNotFoundError(f"Session file not found: {cookies_path}")
    with open(cookies_path) as f:
        return json.load(f)


async def is_logged_in(page: Page) -> bool:
    """Check whether the Playwright page has an active X session.

    Navigates to x.com/home and looks for article elements.
    Waits up to 10s for tweets to render.
    """
    try:
        await page.goto("https://x.com/home", wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)
        await page.wait_for_selector("article", timeout=8000)
        return True
    except Exception:
        await page.goto("https://x.com/home", wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)
        articles = await page.locator("article").count()
        return articles > 0
