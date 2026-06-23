# xfeed — X/Twitter Feed → Obsidian Pipeline

[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Automates scraping your X/Twitter timeline, bookmarks, and likes using Playwright, filters for tech content, enriches links with Firecrawl, and writes structured Markdown notes into an Obsidian vault. Designed to be completely free — no API costs, no third-party services.

## Features

- **Scrape timeline, bookmarks, and likes** in parallel via Playwright headless browser
- **Tech content filter** — keyword matching (AI, coding, tools, etc.) keeps only relevant tweets
- **Firecrawl enrichment** — scrapes each link for title and summary metadata
- **Obsidian output** — dated notes with frontmatter, callouts, wikilinks, and tags (kepano/obsidian-skills format)
- **Deduplication** — tracks seen tweet IDs across runs
- **Cron-ready** — designed to run every 6 hours via cron or hermes
- **100% free** — no Twitter API key, no paid services. Uses Playwright (logged-in browser session) and optionally your own self-hosted Firecrawl

## Prerequisites

- **Python 3.11+**
- **Playwright** (installs Chromium browser)
- **Obsidian vault** (local path for note output)
- **Firecrawl** — self-hosted instance (optional; leave `firecrawl_url` empty to skip enrichment)

## Quick Start

1. **Clone the repo**

   ```bash
   git clone https://github.com/your-username/xfeed.git
   cd xfeed
   ```

2. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

3. **Install Playwright browser**

   ```bash
   playwright install chromium
   ```

4. **Create config**

   ```bash
   cp config.yaml.example config.yaml
   ```

5. **Edit `config.yaml`** — set your X handle and vault path:

   ```yaml
   vault_path: "~/Documents/obsidian-vault"
   x_handle: "your_handle"
   ```

6. **Login to X** — this opens a browser window where you log into X manually:

   ```bash
   python src/auth.py --login
   ```

7. **Run the scraper**

   ```bash
   python run.py
   ```

   On first run it writes notes to `X/Feed/` and `X/Bookmarks/` in your vault.

## Configuration

Edit `config.yaml` in the project root (or set `XFEED_CONFIG` env var for a custom path).

| Field | Required | Description |
|-------|----------|-------------|
| `vault_path` | Yes | Absolute path to your Obsidian vault (`~` is expanded) |
| `x_handle` | Yes | Your X/Twitter handle (with or without `@`) |
| `firecrawl_url` | No | Base URL of a self-hosted Firecrawl instance (e.g. `http://localhost:3002`). Leave empty or omit to skip enrichment |
| `keywords` | Yes | List of case-insensitive keywords for tech filtering |
| `max_tweets_per_source` | Yes | Max tweets to scrape per source (timeline, bookmarks, likes) |
| `cron_interval` | No | Human-readable schedule (informational only, not used by the scraper itself) |

## Obsidian Output

Notes are written to `X/Feed/{date}.md` and `X/Bookmarks/{date}.md` inside your vault. Each file has YAML frontmatter, previous/next navigation, and one `## @author — DisplayName` section per tweet with a `> [!quote]` metadata callout.

```markdown
---
title: '📡 X Feed — 2026-06-23'
tags: [xfeed, feed]
---

← [[X/Feed/2026-06-22]] | [[X/Feed/2026-06-24]] →

> [!note] 📡 X Feed — 2026-06-23
> 3 tweets collected

## @kepano — Stephan Ango

Obsidian Skills: a community guide to workflow design and note-taking
best practices. https://github.com/kepano/obsidian-skills

> [!quote]
> 🔗 [View on X](https://x.com/kepano/status/123456789)
> 🕐 2026-06-23T14:30:00Z
> 🏷 #obsidian #productivity #zettelkasten
> 🌐 https://github.com/kepano/obsidian-skills
```

There's also an optional daily digest combining feed + bookmarks at `X/Daily/{date.md}`.

## Cron Setup

Run the scraper automatically every 6 hours. Example using hermes:

```bash
hermes cron --name xfeed --schedule "0 */6 * * *" -- python run.py
```

Or with a system crontab:

```bash
0 */6 * * * cd /path/to/xfeed && python run.py >> xfeed.log 2>&1
```

## Firecrawl Integration

Link enrichment via Firecrawl is **optional**. If you don't have a self-hosted Firecrawl instance, just leave `firecrawl_url` empty or set it to an empty string in `config.yaml`:

```yaml
firecrawl_url: ""
```

The pipeline will skip enrichment, outputting tweets without `link_summaries`. All other features (scraping, filtering, Obsidian output) work the same.

If you do run Firecrawl, it enriches each tweet's external links with a title and summary by scraping the page content.

## Project Structure

```
xfeed/
├── run.py                  # Main pipeline orchestrator
├── config.yaml.example     # Example configuration
├── requirements.txt        # Python dependencies
├── pyproject.toml          # Project metadata & tool config
├── cookies/                # Playwright session (gitignored)
├── src/
│   ├── auth.py             # X login session management
│   ├── config.py           # YAML config loading & validation
│   ├── scraper.py          # Playwright scraping (timeline, bookmarks, likes)
│   ├── filter.py           # Keyword-based tech tweet filtering
│   ├── enrich.py           # Firecrawl link enrichment
│   ├── obsidian_writer.py  # Obsidian markdown note generation
│   └── state.py            # State persistence (seen tweet IDs)
└── tests/
    ├── conftest.py         # Shared test fixtures
    ├── test_config.py      # Config loading tests
    ├── test_filter.py      # Filter keyword tests
    ├── test_enrich.py      # Firecrawl enrichment tests
    ├── test_obsidian_writer.py  # Note generation tests
    └── test_state.py       # State persistence tests
```

## Contributing

Contributions welcome. Open an issue or submit a PR.

## License

[MIT](LICENSE)
