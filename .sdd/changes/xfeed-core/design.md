# Design: xfeed-core

## Architecture Decisions

### ADR-1: Playwright con session persistence en vez de API key
- **Context:** Necesitamos acceso autenticado a X feed/bookmarks/likes sin pagar API
- **Options:** (a) Playwright browser automation, (b) X API v2 (paga), (c) Nitter (muerto), (d) instaloader-style scraping
- **Decision:** Playwright con `browser_context.storage_state()` para persistir cookies + localStorage
- **Rationale:** Gratis, acceso completo a lo que el usuario ve, sin rate limits de API
- **Consequences:** Login one-time manual, sesión expira ~2 semanas, hay que re-loguear
- **Status:** accepted

### ADR-2: Firecrawl para enrichment de links
- **Context:** Los tweets contienen links a herramientas/blogs. Queremos saber de qué trata cada link
- **Options:** (a) Firecrawl self-hosted, (b) requests + BeautifulSoup manual, (c) readability-lxml, (d) omitting enrichment
- **Decision:** Firecrawl (scrape endpoint → extract markdown)
- **Rationale:** Ya self-hosted, da markdown limpio, maneja JS rendering, mejor que scraping manual
- **Consequences:** Firecrawl debe estar corriendo, si no está disponible → graceful fallback
- **Status:** accepted

### ADR-3: Filtro tech por keywords configurables
- **Context:** No queremos guardar tweets de fútbol/famosos, solo tech
- **Options:** (a) Keywords hardcodeadas, (b) YAML configurable, (c) AI classifier
- **Decision:** Keywords configurables en YAML + regex matching
- **Rationale:** Simple, rápido, sin dep de AI, el usuario controla qué capturar
- **Consequences:** Puede haber falsos positivos/negativos, ajustable editando config
- **Status:** accepted

### ADR-4: Kepano/obsidian-skills para formato de notas
- **Context:** El usuario exige que las notas sigan el estándar de Obsidian
- **Decision:** Frontmatter con title/date/tags, wikilinks para relaciones, callouts para highlights
- **Rationale:** Compatible con el ecosistema Obsidian, el usuario ya tiene estas skills
- **Status:** accepted

### ADR-5: ECC coding-standards para calidad de código
- **Context:** El usuario exige código de calidad profesional
- **Decision:** Type annotations, ruff linting, black formatting, pytest con 80%+ coverage
- **Rationale:** ECC standards probados, mantiene calidad consistente
- **Status:** accepted

## Module Design

### auth.py
- `login()` → abre browser headed, usuario loguea → guarda `cookies/state.json`
- `load_session()` → carga cookies desde archivo
- `is_session_valid()` → verifica si cookies siguen activas navegando a x.com/home

### scraper.py
- `scrape_timeline(context, count=20)` → navega `x.com/home`, scroll, extrae tweets
- `scrape_bookmarks(context, count=20)` → navega `x.com/i/bookmarks`
- `scrape_likes(context, handle, count=20)` → navega `x.com/{handle}/likes`
- `extract_tweets(page)` → evalúa JS en página para extraer arrays de tweet data
- Timeout: 30s por navegación, 10s por scroll

### filter.py
- `is_tech_tweet(tweet, keywords)` → match por keywords + regex en texto
- `filter_tweets(tweets, keywords)` → return solo tech tweets
- Keywords desde config.yaml

### enrich.py
- `enrich_links(tweet, firecrawl_url)` → por cada link, Firecrawl scrape → markdown summary
- `enrich_tweets(tweets, firecrawl_url)` → batch process
- Fallback: si Firecrawl no responde, link sin summary

### obsidian_writer.py
- `write_feed_note(tweets, vault_path, date)` → escribe `X/Feed/YYYY-MM-DD.md`
- `write_bookmark_note(tweets, vault_path, date)` → escribe `X/Bookmarks/YYYY-MM-DD.md`
- Formato: frontmatter + entries con callouts + format kepano

### state.py
- `load_state(path)` → carga state.json
- `save_state(path, state)` → persiste
- `is_new(tweet_id, state)` → check dedup
- `update_state(state, tweets)` → agrega nuevos IDs + timestamps

### config.py
- `load_config(path)` → carga config.yaml, valida campos requeridos
- `Config` dataclass con todos los settings

## Data Flow
```
run.py
  │
  ├── load_config("config.yaml")
  ├── load_state("state.json")
  ├── auth.load_session("cookies/state.json")
  │     └── if no cookies → ERROR: run auth.py --login first
  │
  ├── browser = playwright.chromium.launch(headless=True)
  ├── context = browser.new_context(storage_state=cookies)
  │
  ├── timeline_tweets = scraper.scrape_timeline(context)
  ├── bookmark_tweets = scraper.scrape_bookmarks(context)
  ├── like_tweets = scraper.scrape_likes(context, handle)
  │
  ├── all_tweets = timeline_tweets + bookmark_tweets + like_tweets
  ├── new_tweets = [t for t in all_tweets if state.is_new(t.id)]
  ├── tech_tweets = filter.filter_tweets(new_tweets, keywords)
  │
  ├── enriched = enrich.enrich_tweets(tech_tweets, firecrawl_url)
  │
  ├── obsidian_writer.write_feed_note(timeline_tech, vault, today)
  ├── obsidian_writer.write_bookmark_note(bookmark_tech, vault, today)
  │
  ├── state.update(new_tweets)
  ├── state.save("state.json")
  │
  └── browser.close()
```
