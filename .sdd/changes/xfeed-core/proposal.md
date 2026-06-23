# Proposal: xfeed — X/Twitter Feed → Obsidian Pipeline

## Intent
Pipeline automático y gratuito que scrapea el feed, bookmarks y likes de X (Twitter) usando Playwright + Firecrawl, filtra contenido tech (AI, Hermes, Codex, Claude, herramientas, agentes), y lo persiste como notas estructuradas en Obsidian siguiendo kepano/obsidian-skills. Corre cada 6hs vía cron.

## Scope

### In
- [x] Scraping de Home Timeline (`x.com/home`) via Playwright con sesión persistente
- [x] Scraping de Bookmarks (`x.com/i/bookmarks`) via Playwright
- [x] Scraping de Likes (`x.com/{handle}/likes`) via Playwright
- [x] Login one-time con captura de cookies/storage state (usuario loguea manualmente)
- [x] Extracción de tweet data: texto, autor, fecha, URL, links, hashtags, menciones
- [x] Filtro por keywords tech: AI, LLM, Hermes, Codex, Claude, agent, tool, framework, Python, JS/TS, coding, etc.
- [x] Firecrawl enrichment: para cada link en tweets filtrados, scrapea la página destino y extrae resumen/summary
- [x] Obsidian writer: genera notas .md con frontmatter, wikilinks, callouts, tags (kepano format)
- [x] Estructura en vault: `X/Feed/YYYY-MM-DD.md` y `X/Bookmarks/YYYY-MM-DD.md`
- [x] State manager: dedup por tweet ID, evita duplicados entre runs
- [x] Cron job cada 6 horas via Hermes cron
- [x] Documentación del proyecto en Obsidian (tutorial de setup, qué hace cada parte)
- [x] GitHub repo público con README, LICENSE MIT, .gitignore

### Out
- [ ] Instagram / otras redes sociales (fase 2)
- [ ] API oficial de X (requiere pago)
- [ ] Análisis automático de herramientas (que yo pruebe cada una — eso lo hacemos manual/on-demand)
- [ ] Interfaz gráfica o web
- [ ] Scraping de DMs o notificaciones

## Approach

### Arquitectura
```
run.sh (entry point, cada 6hs)
  │
  ├── src/auth.py          → Login one-time + cookie management
  │
  ├── src/scraper.py       → Playwright headless: timeline + bookmarks + likes
  │     │                    Extrae: tweet data en dicts
  │     │
  │     └── src/filter.py  → Filtra por keywords tech (configurable)
  │
  ├── src/enrich.py        → Firecrawl: scrapea links de tweets → markdown summaries
  │
  ├── src/obsidian_writer.py → Genera .md en vault/ (kepano format)
  │
  └── src/state.py         → State JSON: últimos tweet IDs vistos (dedup)
```

### Data Flow
1. Playwright carga cookies saved → navega a X
2. Scrapea timeline (~20 tweets), bookmarks (~20), likes (~20)
3. Filtra por tech keywords → solo posts relevantes
4. Para cada post: extrae links → Firecrawl scrapea la página destino → summary markdown
5. State check: ¿ya vimos este tweet? Si sí, skip. Si no, procesar.
6. Genera notas .md en Obsidian
7. Actualiza state.json

### Tech Stack
| Capa | Tecnología | Justificación |
|------|-----------|---------------|
| Scraping | Playwright Python | Headless browser, cookies persistentes, anti-detección |
| Enriquecimiento | Firecrawl self-hosted (Docker) | Ya instalado local, da markdown limpio de URLs |
| Output | Obsidian Flavored Markdown | kepano/obsidian-skills format |
| Estado | JSON local | Simple, sin BD |
| Cron | Hermes cron | Nativo, no requiere setup externo |
| GitHub | MIT License | Open source tool para Hermes |

### Risks
| Riesgo | Mitigación |
|--------|-----------|
| X cambia DOM/selectors | Usar data-testid attributes (relativamente estables). Modular extractor para fácil parche |
| Sesión de X expira | Login one-time + script detecta y avisa cuando expira |
| Firecrawl offline | Fallback: guardar solo link sin enrichment |
| Rate limiting de X | Scrollear con delays aleatorios, max ~20 tweets por fuente |
| Duplicados | State dedup por tweet ID, idempotente por diseño |

## Tech Stack
| Capa | Tecnología | Justificación |
|------|-----------|---------------|
| Runtime | Python 3.11 | Ya instalado, Playwright soportado |
| Scraping | Playwright | Headless browser, session persistence |
| Enrichment | Firecrawl self-hosted | Ya disponible local |
| Output | Obsidian Flavored Markdown | kepano standards |
| Testing | pytest | Estándar Python |
| Linting | ruff + black | ECC coding standards |
| CI | GitHub Actions | pytest on push |

## Skill Resolution
- ECC `coding-standards` → ruff, black, type annotations
- `obsidian-markdown` → formato de notas
- `command-code` → cmd para implementación
- `git-setup-skill` → post-archive

## Modules Affected
- Ninguno (greenfield) — se crea `~/projects/xfeed/` completo
