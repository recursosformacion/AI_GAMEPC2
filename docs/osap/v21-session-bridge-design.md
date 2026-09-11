# F3 — Diseño del puente ResolutionSession ↔ pipeline V2.1

**Estado:** Espiga de diseño (2026-09-09). Read-only, sin cambios de código de producción.
**Autoridad:** estado F1 local (ADR-0035, `code-audit-2026.md`). Complementa al ADR-0035
(D1) y a los ADR-0033/0034.
**Objetivo:** fijar entrada, adaptador, salida y punto de sustitución para que la
resolución por sesiones use la pipeline canónica de dominio (Canonicalizer → Matcher →
WorkGrouper → DefaultWorkRanker → DefaultMergeService → Evidence) en vez de la capa de
dicts JSON de `infrastructure/resolution/`.

---

## 1. Flujo objetivo

```
HTTP POST /works/resolve  →  ResolutionSession (202 + session_id)
        │
        ▼
AcquisitionService  ── adquiere páginas (ProviderAdapterAcquirer / CatalogAcquirer)
        │              └─ persiste provider_results (ProviderWork ↔ JSON)  [ADR-0033]
        ▼
rebuild_universe()  ── lee SOLO provider_results (sin HTTP)  → ProviderWork tipados
        │
        ▼
┌─────────────────────────────────────────────────────────┐
│  ADAPTADOR SESSION → DOMAIN  (infrastructure/resolution)│
│                                                         │
│  ProviderWork (u objeto original si hay vía viva)       │
│        │                                                │
│        ▼                                                │
│  CandidateRepresentation (+ WorkDescriptor)             │
│  (no inventa datos que ProviderWork no expresa)         │
└─────────────────────────────────────────────────────────┘
        │
        ▼
V2.1 CANÓNICO (dominio/aplicación, sin dicts)
        │  Canonicalizer → DefaultWorkMatcher → WorkGrouper
        │  → DefaultWorkRanker → DefaultMergeService → EvidenceCollector
        │
        ▼
ResolutionDecisionPolicy  (reglas ADR-0034 → resolved|ambiguous|not_found)
        │
        ▼
Serializador determinista  →  resolution_items (mismo esquema de columnas que hoy)
        │
        ▼
GET /sessions/{id}/results  (API V3.1 sin cambios)
```

Regla de frontera: **los dicts JSON de `provider_results` son contrato de persistencia de
infraestructura** (ADR-0033 punto 5) y **nunca cruzan a `domain/`**. El dominio recibe
objetos tipados; la serialización a JSON ocurre solo en los bordes (persistencia y API).

---

## 2. Contrato de entrada de la pipeline V2.1 (objetos exactos)

La pipeline canónica trabaja exclusivamente con objetos de dominio; ningún componente
recibe dicts ni conoce `ProviderWork`:

| Componente | Entrada | Salida |
|---|---|---|
| `Canonicalizer.canonicalize(text)` | `str` (título crudo del proveedor) | `CanonicalResult` (forma canónica + `AppliedRule`) |
| `DefaultWorkMatcher.match(first, second)` | `WorkDescriptor` + `WorkDescriptor` | `MatchResult` (`MatchLevel`, `MatchReason`, `MatchField`) |
| `WorkGrouper.group(candidates)` | `tuple[CandidateRepresentation, ...]` | `tuple[WorkGroup, ...]` (dominio, `domain/work_group.py`) |
| `DefaultWorkRanker.rank(works, context, policy)` | `tuple[WorkGroup]`, `RankingContext`, `RankingPolicy` | `RankingResult` (`RankingScore` por grupo) |
| `DefaultMergeService.merge(group, policy)` | `WorkGroup` + `MergePolicy` | `MergeResult` (`MergedWorkDescriptor`, `provenance`, `conflicts`, `evidence`) |
| `DefaultEvidenceCollector.collect(contributors)` | `tuple[IEvidenceContributor]` (matcher/ranking/merge/selection) | `EvidenceResult` (`EvidenceItem` + `EvidenceSummary`) |

Campos que **V2.1 sí necesita** y de dónde salen en el puente:

- **Identidad de obra**: `WorkDescriptor.work_id, title, composer, catalogue_number, opus,
  key, genres, voices/instrumentation`. Proceden de `ProviderWork.identity` +
  `ProviderWork.metadata` (ver tabla de mapeo en §3). Los identificadores de autoridad
  (`identifiers`) solo si el proveedor los expresa; **el adaptador no los fabrica**.
