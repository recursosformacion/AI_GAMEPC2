# F4 — Migración de la búsqueda web a V2.1 y retirada de V1 (plan de corte)

**Estado:** análisis de corte (2026-09-09), sin cambios de código todavía.
**Decisiones ya tomadas:** F4 llega después de F3 (ADR-0035, Anexo B); en la web se
**conserva el orden actual** de resultados (decisión 2026-09-09): F4 sustituye el agrupador
de visualización, no reordena las obras por `DefaultWorkRanker` (eso queda como mejora
opcional posterior).

## Estado de ejecución

- **F4.A ✅ (2026-09-09)** — `WorkGrouper.group` emite ahora el `WorkGroup` de `domain/`
  (frozen, con propiedades compatibles `key` y `primary`); eliminado el `WorkGroup`
  `__slots__` de `work_grouper.py`. `work_merge_service` reexporta el de dominio;
  `resource_resolver` importa de `domain`. Algoritmo de visualización y orden intactos.
- **F4.B ✅ (automático)** — `_run_search`/`_focused_representations`/CLI consumen ya el
  `WorkGroup` de dominio (la fachada devuelve el tipo unificado); DTO/filtros sin cambios.
- **F4.C ✅ (2026-09-09, decisión cambiada: adoptar V2.1)** — La búsqueda web **ya no
  ordena por el rank V1**: `engine.gather()` recolecta candidatos sin `DefaultRankingEngine`
  (nuevo método público del `WorkResolutionEngine`) y `_run_search` agrupa con `WorkGrouper`
  y **ordena las obras por `DefaultWorkRanker` (V2.1)**: representaciones → evidencia →
  grupo → score de obra → presentación ordenada (criterio explicable). `SearchResultItem.score`
  pasa a ser el score de la obra V2.1. Añadidos al container: `work_ranker()` y
  `work_ranking_policy()`. **Nota**: `DefaultRankingEngine`/`RankingConfig` V1 siguen
  usados por la resolución de una sola obra (`resolve()`), el CLI y el motor de compositores;
  su retirada es el siguiente paso (F4.E), ya sin afectar a la agrupación web.
- **F4.D ✅** — `test_golden_dataset` verde (27/27 tras el ajuste de matcher). La suite de
  búsqueda (`test_platform_api`) no fijaba orden y sigue verde con el nuevo contrato
  semántico (sin regresión: 21/21 salvo 501 alineado).
- **F4.E ⏳ (E1+E2 ejecutados el 2026-09-09)** —
  - **E1 ✅**: `WorkComposerMatcher` pasa a `engine.gather(...).candidates` (fase catálogo
    sin ranking V1).
  - **E2 ✅**: `WorkResolutionEngine.resolve()` reescrito a V2.1: `gather` → `WorkGrouper`
    → `DefaultWorkRanker` (mejor obra) → representaciones por `_sort_key` (preferencia de
    adquisición, misma selección efectiva) → evidencia estructural V2.1
    (`_build_evidence`, sin `EvidenceEngine`/`rank_detailed`). La forma de `ResolveResult`
    y los tipos de `domain/` se conservan; los 8 tests del engine y las suites de
    compositores/CLI/plataforma siguen verdes.
  - **Retirada final (2026-09-11)**: el **CLI ya no usa `engine.rank()`** (migrado a V2.1 con
    `_ordered_candidates`: gather → WorkGrouper → DefaultWorkRanker → aplanado por
    preferencia). `engine.rank()` sobrevive **solo** para su test unitario y el harness
    offline `tests/fusion/`; `DefaultRankingEngine`, `RankingConfig` V1, `score_ranking`,
    `evidence_engine` e `IRankingEngine` quedan como deuda de retirada (sin consumidores de
    producto).

## F4.E — espiga de diseño (2026-09-09, read-only)

**Inventario de consumidores de `WorkResolutionEngine` tras F4.C:**

