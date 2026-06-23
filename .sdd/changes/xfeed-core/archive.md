# Archive: xfeed-core

## Summary
- **Intent:** Pipeline automático X → Obsidian, scraping feed/bookmarks/likes con Playwright + Firecrawl
- **Implementation:** 6 módulos Python + tests + run.py orquestador
- **Verification:** PASS (Ruff clean + 31/31 tests)

## Files Created
| File | Purpose |
|------|---------|
| `src/config.py` | YAML config loader with pydantic validation |
| `src/auth.py` | Playwright login + cookie management |
| `src/scraper.py` | Scrape timeline/bookmarks/likes via Playwright |
| `src/filter.py` | Tech keyword filter |
| `src/enrich.py` | Firecrawl link enrichment |
| `src/obsidian_writer.py` | kepano/obsidian-skills formatted .md writer |
| `src/state.py` | JSON state + dedup manager |
| `run.py` | Pipeline orchestrator |
| `config.yaml.example` | Example configuration |
| `tests/` | 6 test files + conftest, 31 tests |
| `README.md` | Full documentation |
| `LICENSE` | MIT |
| `.gitignore` | Python/cookies/state ignores |
| `pyproject.toml` | Ruff + pytest config |

## ADRs Created
- ADR-1: Playwright session persistence (no API key)
- ADR-2: Firecrawl for link enrichment
- ADR-3: Tech filter by configurable keywords
- ADR-4: kepano/obsidian-skills note format
- ADR-5: ECC coding standards

## What Was Learned
- httpx.AsyncClient mocking with async context managers is tricky — pytest-httpx is the right tool
- X.com uses data-testid attributes for testing which are great for scraping selectors
- Playwright storage_state persists cookies + localStorage in one file
- Firecrawl self-hosted API is simple: POST /v1/scrape with URL + formats

## Next Steps
- [ ] Crear GitHub repo y pushear
- [ ] Configurar cron cada 6hs
- [ ] Login inicial en X (auth.py --login)
- [ ] Probar pipeline completo con sesión real
