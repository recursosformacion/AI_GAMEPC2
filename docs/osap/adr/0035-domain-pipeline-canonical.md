# ADR-0035 – Pipeline canónica de decisión y deuda estructural (V2.1/V3)

## Estado

Aceptado (2026-09-09). Registra las decisiones D1/D2/D3 tomadas tras la auditoría
`docs/osap/code-audit-2026.md` (Anexo B).

## Contexto

La auditoría detectó que conviven **tres flujos de decisión** en `src/osap/`:

1. **V1 (legacy, activo)** — `WorkResolutionEngine` + `DefaultRankingEngine`
   (`infrastructure/rankings/`) sobre `CandidateRepresentation` planos. Usado por la
   búsqueda web (`platform.py:_run_search`, `_focused_representations`), el CLI,
   `WorkComposerMatcher` y `api/app.py`.
2. **V2.1 (dominio puro, no cableado)** — la pipeline del ADR-0022/0027:
   `Canonicalizer → DefaultWorkMatcher → WorkGrouper → DefaultWorkRanker →
   DefaultMergeService → EvidenceCollector → KnowledgeMiner`. Implementada en
   `domain/` + `application/` con tests de integración
   (`test_search_intelligence_pipeline`, `test_merge_service`, `test_evidence_collector`,
   `test_knowledge_mining`) pero **sin consumidores en runtime**.
3. **V3 (sesiones)** — `infrastructure/resolution/` (`AcquisitionService`,
   `provider_acquirer`, `universe_matching`, `work_ranker.decide`) + `resolution_store`
   (ADR-0033/0034). Trabaja con **dicts JSON** en vez de objetos de dominio.

Además: `api/app.py` (legacy) y `api/platform_app.py` (V3.1, producción) son dos entradas
FastAPI solapadas, y `DefaultKnowledgeMiner`/`DefaultKnowledgeCollector` nunca se cablean.

## Decisión

### D1 — La pipeline V2.1 (dominio puro) es la capa canónica de decisión

- La vía V3 de sesiones **debe consumir los componentes de dominio** (V2.1) y eliminar la
  capa de decisión por dicts JSON (`decide()` en `infrastructure/resolution/work_ranker.py`).
- Se introduce una **capa de adaptación** que reconstruye objetos de dominio
  (`CandidateRepresentation`/`WorkGroup`) a partir de la salida de los acquirers, y se
  sustituye `decide()` por `DefaultWorkRanker` + `DefaultMergeService` + evidence, por grupo
  del universo.
- La vía V1 queda **legacy**: la búsqueda web se migra a V2.1 **solo después** de que la
  integración en sesiones (F3) esté demostrada con tests.
- `WorkGroup` se mueve a `domain/` (única definición) para que dominio y puertos no dependan
  de `application/`.

### D2 — `api/app.py` queda deprecada

- `platform_app.py` (`create_platform_app`, V3.1) es la **única entrada de producción**.
- `create_app` se marca deprecated en `api/__init__.py`; no se añaden rutas nuevas a
  `app.py`; `tests/osap/test_api.py` migra a `test_platform_api.py` progresivamente.
- Retirada de `app.py` cuando no queden consumidores. **Ejecutado el 2026-09-09**: no
  quedaban consumidores en runtime; `src/osap/api/app.py` y su suite de compatibilidad
  `tests/osap/test_api.py` fueron eliminadas. `api/__init__.py` solo documenta.

### D3 — Knowledge Mining sin cablear hasta V3.3 (intencional)

- `DefaultKnowledgeMiner`/`DefaultKnowledgeCollector` y sus tests se conservan.
- No se produce observaciones ni sugerencias en runtime hasta V3.3 (aplicación humana de
  sugerencias, conforme al ADR-0027). La vía de conexión prevista es: sesión terminal →
  observaciones → `DefaultKnowledgeCollector` → `DefaultKnowledgeMiner` →
  `KnowledgeStore`.

## Consecuencias

- Elimina la ambigüedad de `RankingConfig`/`WorkGroup` (dos clases homónimas) y la violación
  de dependencia domain→application.
- Sustituye el determinismo basado en `abs(hash())` (no determinista entre procesos) por
  digests estables.
- La búsqueda web mantiene comportamiento V1 hasta que la migración (F4) esté validada; el
  contrato REST público (V3.1) no cambia durante la transición.
- `knowledge` permanece como subsistema aislado y testeado; el `KnowledgeStore` actual queda
  como lector en memoria.

## Plan de ejecución

Ver `docs/osap/code-audit-2026.md`, Anexo B (fases F0→F5). El diseño del puente
sesión↔V2.1 (espiga F3) está en `docs/osap/v21-session-bridge-design.md`.
