# Tasks: xfeed-core

## Dependency Order
T1 ← T2 ← T3 ← T4 ← T5 (secuencial estricto)

## Tasks

### T1: Project scaffold + Config + Auth (AFK · cmd)
- **Files:** `config.yaml.example`, `requirements.txt`, `src/__init__.py`, `src/config.py`, `src/auth.py`
- **Acceptance:** config.yaml.example válido, auth.py puede hacer login y guardar cookies
- **Done condition:** `python -c "from src.config import load_config; from src.auth import login"` no da error
- **Dependencies:** ninguna
- **Estimated size:** medium

### T2: Scraper module (AFK · cmd)
- **Files:** `src/scraper.py`
- **Acceptance:** scrape_timeline(), scrape_bookmarks(), scrape_likes() funcionan con sesión válida
- **Done condition:** módulo importable, funciones tipadas, la lógica de extracción de tweets está completa
- **Dependencies:** T1
- **Estimated size:** medium

### T3: Filter + Enrich modules (AFK · cmd)
- **Files:** `src/filter.py`, `src/enrich.py`
- **Acceptance:** filter.is_tech_tweet() funciona con keywords, enrich.enrich_links() scrapea via Firecrawl
- **Done condition:** módulos importables, tipados, firecrawl enrichment con fallback
- **Dependencies:** T1
- **Estimated size:** medium

### T4: Obsidian writer + State manager + Runner (AFK · cmd)
- **Files:** `src/obsidian_writer.py`, `src/state.py`, `run.py`
- **Acceptance:** run.py ejecuta pipeline completo: scrape → filter → enrich → write → state update
- **Done condition:** `python run.py` ejecuta sin error (falla graceful si no hay cookies)
- **Dependencies:** T2, T3
- **Estimated size:** large

### T5: Tests + README + Git setup (AFK · cmd)
- **Files:** `tests/`, `README.md`, `.gitignore`, `LICENSE`, `pyproject.toml`
- **Acceptance:** pytest pasa, README explica setup, .gitignore cubre Python
- **Done condition:** `pytest` corre y tests pasan
- **Dependencies:** T4
- **Estimated size:** medium
