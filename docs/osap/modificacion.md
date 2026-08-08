# Modificación (registro de trabajo)

## 2026-08-08 — Provider API v1.3 + UX de lista de obras + limpieza de legacy

### Entorno (importante)
- El desarrollo se sirve con **Apache `osap-app`** (web/dist + proxy `/api` → uvicorn 8001).
  **NO** usar `vite dev`. Ver `docs/osap/dev-environment.md` y `AGENTS.md`.

### Frontend — lista de obras (ComposerPage + CandidatesPage)
- Al pulsar una línea se abre un **panel inline** en la misma ventana (empuja al resto
  hacia abajo, cierra cualquier otra abierta).
- Representations tabuladas: **Título / Autor / Acción (View)**.
- **Eliminada** la navegación a `/resolution` desde la lista (ya no aparece el aviso
  "Se han encontrado varias obras compatibles" al pulsar una línea).
- Archivos: `web/src/pages/ComposerPage.tsx`, `web/src/pages/CandidatesPage.tsx`.
- Estado: **rebuildado `web/dist`**, funcional en `http://osap-app` (desarrollo).

### Backend — capa de proveedores v1.3
- Nueva capa declarativa (YAML) + `RemoteCatalogProvider` genérico + arquitectura 3 niveles.
- Detalles: `docs/osap/providers-layer.md`.

### Limpieza de legacy (ejecutada)
- Eliminados proveedores antiguos (IMSLP/OpenScore/OMR), **PDMX**, infraestructura de
  **datasets** y **HuggingFace**.
- Verificado: ruff, mypy y 342 tests pasan.

### Despliegue a producción (ÚLTIMA ACCIÓN, verificar)
- Se hizo `git push` de V3.4 (tag v3.4.0) a `origin/main`.
- **PENDIENTE de confirmar**: el comportamiento de producción (letrero + líneas no
  clicables) se corrigió en desarrollo, pero **aún no se ha confirmado** que el fix de
  `ComposerPage` esté desplegado en producción. Revisar antes de dar por cerrado.