- **Representación**: `format`, `license`, `public_domain`, `downloadable`, `download_url`,
  `view_url`, `remote_id` salen de `ProviderResource` (formato + links + license).
  `CandidateRepresentation` construida con: `candidate_id` estable por proveedor
  (`{provider}:{identity.id}`), `provider_id`, `confidence` desde `identity.confidence`.
- **Preferencias/usuario** (`RankingContext.user_preferences`): las sesiones actuales no
  transportan preferencias; se usa `UserPreferences()` por defecto (decisión de producto
  si más adelante el API las propaga).
- **Catálogo/normalización**: `Canonicalizer` se alimenta de las mismas reglas YAML que el
  resto de la plataforma (`resources/canonical` en tests); la clave de agrupación canónica
  se calcula igual que en `work_grouper._canonical` (título/compositor normalizados).

Datos que **V2.1 exige y el adaptador NO puede inventar** (riesgo asumido, ver §6):

- `QualityLevel` y `completeness`: `ProviderWork` no los expresa hoy. No se pueden derivar
  con honestidad → valor conservador por defecto (`UNREADABLE`, `1.0` como hoy en
  `CandidateRepresentation`). Si la sesión debe rankear por calidad, primero hay que
  ampliar el contrato v1.3 o poblar por formato/validación posterior (`ScoreValidationStage`).
- `checksum`, `edition`, `date_added`: no presentes → `None`. No inventar.
- Atribución `Anonymous/Traditional`: nunca generada por el adaptador (ADR-0034). Solo se
  propaga si el proveedor la expresa como valor literal de `identity.composer`.

---

## 3. El adaptador: `provider_results → objetos de dominio`

**Dónde vive:** `src/osap/infrastructure/resolution/domain_adapter.py` (infraestructura:
lee `ProviderWork`/JSON y emite objetos de dominio; nunca al revés).

**Dos vías de entrada** (importante para no perder datos):

1. **Vía viva (sin pérdida):** cuando la sesión se resuelve en el mismo proceso que
   adquirió, los acquirers ya poseen objetos de dominio antes de serializar. `CatalogAcquirer`
   convierte hoy `CandidateRepresentation → ProviderWork` de forma **pérdida** (descarta
   quality/checksum/edition/voices/genres…). Propuesta: extender `AcquiredPage` con
   `candidates: tuple[CandidateRepresentation, ...]` opcional y resolver la sesión sobre
   esos objetos; `ProviderWork` queda solo para persistencia. Sin round-trip lossy.
2. **Vía reanudación/reprocesado (sin HTTP, ADR-0033):** `provider_results.payload_json`
   es la única fuente. Se decodifica al dataclass `ProviderWork` (inverso de
   `provider_work_to_dict`) y el adaptador reconstruye `CandidateRepresentation` con la
   tabla siguiente (subconjunto **documentado** y pérdida conocida).

**Mapeo JSON/ProviderWork → dominio (vía reanudación):**

| Campo dominio | Origen | Conserva | Puede faltar |
|---|---|---|---|
| `WorkDescriptor.work_id` | `identity.id` | sí (siempre) | — |
| `title` | `identity.title` | sí | — |
| `composer` | `identity.composer` | sí (atribución de fuente, cruda) | sí → `None` (desconocido) |
| `catalogue_number`, `opus`, `key` | `identity.catalogue` / `metadata.opus` / `metadata.musical_key` | si existen | sí |
| `genres`, `voices`, `instrumentation` | `metadata.genres` / instruments | si existen | sí |
| `format`, `license`, `public_domain` | `resource.format/license` + `metadata.public_domain` | si existen | format → `PDF` por defecto |
| `downloadable`, `download_url`, `view_url`, `remote_id` | `resource.links` + `resource.id` | si existen | no → no-descargable |
| `confidence` | `identity.confidence` | sí | 0.0 (no inventar) |
| `quality`, `completeness`, `checksum`, `edition` | — | **no** | por defecto / `None` (no inventar) |

Reglas del adaptador:
- Nunca decide identidad ni estado; **solo reconstruye**.
- `composer=None` se conserva como desconocido (nunca Anonymous/Traditional, ADR-0034).
- Si una `ProviderWork` no trae recursos, se emite una representación con
  `downloadable=False` para conservar la evidencia de que "el proveedor la anunció".
