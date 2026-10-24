# Documentación de OSAP

Documentación organizada por **versión general**. Los contratos (`domain/` y `ports/`)
son **API pública congelada**: cambiarlos requiere un ADR.

```
osap/
├── v1/     Base / pre-V2 (arquitectura, API REST, frontend, jobs, datasets, ...)
├── v2/     V2: contratos y diseños congelados
│           · osap-architecture-book.md (fuente de verdad técnica)
│           · architecture-audit.md   (Auditoría 2026, congelada)
│           · provider-contract.md    (Contrato de proveedores)
│           · search-engine-design.md (Search Intelligence V2.1)
│           · normalization-explorable.md (Normalización explicable V2.1.1)
│           · work-matcher-design.md  (WorkMatcher V2.1.2)
│           · ranking-design.md       (Ranking de obras V2.1.3)
│           · evidence-design.md      (Evidence definitivo V2.2.a)
│           · dedup-merge-design.md   (Dedup/Merge V2.2.b)
│           · jobs-design.md          (Jobs V2.2.c)
│           · knowledge-mining-design.md (Knowledge Mining V2.2.d)
│           · web-docs.md             (documentación web)
│           · presentation-v22.md     (presentación 20 diapositivas)
├── v3/     V3: plataforma
│           · api-design.md           (API REST, contrato congelado V3.1.a)
├── adr/    Architecture Decision Records (0001–0037)
└── old/    Documentos obsoletos (histórico, no se editan)
```

## Para empezar a trabajar

- **`dev-environment.md`** — **LEER PRIMERO**: cómo levantar el entorno (Apache `osap-app`
  sirve `web/dist` y proxya `/api` a uvicorn 8001). Cómo hacer cambios de frontend
  (rebuild `web/dist`) y de backend (reiniciar uvicorn). Evita errores conocidos.

## Documentos fundamentales

1. `v2/osap-architecture-book.md` — **fuente de verdad técnica** de OSAP V2.2.
2. `v2/architecture-audit.md` — Auditoría arquitectónica (congelada).
3. `ROADMAP.md` (raíz) — versiones de plataforma.
4. `v2/provider-contract.md` — contrato de proveedores.
5. `v2/search-engine-design.md` — diseño del Search Intelligence.

Chorus (producto independiente): `docs/chorus-vision.md` (visión),
`docs/chorus-product.md` (producto/MVP), `docs/chorus-separation.md` (frontera OSAP ≠ Chorus),
`docs/chorus-web.md` (web independiente).

## Mejoras pendientes (anotadas)

- **Pendientes 2026-10-21** (`pending.md`): integración del módulo externo
  `ai-recogeYouTube` (búsqueda global + valoraciones, correspondencia de obras y cuota) y
  estado de las fuentes externas de partituras (BNE, BnF, BL, DNB, LOC, Europeana, Cantorion,
  Gallica).
- **Ficha de PROD SSR** (`prod-ssr-plan.md`): runbook completo para desplegar el HTML SSR
  React (Node 3000, systemd, nginx, caché, verificación y rollback), con fechas y versión
  pendientes de rellenar.
- **Subida 5.5.0** (`release-5.5.0.md`): checklist de la entrega actual con mantenimiento en
  servidor, verificación por `?preview` y rollback; **no** incluye el SSR de React.
- **Mantenimiento y token de revisión** (`maintenance.md`): cómo activar/desactivar y dónde
  está el enlace `?preview=<TOKEN>` (impreso por el script y en `web/dist/maintenance.token`).
- **V6 — Work/Resource/File** (`v6-work-resource-model.md`): plan para sustituir los tres
  niveles actuales (storage works, índice index_works, representaciones/ficheros) por un
  modelo con Work + Resource + File, reparto de campos, IDs estables, migración y preguntas
  abiertas. Es un cambio **A (major)**: exige punto de control antes de empezar.
- **Estudio YouTube / ai-recogeYouTube** (`ai-recogeyoutube-integration-study.md`): botón en
  la ficha de obra, pantalla nueva dentro de OSAP, búsqueda/voto, arquitectura de invocación,
  asociación de obras, cuota y fases. Sin implementar.

- **Catálogo de formaciones vocales (voicings)**: además de los términos normalizados de
  búsqueda (`SATB`, `STTB`, `AATB`, `ATTB`, …), valorar una tabla/catálogo de voicings con
  pequeña descripción de cada formación (voces, uso típico) para filtros/presentación.
  Pendiente de decidir dónde vive (corpus CPDL/osap-storage) y si aporta valor real.
- **Compositores desde CPDL**: posibilidad de importar compositores de CPDL si nos interesa
  (evaluar coste/beneficio antes de construir el importer).
- **Cron semanal de CPDL**: crear un proceso programado (cron) que actualice semanalmente
  las works de CPDL (`import_cpdl_pages`/reindex de corpus) de forma reproducible.
