# Spec: xfeed-core

## Requirements

### Functional
- [ ] REQ-F1: Scrapear Home Timeline de X y extraer tweet data (text, autor, fecha, URL, links)
- [ ] REQ-F2: Scrapear Bookmarks de X (x.com/i/bookmarks)
- [ ] REQ-F3: Scrapear Likes de un usuario de X
- [ ] REQ-F4: Login one-time con captura de cookies/storage state de Playwright
- [ ] REQ-F5: Filtrar tweets por keywords tech configurables (AI, Hermes, Codex, Claude, agent, tool, etc.)
- [ ] REQ-F6: Enriquecer links de tweets via Firecrawl self-hosted → markdown summary
- [ ] REQ-F7: Escribir notas .md en Obsidian con frontmatter, tags, callouts (kepano format)
- [ ] REQ-F8: Dedup — no guardar el mismo tweet dos veces
- [ ] REQ-F9: State persistence — saber qué tweets ya se procesaron
- [ ] REQ-F10: Configurable via YAML (vault path, X handle, keywords, Firecrawl URL)

### Non-Functional
- [ ] REQ-NF1: Sin dependencias de API paga de X — 100% browser automation
- [ ] REQ-NF2: Corre cada 6hs via cron sin intervención humana
- [ ] REQ-NF3: Si la sesión de X expira, loguear warning y no crash
- [ ] REQ-NF4: Tipo annotations en todo el código Python (ECC standard)
- [ ] REQ-NF5: Ruff + Black para linting y formato
- [ ] REQ-NF6: Tests con pytest (mínimo 80% coverage en core modules)

## Scenarios

### Happy Path
1. Usuario ejecuta `python src/auth.py --login` → se abre browser → usuario loguea en X → cookies guardadas
2. Usuario configura `config.yaml`
3. Usuario ejecuta `python run.py` (o corre cron)
4. Script carga cookies → Playwright headless navega a timeline/bookmarks/likes
5. Extrae tweets → filtra tech → enriquece links con Firecrawl
6. Escribe notas .md en Obsidian
7. Actualiza state.json
8. Output: archivos en `X/Feed/2026-06-23.md` y `X/Bookmarks/2026-06-23.md`

### Edge Cases
- Sesión de X expirada → log warning, skip scrape, no crash
- Firecrawl no disponible → fallback: guardar links sin enrichment
- Tweet sin links → guardar tweet sin enrichment
- Tweet con muchos links (thread) → enrich cada link
- Ya no hay tweets nuevos → state dedup → no escribe nada (no duplica)
- Playwright timeout → retry 1 vez, si falla de nuevo log error y abort

### Error Cases
- No hay cookies guardadas → error claro: "Ejecutá python src/auth.py --login primero"
- config.yaml inválido → validar al inicio, error con qué campo falta
- Playwright no instalado → error claro con instrucciones de instalación
- Directorio de vault no existe → crearlo automáticamente

## Data Schemas

### Tweet Data (internal dict)
```python
{
    "id": "1234567890",           # X tweet ID
    "url": "https://x.com/user/status/1234567890",
    "author": "@username",
    "author_display": "User Name",
    "text": "Tweet content here...",
    "created_at": "2026-06-23T10:30:00Z",
    "source": "feed | bookmark | like",
    "hashtags": ["#AI", "#tools"],
    "mentions": ["@otheruser"],
    "links": ["https://example.com/tool"],
    "is_reply": False,
    "is_retweet": False,
    "media_type": "photo | video | none"
}
```

### State JSON
```json
{
  "last_run": "2026-06-23T10:30:00Z",
  "seen_ids": ["1234567890", "0987654321"],
  "last_timeline_id": "1234567890",
  "last_bookmark_id": "0987654321",
  "last_like_id": "1122334455"
}
```

### Obsidian Note Format
```markdown
---
title: "📡 X Feed — 2026-06-23"
date: 2026-06-23
tags:
  - xfeed
  - feed
  - ai
  - tools
---

## 🐦 @username — *23 Jun 2026*

**Tweet**: [link](https://x.com/user/status/123)

{{text}}

**Tags**: #AI #tools #agents

**Links**:
- 🔗 [Tool Name](https://tool.io) — *Firecrawl summary of the tool*

---
```