- La clave `identity.id` es inestable entre proveedores: el `candidate_id` de dominio debe
  ser `{provider}:{identity.id}`, y la identidad de obra **canónica** la decide la pipeline
  (WorkGrouper), nunca el adaptador.

---

## 4. Salida: de V2.1 a `resolution_items` (y a la API)

El esquema de `resolution_items` **no cambia** (columnas actuales: `id, session_id,
ref_json, status, resolution_stage, revision, normalized_json, resolved_json, confidence,
candidates_json, evidence_json`). Se conserva para que la API y los `resolution_items`
persistentes no cambien de contrato.

| Columna | Origen V2.1 |
|---|---|
| `id` | fingerprint estable de la clave canónica de la obra (mismo formato `itm_…`) |
| `ref` / `normalized` / `resolved` | `MergedWorkDescriptor` + `WorkDescriptor` canónico (mismo shape que hoy) |
| `status` | `ResolutionDecisionPolicy` (§5) |
| `resolution_stage` | `provisional` \| `definitive` (mecánica de sesión, sin cambios) |
| `revision` | `replace_items` ya sube revision solo si el contenido difiere (idempotencia) |
| `confidence` | score ponderado del `RankingScore` / `MergeResult` |
| `candidates` | `WorkGroup.representations` serializadas (orden canónico determinista) |
| `evidence` | `EvidenceItem` de `DefaultEvidenceCollector` + razones de la decisión |
| `composer_evidence` (procedencia) | se serializa **dentro de** `evidence`/`normalized` con campos `source/field/raw` (no es columna nueva) |

**Determinismo de serialización (crítico para la revisión):** `replace_items` compara por
igualdad exacta de JSON (`_item_same`). El serializador debe ordenar de forma canónica
`candidates` (por `provider, candidate_id`) y `evidence` (por `source, code, fields`) para
que un re-resolver sobre el mismo universo no incremente `revision` sin motivo.

**API V3.1 sin cambios:** `GET /sessions/{id}` y `/results` consumen `resolution_items` +
`resolution_sessions` tal como hoy.

---

## 5. Decisiones de estado (`resolved | ambiguous | not_found`) y ADR-0034

Hoy `work_ranker.decide()` aplica una heurística sobre dicts (compositor presente,
`matching_providers >= min_providers`, margen sobre el 2º). Esa responsabilidad **no** la
absorbe ninguno de los componentes V2.1 existentes (matcher/ranker/merge deciden piezas,
no el estado global de un grupo). El puente introduce una pieza pura de aplicación:

```
ResolutionDecisionPolicy (application, puro, sin infraestructura)
  entradas: RankingScore (por grupo) + MergeResult + atribución del grupo
  reglas ADR-0034:
    - composer=None          → nunca "Anonymous/Traditional"; obra identificada sin
                               atribución → ambiguous (no resolved, no not_found).
    - resolved               → identidad estable (match ≥ umbral) + sin conflicto
                               material de identidad + atribución presente + evidencia
                               con ≥ min_matching_providers y margen suficiente.
    - ambigüedad real        → ≥2 identidades/candidatos dominantes distintos → ambiguous.
    - not_found              → solo cuando el grupo no tiene candidatos (conserva la
                               semántica actual de decide()).
  config: min_matching_providers, margen mínimo (parámetros equivalentes a los de decide()).
```

Requisito de paridad: sobre el corpus de las 250 obras reales usado en la prueba del
ADR-0033, el nuevo policy debe producir los mismos `status` que `decide()` (o divergencia
justificada y documentada). Se añadirá un test de paridad que compare ambos sobre los
universos fijos de `test_resolution_*`.

Reglas ADR-0034 que el puente debe verificar explícitamente en tests:
- `composer=None` → desconocido; nunca se infiere anónimo/tradicional.
- `composer_explicit ≠ resolved`: tener compositor es evidencia, no prueba de identidad.
- `resolved` requiere identidad estable + sin ambigüedad material (no solo compositor).
- La procedencia de la atribución (source/field/raw) se conserva en la evidencia.

---

## 6. Punto de sustitución en `infrastructure/resolution`