| Consumidor | Uso actual de V1 | Migración |
|---|---|---|
| `infrastructure/resolvers/work_match.py` (`WorkComposerMatcher`) | `engine.resolve(...)` y recorre `result.ranking` para emitir `(provider, composer)` | **E1**: usar `engine.gather(...).candidates` (solo recorre el conjunto; el orden no importa). Sin cambio semántico. |
| `cli/main.py` (comandos interactivos) | `engine.rank` (3 sitios) + `engine.resolve` + `result.evidence` | **E2**: ver pipeline V2.1 de obra única abajo. |
| `use_cases/resolve_work.py` (wrapper) | delega en `engine.resolve` | se conserva como envoltorio sobre la nueva implementación. |
| `domain/pipeline_context.py` (result opcional) | contenedor de `ResolveResult` | sin consumidores reales; se ajusta o elimina al final. |

**Pipeline V2.1 de obra única (E2):**
1. `gather()` → candidatos (sin V1).
2. `WorkGrouper.group()` → `WorkGroup`s de dominio.
3. `DefaultWorkRanker.rank(..., RankingContext(query))` → mejor obra (primer `order`).
4. Dentro de la mejor obra: representaciones ordenadas por preferencia de adquisición
   (`work_merge_service._sort_key`), que es el criterio actual de `resolve()` cuando recibe
   representaciones dadas → se preserva la selección efectiva.
5. Evidencia V2.1: `DefaultMergeService.merge` (descriptiva + conflictos) + razones del
   `RankingScore` del grupo + contribuidor de preferencia de la representación elegida
   (`EvidenceCode.SELECTED_REPRESENTATION`), empaquetadas como `EvidenceResult`.
6. `ResolveResult` mantiene su forma (`ranking`, `evidence` pasan a contener las piezas
   V2.1 convertidas al tipo `Evidence` actual para compatibilidad de `domain/`/CLI).

**Retirada final tras E1+E2:** `DefaultRankingEngine`, `domain/ranking_config.py`
(`RankingConfig` V1), `domain/score_ranking.py` (si queda huérfano), `evidence_engine` V1,
`IRankingEngine`, `engine.rank()` y el `_ranking_engine`/`_config`/`_evidence_engine` de
`WorkResolutionEngine`. Documento del pipeline (architecture book §5) alineado.

Verificación F4.A: ruff ✅ · mypy (236) ✅ · 104 tests de agrupador/consumidores ✅ ·
`test_golden_dataset` (27 casos) **✅ al completo**: los 7 fallos preexistentes se corrigieron
con un ajuste acotado del matcher (`work_grouping_matcher.py`): la ausencia de metadatos ya
no se trata como conflicto, los títulos-genérico solo se fusionan con detalle unidireccional
si hay anclaje (mismo número, o un lado sin identificadores frente a uno con catálogo), y la
clave tolera tónica sin modo explícito ("A" ≈ "A major"). Verificado sin regresiones
(91 + 132 + plataforma ✅, único fallo el 501 preexistente).

## Inventario de la cadena actual (búsqueda web)

1. `platform.py:_run_search` (864–1023) y `_focused_representations` (1248–1282):
   - obtienen candidatos planos con `WorkResolutionEngine.rank()` (V1 `DefaultRankingEngine`);
   - agrupan para pantalla con `container.work_merge_service().group(ranked)` →
     `WorkGrouper` (algoritmo `WorkGroupingMatcher` con umbrales y `MergeDecision`);
   - consumen del grupo resultante (`WorkGroup` `__slots__` de `work_grouper.py`):
     `group.work.{work_id,title,composer,catalogue_number,key?}` y `group.representations`;
   - filtran por compositor/título/catálogo/formats/providers y construyen `SearchResultItem`
     sin cambiar el orden de `rank()` (first-seen) → con la decisión tomada, este orden se
     **conserva**.
