# Proposal: Auto-tester — clone + test + review tools from tweets

## Intent
Cuando un tweet en el feed/bookmarks contiene links a proyectos/herramientas (GitHub, npm, PyPI), clonarlos automáticamente, probarlos, y dejar una review documentada en Obsidian.

## Scope
### In
- [x] Detectar GitHub repos, npm packages, PyPI packages en links de tweets
- [x] Clonar/instalar en `X/Bookmarks/{project-name}/`
- [x] Probar el proyecto (instalar deps, correr --help, verificar funcionamiento básico)
- [x] Escribir REVIEW.md con: qué hace, cómo se usa, opinión
- [x] State para no re-probar projects ya tested
- [x] Integración en run.py pipeline

### Out
- [ ] Pruebas de UI/visuales
- [ ] Análisis de código profundo
- [ ] Benchmarks de rendimiento

## Tech Stack
| Módulo | Tecnología |
|--------|-----------|
| src/tester.py | subprocess + git + pip + npm |
| Proyectos clonados | X/Bookmarks/{name}/ |
| Reviews | X/Bookmarks/{name}/REVIEW.md |

## Risks
| Riesgo | Mitigación |
|--------|-----------|
| Proyecto enorme (>500MB) | Skip con warning |
| Dependencias rotas | Log error, continuar |
| Script malicioso | Solo clonar, no ejecutar build scripts automáticos |