| Pieza actual | Destino |
|---|---|
| `rebuild_universe()` | **Se queda** como lector de `provider_results`, pero devolviendo `ProviderWork` tipados (decodificando el JSON con el inverso de `provider_work_to_dict`) en vez de `list[{provider, work: dict}]`. |
| `SimpleUniverseMatcher` (agrupación + normalización + status) | **Desaparece.** Su responsabilidad pasa a: adaptador → `WorkGrouper` (agrupar) → `DefaultWorkRanker` → `DefaultMergeService` → `ResolutionDecisionPolicy`. |
| `work_ranker.decide()` / `rank()` | **Desaparecen** (sustituidos por el policy puro sobre salidas de dominio). |
| `IUniverseMatcher` + `AcquisitionService._matcher` | Se reemplaza por un `IUniverseResolver` (infra) que compone la pipeline y devuelve los `resolution_items`; `AcquisitionService` conserva su rol de **adquirir/persistir** y llama al resolver para provisional/definitivo. |
| `candidates`/`evidence` actuales por ítem | Mismo shape de persistencia/API, generado ahora desde objetos de dominio. |

`AcquisitionService` **no se convierte en matcher**: sigue siendo la máquina de
adquisición/persistencia. El matcher/resolver es un componente aparte que recibe el
universo tipado y produce items.

---

## 7. Riesgos y decisiones abiertas

1. **Calidad/completitud inexistentes en ProviderWork** (§2): la vía de reanudación
   rankeará con `QualityLevel.UNREADABLE`/`completeness` por defecto salvo que se amplíe el
   contrato o se poble con validación posterior. Aceptar como limitación documentada o
   extender `ProviderWork` en v1.3+.
2. **Dos algoritmos de agrupación coexisten** (`WorkGrouper`/`WorkGroupingMatcher` canónico
   vs el agrupador por clave del agregador V1). Este puente usa el canónico; la búsqueda
   web (F4) debe converger al mismo para eliminar la duplicidad de `WorkGroup`.
3. **Preferencias de usuario ausentes en sesiones**: `RankingContext` usará
   `UserPreferences()` por defecto; si el producto quiere preferencias en sesiones, el API
   deberá propagarlas.
4. **`quality`/`completeness`/atribución sin pérdida en vía viva**: requiere extender
   `AcquiredPage` con `candidates` (§3). La persistencia JSON seguirá siendo el contrato de
   reanudación (pérdida conocida).
5. **Estabilidad de `revision`**: depende del serializador determinista (§4); test
   específico de "re-resolver mismo universo → sin bump de revisión".
6. **Paridad de decisión** con `decide()` sobre el corpus de 250 obras (test de oro).

## 8. Pasos de implementación (posterior a este diseño, aún no iniciados)

1. `AcquiredPage.candidates` + acquirers sin round-trip lossy. ✅ **hecho (2026-09-09)**
2. `domain_adapter.py` (+ inverso de serialización `ProviderWork`) con tests de pérdida.
   ✅ **hecho (2026-09-09)**
3. `ResolutionDecisionPolicy` puro + test de paridad con `decide()` y reglas ADR-0034.
   ✅ **hecho (2026-09-09)** — `application/resolution_decision.py` + `test_resolution_decision_policy`
   (paridad sintética exhaustiva y paridad sobre `script/works250.results.json`: 0 discrepancias;
   `decide()` se conserva como referencia).
4. `IUniverseResolver` + serializador determinista de items; integración en
   `AcquisitionService` (provisional/definitivo).
   ✅ **parcial (2026-09-09)** — `application/universe_resolution.py`
   (`IUniverseResolver`/`V21UniverseResolver`) y
   `infrastructure/resolution/resolution_serializer.py` (canonical JSON, id de ítem
   estable). Tests en `test_universe_resolution.py`. La integración en `AcquisitionService`
   queda para F3.5. ⏳ integración pendiente
5. Eliminación de `SimpleUniverseMatcher`/`work_ranker.decide` y sus tests, sustituidos por
   los anteriores.
   ✅ **hecho en el flujo real (2026-09-09)** — `platform.py` construye sus sesiones con
   `SessionUniverseResolver` (V2.1 + `ResolutionDecisionPolicy` + serialización canónica);
   `AcquisitionService.recompute_items` (provisional/definitivo) ya pasa por el nuevo
   camino. `SimpleUniverseMatcher`/`decide()` **se conservan como referencia de paridad**
   (`test_resolution_*`, `test_work_ranker`) hasta su retirada en F4. Integración en
   `tests/osap/test_session_resolution_v21.py` (provisional/definitivo, paridad de estados,
   estabilidad de revisión).

---

*Ver también: ADR-0033 (sesiones), ADR-0034 (niveles resolved/resolved_auth), ADR-0035
(D1: V2.1 canónica), `docs/osap/v2/osap-architecture-book.md` §5.*
