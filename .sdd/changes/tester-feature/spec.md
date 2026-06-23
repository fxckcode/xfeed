# Spec: Auto-tester Feature

## Requirements
- [ ] REQ-T1: Detectar proyectos en tweets (GitHub, npm, PyPI)
- [ ] REQ-T2: Clonar repo/instalar paquete en X/Bookmarks/{project-name}/
- [ ] REQ-T3: Probar: instalar deps, correr --help, verificar funcionamiento
- [ ] REQ-T4: Escribir REVIEW.md con documentación de la prueba
- [ ] REQ-T5: State para evitar re-testear projects ya probados
- [ ] REQ-T6: No duplicar — same tweet = same project = una sola review

## Scenarios
### Happy Path
1. Tweet tiene link a github.com/org/repo → detectado como GitHub repo
2. `git clone` en X/Bookmarks/repo-name/
3. Lee package.json/pyproject.toml → instala deps
4. Corre `--help` → captura output
5. Escribe REVIEW.md con hallazgos
6. Guarda en state como tested

### Edge Cases
- Link acortado (t.co) → seguir redirect primero
- Repo que ya existe en X/Bookmarks/ → skip (ya tested)
- Proyecto que falla al instalar → REVIEW.md documentando el error
- Repo sin README ni binarios → REVIEW con lo que se pueda determinar