2. Otros consumidores del agrupador/`WorkGroup` `__slots__`:
   - `application/canonical_metadata.py` (`MetadataEnricher.enrich(group)` usa `group.key`,
     `group.work`, `group.representations`);
   - `application/resource_resolver.py` (`group.key`);
   - `cli/main.py` (agrupación de resultados para el CLI);
   - `work_merge_service.py` (fachada: reexporta `WorkGroup`, `_sort_key`).

## Por qué no se sustituye a ciegas

- **Membresía**: `WorkGroupingMatcher` agrupa por similitud umbral (p. ej. variantes de una
  misma página); el clúster por identidad `MatchLevel.SAME` de la pipeline de sesiones puede
  dividir lo que el agrupador actual une. Cambiar la membresía altera el número y contenido
  de los resultados mostrados.
- **Descriptor de visualización**: `WorkGrouper` construye `work` canónico con
  `MetadataNormalizer` (display limpio, `canonical_title`, `canonical_key`, catalogue/key/opus
  extraídos del título). El clúster V2.1 actual usa el descriptor crudo del primer miembro.
  Un reemplazo directo cambiaría títulos mostrados.

## Plan de corte (slices verificables, sin retirar nada hasta el final)

**F4.A — Unificar `WorkGroup` conservando el algoritmo de visualización.**
- Portar el resultado de `WorkGrouper.group` al `WorkGroup` de `domain/` (frozen) manteniendo
  la construcción canónica actual y el orden estable actual (`_sort_key`).
- Los campos `key`/`primary`/`canonical_score` del `__slots__` se expresan sobre el de dominio:
  `key = canonical_key` (o `work_id`), `primary = representations[0]`, y `canonical_score` se
  sustituye por la score del ranking V2.1 o se elimina (migrando sus consumidores).
- Migrar consumidores de `work_grouper.WorkGroup` a `domain.WorkGroup` (canonical_metadata,
  resource_resolver, cli, work_merge_service) y tests asociados. `WorkGrouper` sigue siendo el
  productor de visualización (algoritmo intacto) pero emite el tipo de dominio → **un único
  `WorkGroup`** (cierra el hallazgo 2).
- Verificación: golden de búsquedas (títulos, nº de grupos, orden) idéntico antes/después.

**F4.B — La búsqueda web consume el grupo de dominio directamente.**
- `_run_search`/`_focused_representations`: `engine.rank()` (adquisición/orden V1, se mantiene
  por la decisión de orden) → `work_merge_service().group()` devuelve ya `WorkGroup` de dominio
  (vía F4.A) → se elimina la dependencia del `WorkGroup` `__slots__`.
- Los filtros/DTO `SearchResultItem` quedan intactos.

**F4.C — Retirada de V1 (solo cuando no queden consumidores).**
- Migrar `cli/main.py`, `WorkComposerMatcher` y (si vive) `app.py` a la pipeline V2.1 sobre
  `WorkGroup` de dominio.
- Retirar: `DefaultRankingEngine` (`infrastructure/rankings`), `domain/ranking_config.py`
  (`RankingConfig` V1), `domain/score_ranking.py` si queda huérfano, `evidence_engine` V1 si se
  sustituye por `DefaultEvidenceCollector`, y `WorkResolutionEngine` cuando sus consumidores
  migren.
- Retirar `work_grouper.py` `__slots__` y `work_merge_service.py` (o reducirla a fachada sobre
  el nuevo camino).
- Alinear `osap-architecture-book.md` §5 con el flujo real.

**F4.D — Cierre.**
- `WorkGroup` único en `domain/`; `application/__init__.py` exporta el de dominio; suite
  completa verde (ruff/mypy/pytest); docs alineadas.

## Fuera de alcance (decisión tomada)

- No reordenar las obras por `DefaultWorkRanker` en la web en F4 (opcional posterior).
- No tocar `V21UniverseResolver` de sesiones (F3, ya canónico) en estos slices.
- No tocar `app.py` (retirada cuando no queden consumidores, carril aparte).
