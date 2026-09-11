# Code Audit — OSAP Core (`osap-api`)

**Scope:** `src/osap/` (domain, ports, application, infrastructure, bootstrap, api, cli)
**Date:** 2026-09-09
**Method:** Static analysis (file reads, AST inspection, grep). No code was modified.
**Basis of comparison:** `docs/osap/v2/osap-architecture-book.md`, `docs/osap/v2/architecture-audit.md`, and ADRs 0020–0033.

---

## 1. Executive Summary

The core domain layer (`domain/`) is largely healthy: immutable value objects, frozen dataclasses, typed enums, and a small set of violations. However, the **transitional V2.x → V3 rewrite left a split identity**: two competing `RankingConfig` classes, two competing `WorkGroup` classes, and a V2.1 ranking/merge pipeline that exists in code but is **never wired** into the running application. The active code path uses the V1-style `DefaultRankingEngine` operating on flat `CandidateRepresentation` lists, while the newer `WorkGroup`-based pipeline (`DefaultWorkRanker`, `DefaultMergeService`) is entirely dead code.

Several violations of the project's own architectural rules are present:

- The **determinism** principle (architecture book §3) is violated by `abs(hash())` for work IDs.
- The **layered dependency** rule (domain never depends on application) is violated in `domain/ranking.py`.
- The **"no `src.` absolute imports"** convention is violated in `domain/`.

---

## 2. Critical: Dual `RankingConfig` — One Shadowed

### What documentation says
`docs/osap/v2/osap-architecture-book.md` §5: "el dominio no depende de nadie." The architecture book references a single `RankingConfig` as a domain value object.

### What the code does
**Two different classes share the name `RankingConfig`:**

| File | Version | Fields | Used by |
|------|---------|--------|---------|
| `domain/ranking.py:87` | V2.0 | `enabled_criteria`, `weights`, `sorting_policy` | `ranker.py` (dead), `__init__.py` exports it *implicitly* |
| `domain/ranking_config.py:7` | V1 (legacy) | `format_order`, `public_domain_weight`, `quality_weight`, `composer_exact_weight`, `title_exact_weight`, `confidence_weight`, `local_availability_weight`, `provider_order`, `language_boost` | `container.py`, `DefaultRankingEngine`, `IRankingEngine` |

**The shadowing happens in `domain/__init__.py`:**

- Line 77–85: imports `RankingContext, RankingCriterion, RankingReason, RankingResult, RankingScore, SortingPolicy, UserPreferences` from `.ranking` — **but NOT `RankingConfig`**.
- Line 86: `from .ranking_config import RankingConfig` — imports the V1 version.

Result: `from src.osap.domain import RankingConfig` silently gives you the V1 config, not the V2.0 one. The `__all__` at line 230 also lists `"RankingConfig"`.

### Impact
- The V2.0 ranking pipeline (`DefaultWorkRanker` using `RankingCriterion` weights) is **completely dead code**.
- `container.py:14` and `wiring.py:366` import the V1 `RankingConfig` and wire `DefaultRankingEngine` (which uses the V1 weights approach).
- A developer adding a new `RankingCriterion` to `domain/ranking.py` will assume it flows through to ranking — it does not, because the wired engine never reads it.

---

## 3. Critical: Two Competing `WorkGroup` Definitions

### What documentation says
`docs/osap/v2/architecture-audit.md` §1 (line 180) lists `work_merge_service` as "✅ se queda". The architecture book §5 shows `WorkMatcher → WorkGrouping → WorkGroup → Ranking → Evidence`.

### What the code does
**Two completely different classes named `WorkGroup`:**

#### `WorkGroup` v1 (active) — `application/work_grouper.py:129`
```python
class WorkGroup:
    __slots__ = ("key", "work", "representations", "primary", "canonical_score")
    def __init__(self, key, work, representations): ...
```
- Has `key`, `primary`, `canonical_score`, `providers` (sort key)
- Used by: `work_merge_service.py` (re-exported), `resource_resolver.py`, `app.py` (TYPE_CHECKING), `cli/main.py`

#### `WorkGroup` v2 (frozen) — `application/execution_plan.py:42`
```python
@dataclass(frozen=True)
class WorkGroup:
    work: WorkDescriptor
    representations: tuple[CandidateRepresentation, ...] = ()
    providers: tuple[ProviderId, ...] = ()
```
- No `key`, `primary`, `canonical_score`
- Used by: `merge_service.py`, `ranker.py`, `provider_result_aggregator.py`, `domain/ranking.py` (TYPE_CHECKING)

### The Dead Pipeline
The V2.x pipeline (`DefaultWorkRanker`, `IMergeService`, `DefaultMergeService`) is never instantiated:

- `DefaultWorkRanker` (ranker.py:23) implements `IWorkRanker` using the frozen `WorkGroup` from `execution_plan.py`.
- `container.py` and `wiring.py` never import or register `DefaultWorkRanker`.
- `container.py:365` wires `DefaultRankingEngine` (infrastructure), which implements `IRankingEngine` (not `IWorkRanker`), operating on flat `CandidateRepresentation` tuples — a completely different abstraction.
- `work_resolution_engine.py:96` calls `self._ranking_engine.rank(candidates, request, self._config)` returning `tuple[CandidateRepresentation, ...]`, bypassing `WorkGroup` entirely.

### Impact
- The `DefaultMergeService` (merge_service.py:36) and `IMergeService` port are dead code.
- The `DefaultWorkRanker` and `IWorkRanker` port are dead code.
- Developers may implement against the `IWorkRanker`/`IMergeService` contracts, which will never be called.

---

## 4. Critical: Domain Layer Dependency Violation

### What documentation says
ADR-0003 "domain-is-the-center": "el dominio no conoce a nadie." Architecture book §5: "el dominio no depende de la web, ni de la infraestructura."

### What the code does
**`domain/ranking.py:9`:**
```python
if TYPE_CHECKING:
    from src.osap.application.execution_plan import WorkGroup
```

This is used as a string annotation `"WorkGroup"` in `RankingScore.work` (line 42). While `TYPE_CHECKING` prevents a runtime import cycle, it **violates the architectural boundary**: the domain layer now depends on (references) the application layer.

Additionally, `ports/work_ranker.py:7` and `ports/merge_service.py:7` both import `WorkGroup` from `..application.execution_plan` under `TYPE_CHECKING` — the ports layer (which should be pure interfaces) depends on application code.

### Impact
- The domain layer is no longer self-contained; static analysis tools and type checkers see a dependency where none should exist.
- Circular dependency risk: `application/work_grouper.py` imports from `domain/`; `domain/ranking.py` imports from `application/` (even under `TYPE_CHECKING`, this creates a conceptual cycle).

---

## 5. Critical: Non-Deterministic Work IDs (Violates Core Principle)

### What documentation says
Architecture book §3, principle 3: **"Determinismo: mismas entradas → mismas salidas. Sin aleatoriedad."**

### What the code does
Two places generate `WorkId` using Python's `hash()`:

**`application/work_resolver.py:18`:**
```python
work_id=WorkId(f"work-{abs(hash(title))}")
```

**`application/work_grouper.py:118`:**
```python
work_id=WorkId(f"work-{abs(hash(signature))}")
```

Python's `hash()` for `str` is **randomized per interpreter process** (controlled by `PYTHONHASHSEED`, default `random`). This means:

- Restarting the server produces **different `WorkId` values** for the same work.
- Cached results, database keys, and downstream references break across restarts.
- The "determinismo" principle is directly violated.

### Fix direction: use `hashlib` (SHA-256 or MD5) instead. Note that `work_resolution_engine.py:1` already imports `hashlib` and uses `hashlib.sha256` at line 145 — the pattern exists in the codebase.

---

## 6. High: Inconsistent Import Style in Domain Layer

### What documentation says
Implicit codebase convention: domain modules use **relative imports** (e.g., `from .value_objects import ...`). ADR-0027 "domain-closure": domain layer should be "closed" and pure.

### What the code does
Most domain files use relative imports, but **two files use absolute `src.osap.domain.*` imports**:

**`domain/ranking.py:5-6`** (lines 5-6):
```python
from src.osap.domain.output_format import OutputFormat
from src.osap.domain.work_descriptor import WorkDescriptor
```

**`domain/resolve_result.py:3-7`** (lines 3-7):
```python
from src.osap.domain.candidate_representation import CandidateRepresentation
from src.osap.domain.evidence import Evidence
from src.osap.domain.resolve_request import ResolveRequest
from src.osap.domain.value_objects import Duration, ProviderId
from src.osap.domain.work_descriptor import WorkDescriptor
```

All other domain files (e.g., `candidate_representation.py`, `catalog_capabilities.py`, `edition.py`) use `from .module import ...`.

### Impact
- Style inconsistency across the domain layer.
- The `src.osap` absolute path means the domain layer is **tied to the repository root layout** rather than being relocatable — contradicts the "closed domain" goal.

---

## 7. High: `_MysqlStore` Missing `super().__init__()`

### What the code does
`infrastructure/state/op_store.py:238-243`:

```python
class _MysqlStore(_MemoryStore):
    def __init__(self, host, user, password, database) -> None:
        self._params = {...}
        self._init()
```

`_MemoryStore.__init__` (line 30-35) initializes `_suggestions`, `_corrections`, `_work_selections`, `_providers`, `_config`. `_MysqlStore.__init__` **never calls `super().__init__()`**, so these attributes are not set on `_MysqlStore` instances.

Additionally, `build_op_store()` (line 693-708) calls `store._init()` and `store._migrate()` **again** after `__init__` already called `_init()` and `_migrate()`:

```python
store = _MysqlStore(**params)       # __init__ calls _init() and _migrate()
store._init()                      # redundant
store._migrate()                   # redundant
```

### Impact
- `_MysqlStore` currently overrides every method that accesses the parent's data structures, so it doesn't crash at runtime. But:
- Any future method added to `_MemoryStore` that `_MysqlStore` doesn't override will raise `AttributeError` (the parent's lists/dicts were never initialized).
- The redundant `_init()`/`_migrate()` call in `build_op_store` is wasted work (DDL `CREATE TABLE IF NOT EXISTS` re-execution).
- The return type annotation `_MemoryStore` (line 698) is technically correct (subtype) but misleading.

---

## 8. High: Bare `except Exception` in Wiring

### What the code does
`bootstrap/wiring.py` uses bare `except Exception:` (with `# noqa: BLE001` suppressions) in three places:

| Line | Function | What it swallows |
|------|----------|-----------------|
| 126–128 | `_provider_definition` | Any error loading provider from DB or YAML — silently falls back |
| 180–181 | `_db_provider_metadata` | Any connection/auth/schema error — returns `[]` |
| 303–310 | CPDL wiring check | Any error listing providers — sets `cpdl_wired = False` |

### Impact
- Database connection failures, auth errors, schema corruption, and `KeyboardInterrupt` are all silently swallowed.
- The application starts in a degraded state with **no logging** of the root cause.
- A misconfigured `OSAP_STORAGE_BASE_URL` or a down MySQL server is indistinguishable from "no providers configured."

---

## 9. High: Two Active API Entry Points (`app.py` and `platform_app.py`)

### What documentation says
ADR-0029 mentions V3.1 API contract. Architecture book §6 mentions V3 API (FastAPI).

### What the code does
Two parallel API modules exist:

| File | Lines | Entry point | Status |
|------|-------|-------------|--------|
| `api/app.py` | 302 | `create_app()` | V1/V2 legacy |
| `api/platform_app.py` | 2,580 | `create_platform_app()` | V3.1 "Platform API" |

Both define FastAPI applications with overlapping endpoints (`/api/v1/health`, `/api/v1/providers`, `/api/v1/search`, `/api/v1/resolve`, etc.). The `platform_app.py` file is massive (2,580 lines) and duplicates much of `app.py`'s functionality.

### Impact
- Confusion about which API is authoritative.
- Maintenance burden: two implementations of overlapping endpoints.
- The `AGENTS.md` instructions reference `platform_app.py` for the V3.1 API, but `app.py` is still the one exported from `api/__init__.py`.

---

## 10. Medium: Oversized Modules

### What documentation says
ADR-0014 "platform-architecture" and the architecture book §5 suggest hexagonal architecture with small, focused modules.

### What the code does
Top 10 modules by line count:

| Lines | File | Description | Concerns |
|-------|------|-------------|----------|
| 2,580 | `api/platform_app.py` | FastAPI HTTP routes + inline orchestration | Routing, DTO mapping, orchestration all mixed |
| 2,570 | `api/platform.py` | Use cases + API logic | 50+ use cases in one file |
| 842 | `api/contracts.py` | DTO definitions | Single file with all contract types |
| 708 | `infrastructure/state/op_store.py` | `_MemoryStore` + `_MysqlStore` + migrations | Two stores + schema management + factory |
| 679 | `cli/main.py` | CLI | Resolution, provider mgmt, jobs, votes, knowledge |
| 603 | `infrastructure/providers/adapters/generic_provider_adapter.py` | HTTP client + YAML loading + mapping | `ProviderHttpClient`, `ProviderDefinition`, mapping logic |
| 533 | `infrastructure/state/resolution_store.py` | Resolution store | Single file for persistence logic |
| 499 | `application/lexicon.py` | Lexicon | Hardcoded data tables + logic |
| 442 | `bootstrap/wiring.py` | DI wiring | All provider registration + config |
| 416 | `application/metadata_normalizer.py` | Normalizer | Hardcoded normalization tables |

### Impact
- `platform.py` and `platform_app.py` are the most severe: a single module with 2,500+ lines handling 50+ endpoints violates the Single Responsibility Principle.
- Hard to test: tests for one endpoint may need to import the entire module.
- Hard to review: a PR touching any endpoint in these files is enormous.

---

## 11. Medium: SOLID Violations

### SRP (Single Responsibility Principle)

**`api/platform.py` (2,570 lines):** A single module serves as the application service layer for the entire REST API. It handles provider discovery, work resolution, work selection, composer resolution, votes, statistics, knowledge review, corrections, source suggestions, jobs, and exports — all in one file.

**`infrastructure/providers/adapters/generic_provider_adapter.py` (603 lines):** `ProviderHttpClient` (HTTP), `ProviderDefinition` (config dataclass), `ProviderQuery` (query DTO), and mapping logic are all in one module. The `GenericProviderAdapter` class (the 511-line class spanning ~lines 100–603) handles: HTTP invocation, YAML loading, field mapping, resource extraction, authentication, and response formatting.

**`infrastructure/state/op_store.py` (708 lines):** `_MemoryStore` and `_MysqlStore` (20+ methods each, duplicated), schema migration (`_init`, `_migrate`), and factory (`build_op_store`) all in one file.

### OCP (Open/Closed Principle)

**`application/lexicon.py:14`** — `_GENRE_MAP` is a hardcoded `dict[str, str]`. Adding a genre mapping requires editing source code:
```python
_GENRE_MAP: dict[str, str] = {"mass": "Mass", "missa": "Mass", ...}
```
Should be loaded from a YAML data file (the `lexicon/*.yaml` directory exists for exactly this purpose, per architecture book §7).

**`application/metadata_normalizer.py`** — Contains large hardcoded normalization tables (genre maps, voice patterns, instrumentation aliases) that should be data-driven.

### DIP (Dependency Inversion Principle)

**`application/work_resolution_engine.py:51-60`** — `WorkResolutionEngine.__init__` accepts concrete types instead of port interfaces:
```python
orchestrator: ProviderOrchestrator | None = None    # should be an interface
evidence_engine: EvidenceEngine | None = None        # should be an interface
```

**`application/composer_resolution_engine.py:102-108`** — Takes `resolvers: list[IComposerResolver]` (interface — OK) but `work_matcher: WorkMatcher | None` where `WorkMatcher` is a `Callable` (line 30: `WorkMatcher = Callable[[ResolverQuery], list[WorkMatchPair]]`), not a port interface.

### ISP (Interface Segregation Principle)

**`ports/ranking_engine.py`** — `IRankingEngine` forces all implementations to provide both `rank()` and `rank_detailed()`. Clients that only need simple ranking are forced to implement the detailed variant.

**`ports/knowledge_miner.py`** — `IKnowledgeMiner` has a single `mine()` method (acceptable), but `IKnowledgeCollector` has `collect()` — the split is arbitrary and neither is wired.

---

## 12. Medium: Untyped `except Exception` Also in Infrastructure

**`infrastructure/providers/adapters/generic_provider_adapter.py:87`:**
```python
except Exception:
    return None
```
Swallows all errors from `urllib.request.urlopen` — including connection errors, timeouts, and SSL errors — returning `None` silently. No logging, no retry, no diagnostic.

---

## 13. Low: `KnowledgeMiner` / `KnowledgeCollector` Not Wired

### What documentation says
ADR-0027 §2: "Knowledge Mining nunca modifica el sistema; solo propone; siempre decide un humano." Architecture book §6: V2.2.d (Knowledge Mining) should be complete.

### What the code does
`DefaultKnowledgeMiner` (in `application/knowledge_miner.py`) and `DefaultKnowledgeCollector` (in `application/knowledge_collector.py`) exist as implementations of their respective ports, but:

- `container.py` has no method to provide a `KnowledgeMiner` or `KnowledgeCollector`.
- `wiring.py` never registers either.
- Neither is imported outside its own module.

### Impact
- V2.2.d's Knowledge Mining feature is **implemented but unreachable**.
- Tests may exist for these classes, but the feature cannot be exercised end-to-end.

---

## 14. Low: Pipeline Documentation Mismatch

### What documentation says
Architecture book §5 (pipeline):
```
Query → Tokenizer → Lexicon → Canonicalizer → WorkMatcher → WorkGrouping → Ranking → Merge → Selection → Evidence
```

ADR-0022 §Principios (line 38):
```
Tokenizer → Lexicon → Canonicalizer → WorkMatcher → WorkGroup → Ranking → Evidence
```

### What the code does
`WorkResolutionEngine.resolve()` (line 76-182):
1. `self._work_resolver.resolve(request)` — resolve work identity (simple)
2. `self._collect(request)` → `ProviderOrchestrator.search()` — fetch from providers
3. `self._ranking_engine.rank(candidates, request, self._config)` — rank flat candidates (V1 `DefaultRankingEngine`)
4. `self._pick(ranking, index)` — select top
5. `self._ranking_engine.rank_detailed(ranking, ...)` + `self._evidence_engine.explain(...)` — evidence

**Missing from the active pipeline:** Canonicalizer, WorkMatcher, WorkGrouping, Merge. These exist as dead code (`DefaultWorkRanker`, `DefaultMergeService`, `WorkGrouper` is used for grouping in CLI only).

### Impact
- The documented pipeline and the actual pipeline are different. New developers will implement against the documented architecture and find their code unused.

---

## 15. Low: `_GENRE_MAP` in `canonical_metadata.py` is Duplicated

`application/canonical_metadata.py:14-36` defines `_GENRE_MAP` — the same genre mapping table. `application/lexicon.py` also contains genre mapping data. Two separate mappings for the same concept exist in two modules, with no shared source of truth.

---

## Summary Table

| # | Severity | Issue | Location |
|---|----------|-------|----------|
| 1 | Critical | Dual `RankingConfig` — V2.0 shadowed by V1 in `__init__.py` | `domain/__init__.py:77-86`, `domain/ranking.py:87`, `domain/ranking_config.py:7` |
| 2 | Critical | Two competing `WorkGroup` classes — V2.x pipeline is dead code | `application/work_grouper.py:129`, `application/execution_plan.py:42`, `application/ranker.py:23`, `application/merge_service.py:36` |
| 3 | Critical | Domain layer imports from application (`WorkGroup`) | `domain/ranking.py:9`, `ports/work_ranker.py:7`, `ports/merge_service.py:7` |
| 4 | Critical | Non-deterministic `WorkId` via `abs(hash())` — violates determinism | `application/work_resolver.py:18`, `application/work_grouper.py:118` |
| 5 | High | Absolute imports in domain (`src.osap.domain.*`) instead of relative | `domain/ranking.py:5-6`, `domain/resolve_result.py:3-7` |
| 6 | High | `_MysqlStore` missing `super().__init__()` + redundant `_init`/`_migrate` | `infrastructure/state/op_store.py:238-243`, `build_op_store:693-708` |
| 7 | High | Bare `except Exception` in wiring (3 sites) | `bootstrap/wiring.py:126, 180, 303` |
| 8 | High | Two active API entry points: `app.py` (302 lines) + `platform_app.py` (2,580 lines) | `api/app.py`, `api/platform_app.py` |
| 9 | Medium | Oversized modules (4 files >500 lines) | `api/platform.py:2570`, `api/platform_app.py:2580`, `op_store.py:708`, `generic_provider_adapter.py:603` |
| 10 | Medium | SRP violation: `platform.py` handles 50+ use cases in one file | `api/platform.py` |
| 11 | Medium | OCP violation: hardcoded `_GENRE_MAP` dict | `application/lexicon.py:14`, `application/canonical_metadata.py:14` |
| 12 | Medium | DIP violation: `WorkResolutionEngine` takes concrete types | `application/work_resolution_engine.py:51-60` |
| 13 | Medium | ISP violation: `IRankingEngine` forces `rank_detailed` | `ports/ranking_engine.py` |
| 14 | Low | `KnowledgeMiner` / `KnowledgeCollector` not wired | `application/knowledge_miner.py`, `application/knowledge_collector.py`, `container.py` |
| 15 | Low | Pipeline doc doesn't match implementation | Architecture book §5 vs `WorkResolutionEngine.resolve()` |
| 16 | Low | Bare `except Exception` in provider HTTP client | `generic_provider_adapter.py:87` |
| 17 | Low | Duplicated `_GENRE_MAP` across modules | `lexicon.py`, `canonical_metadata.py` |

---

## Recommendations (for future work)

1. **Unify `RankingConfig`**: Delete `domain/ranking_config.py` or merge into `domain/ranking.py`. Ensure `domain/__init__.py` imports `RankingConfig` from one source only.
2. **Unify `WorkGroup`**: Choose one definition (the frozen dataclass in `execution_plan.py` is the cleaner one). Remove the `__slots__`-based `WorkGroup` from `work_grouper.py`, or fully wire the V2.x pipeline.
3. **Remove dead code**: Delete `ranker.py` (`DefaultWorkRanker`), `ports/work_ranker.py` (`IWorkRanker`), `merge_service.py` (`DefaultMergeService`), `ports/merge_service.py` (`IMergeService`) — or wire them if the V2.1 pipeline is intended.
4. **Fix determinism**: Replace `abs(hash(...))` with `hashlib.sha256(...).hexdigest()[:12]` (pattern already used at `work_resolution_engine.py:145`).
5. **Fix domain imports**: Change `domain/ranking.py` and `domain/resolve_result.py` to use relative imports. Remove the `TYPE_CHECKING` import of `WorkGroup` from `domain/ranking.py` — use `TYPE_CHECKING` or restructure to avoid the dependency.
6. **Fix `_MysqlStore`**: Call `super().__init__()` before setting `_params`, or restructure to use composition instead of inheritance.
7. **Replace bare `except Exception`**: Catch specific exceptions (`pymysql.err.OperationalError`, `KeyError`, `TypeError`) and log at appropriate levels.
8. **Split `platform.py`**: Extract use-case groups into separate modules (e.g., `platform/works.py`, `platform/composers.py`, `platform/providers.py`, `platform/jobs.py`).
9. **Consolidate API entry points**: Determine whether `app.py` or `platform_app.py` is authoritative for V3.1 and remove the other.
10. **Wire Knowledge Mining**: Register `DefaultKnowledgeMiner` and `DefaultKnowledgeCollector` in `container.py`/`wiring.py`, or remove if not yet needed.

---

# Anexo A — Verificación de las afirmaciones (2026-09-09)

Verificación contra el código real (lectura de fuentes, AST y greps). Cada hallazgo del
cuerpo del documento se marca **V** (cierto), **P** (parcial/necesita matiz) o **F** (falso).

| # | Veredicto | Corrección / matiz |
|---|-----------|--------------------|
| 1 | P | Hay **dos clases homónimas `RankingConfig`**: V1 (`domain/ranking_config.py`, usada por el camino activo: `IRankingEngine`, `DefaultRankingEngine`, `container`) y V2.0 (`domain/ranking.py`, usada solo por la pipeline V2.1 no cableada). Pero **no hay shadowing en `domain/__init__.py`**: ese `__init__` solo importa la V1 (`ranking_config`); la V2.0 se importa únicamente por ruta de módulo (`src.osap.domain.ranking`) en `ranker.py` y tests. El problema real es **ambigüedad de nombres**, no un import eclipsado. |
| 2 | P | Cierta la **duplicidad**: `execution_plan.WorkGroup` (frozen) lo instancia el agregador activo (`provider_result_aggregator.py`) y lo consumiría la pipeline V2.1; `work_grouper.WorkGroup` (`__slots__`) lo usa la agrupación de visualización (CLI/API). **Falso que sea "código muerto sin uso"**: hay tests que ejercitan la pipeline V2.1 completa (`test_search_intelligence_pipeline`, `test_merge_service`, `test_evidence_collector`, `test_knowledge_mining`). Es **pipeline implementado y testeado pero no cableado** en los flujos en producción. |
| 3 | V | `domain/ranking.py:9`, `ports/work_ranker.py:7` y `ports/merge_service.py:7` referencian `application.execution_plan.WorkGroup` (en `TYPE_CHECKING`). Cierta la violación de dependencia (el tipo correcto debería vivir en `domain/`). |
| 4 | V | Cierta, e **infracontada**: hay **4 sitios** `abs(hash(...))`: `application/work_resolver.py:18`, `application/work_grouper.py:118`, `application/work_grouping_matcher.py:193` y `api/app.py:103` (job id). El patrón correcto (`hashlib.sha256`) ya existe en `work_resolution_engine.py:145`. |
| 5 | V | `domain/ranking.py:5-6` y `domain/resolve_result.py:3-7` usan imports absolutos `src.osap.domain.*`; el resto del dominio usa relativos. |
| 6 | V | `_MysqlStore.__init__` no llama a `super().__init__()`; `build_op_store` repite `_init()` + `_migrate()` que `__init__` ya ejecuta (`_init` además llama a `_migrate` al final). |
| 7 | V | `bootstrap/wiring.py:126, 180, 303-310` con `except Exception` silencioso. Se añade `api/platform.py:726` (este sí loguea con `logger.exception`; más aceptable). |
| 8 | P | `app.py` (`create_app`) es legacy pero **sigue viva**: exportada en `api/__init__.py` y cubierta por `tests/osap/test_api.py`. `platform_app.py` (`create_platform_app`, V3.1) es la de producción según AGENTS.md. Solapamiento real; no se puede borrar `app.py` sin migrar sus tests. |
| 9 | V | Líneas medidas: `platform_app.py` 2 580, `platform.py` 2 570, `contracts.py` 842, `op_store.py` 708, `cli/main.py` 679, `generic_provider_adapter.py` 603, `resolution_store.py` 533, `lexicon.py` 499, `wiring.py` 442, `metadata_normalizer.py` 416. |
| 10 | V | `api/platform.py` concentra use-cases de todos los dominios (objetivo; 50+ endpoints). |
| 11 | F (parcial) | `_GENRE_MAP` **no está en `lexicon.py`**: solo existe en `application/canonical_metadata.py:14`. En `lexicon.py` sí hay tablas hardcodeadas (`_STOPWORDS`, `_PROPER_NAMES`, `_PROVIDER_WORDS`, `_CATALOGUE_PREFIXES`), pero son datos distintos. La afirmación OCP es válida en general (data-in-code), con la localización corregida. |
| 12 | V | `WorkResolutionEngine` recibe concretos (`ProviderOrchestrator`, `EvidenceEngine`); no existen puertos para ellos. |
| 13 | V (menor) | `IRankingEngine` obliga a implementar `rank` + `rank_detailed`. |
| 14 | P | No cableados en `container`/`wiring`, cierto. Matiz: tienen **tests** (`test_knowledge_mining.py`) y, según ADR-0027, la aplicación humana de sugerencias está prevista para V3.3 — puede ser **omisión intencional**, no defecto. |
| 15 | P | La pipeline V2.1 (Canonicalizer → Matcher → WorkGrouper → Ranker → Merge → Knowledge) existe, está testeada como subsistema aislado y coincide con la documentación; lo que no coincide es el **flujo activo** (`WorkResolutionEngine`), que usa `DefaultRankingEngine` (V1) sobre candidatos planos y `work_grouper` solo para agrupar en pantalla. |
| 16 | V | `generic_provider_adapter.py:87` traga cualquier error HTTP silenciosamente (`return None`). |
| 17 | F | `_GENRE_MAP` tiene **una sola** definición (`canonical_metadata.py:14`). No hay duplicación. |

**Añadido detectado en la verificación:** existe una **tercera vía de resolución** en
`infrastructure/resolution/` (`work_ranker.py` con `decide()`, `provider_acquirer.py`,
`universe_matching.py`, `acquisition_service.py`) usada por `PlatformApi` (`platform.py`)
para las sesiones de resolución (`resolve_session`, ADR-0033/0034), que trabaja con dicts
JSON en vez de los objetos de dominio/application. Conviven, por tanto, **tres flujos de
decisión**: V1 (`WorkResolutionEngine`+`DefaultRankingEngine`), V2.1 (no cableada) y V3
(`AcquisitionService`+`decide()`).

---

# Anexo B — Plan de remediación

## Decisiones tomadas (2026-09-09)

| Decisión | Resolución | Consecuencia |
|----------|-----------|--------------|
| **D1 — Pipeline** | **V2.1 como capa canónica de decisión** (dominio puro: Canonicalizer → Matcher → WorkGrouper → Ranker → Merge → Evidence → Knowledge). La vía V3 de sesiones debe **consumir esos componentes de dominio** (sustituir `decide()` y los dicts JSON por objetos de dominio). La vía V1 (`WorkResolutionEngine`+`DefaultRankingEngine`) queda **legacy**: la búsqueda web migrará después, no antes. | La pipeline de dominio deja de ser "no cableada"; la vía de dicts de `infrastructure/resolution/` se reemplaza por una capa de adaptación dominio↔sesión. |
| **D2 — API doble** | **Deprecar `app.py`** (`create_app`). `platform_app.py` (`create_platform_app`, V3.1) es la única entrada de producción. | Marcar deprecación en `api/__init__.py` y docstring; no añadir rutas nuevas a `app.py`; migrar sus tests progresivamente. Nada se rompe hoy. |
| **D3 — Knowledge Mining** | **Dejarlo sin cablear hasta V3.3** (omisión intencional, acorde a ADR-0027). | Conservar `DefaultKnowledgeMiner`/`DefaultKnowledgeCollector` y sus tests; documentar la decisión. Sin observaciones/sugerencias en runtime hasta V3.3. |

## F0 — Registro y documentación
- Crear **ADR-0035** con D1/D2/D3 y el modelo de integración V2.1↔sesiones (justificación de D1: ADR-0022/0027 describen la pipeline de dominio como canónica; las sesiones V3 (ADR-0033/0034) son el vehículo donde integrarla).
- Actualizar `docs/osap/v2/osap-architecture-book.md` §5: reflejar las tres vías actuales y la vía canónica objetivo (evitar que la doc se considere fuente de la pipeline mientras no se ha cableado — ver hallazgo 15).
- Nota en `platform.py`/`KnowledgeStore` sobre D3 (intencional hasta V3.3).

## F1 — Correcciones de bajo riesgo (independientes de D1–D3)
1. **Determinismo de IDs (#4).** Helper estable (`hashlib.sha256(...).hexdigest()[:16]`) y sustitución en los **4 sitios** (`work_resolver.py:18`, `work_grouper.py:118`, `work_grouping_matcher.py:193`, `api/app.py:103`). Revisar tests que fijen literales `"work-"`/`"job-"`.
2. **Dominio autocontenido (#3, #5).**
   - Crear `domain/work_group.py` con el `WorkGroup` frozen (solo tipos de dominio); re-export desde `application/execution_plan.py` para no romper `AggregatedProviderResult`.
   - `ports/work_ranker.py`, `ports/merge_service.py` y `domain/ranking.py` referencian el tipo desde `domain/`; `provider_result_aggregator.py`, `ranker.py`, `merge_service.py` importan de `domain/`.
   - Imports relativos en `domain/ranking.py` y `domain/resolve_result.py`.
3. **`_MysqlStore` (#6).** Llamar `super().__init__()`; quitar `_init()`/`_migrate()` redundantes en `build_op_store`.
4. **Excepciones (#7, #16).** `wiring.py`: capturar `pymysql.err.OperationalError`, `ValueError`, `KeyError` con `logger.warning`; `generic_provider_adapter.py:87`: loguear antes de devolver `None`.
5. **Ambigüedad `RankingConfig` (#1).** Renombrar la clase de **dominio puro** (`domain/ranking.py`, `enabled_criteria`/`weights`/`sorting_policy`) a **`RankingPolicy`** — es la que usará la pipeline canónica (D1) y tiene menos referencias (`ranker.py` + 3 tests). La V1 (`ranking_config.py`) conserva el nombre `RankingConfig` mientras siga activa en la búsqueda web legacy; se retirará en F4.

Verificación F1: `ruff`, `mypy`, `pytest`; ningún test debe cambiar de semántica.

## F2 — Deprecación de `app.py` (D2)
1. Marcarlo `deprecated` en el docstring y en `api/__init__.py` (p. ej. `warnings.warn(..., DeprecationWarning)`).
2. Inventario de rutas de `app.py` frente a `platform_app.py` (79 decorators): portar a `platform_app` cualquier endpoint único que falte.
3. Migrar `tests/osap/test_api.py` (usa `create_app`) hacia `test_platform_api.py` (que ya existe); dejar `test_api.py` como suite de compatibilidad mientras viva `app.py`.
4. Criterio de retirada: sin consumidores en `src/`, `cli/`, scripts ni docs → borrar `app.py` y su re-export.

## F3 — Integración de la pipeline V2.1 en sesiones (D1; trabajo mayor)
Requisito previo: lectura completa de `docs/osap/adr/0033-*-resolution-sessions`, `0034-*-work-resolution-levels`, `infrastructure/resolution/` (acquisition_plan, provider_acquirer, universe_matching, work_ranker, acquisition_service), `resolution_store.py` y los endpoints de sesión de `platform_app`/`PlatformApi` antes de codificar (el diseño se registra en ADR-0035).

1. **Capa de adaptación sesión↔dominio.** Los acquirers devuelven JSON (`provider_works_to_json`); hay que reconstruir `CandidateRepresentation`/`WorkDescriptor`/`WorkGroup` de dominio a partir de la salida de los proveedores (o cambiar los acquirers para devolver objetos ya mapeados). Este adaptador se reutilizará en la búsqueda web (F4).
2. **Sustituir `decide()`** (`infrastructure/resolution/work_ranker.py`) por la pipeline canónica por grupo del universo:
   - `WorkGroup` (dominio, tras F1.2) → `DefaultWorkRanker.rank(..., RankingPolicy)` → `DefaultMergeService.merge(..., MergePolicy)` → `DefaultEvidenceCollector`/`EvidenceEngine`.
   - Preservar la semántica de `resolved | ambiguous | not_found` y las políticas hoy en `decide()` (min_providers, min_margin) trasladándolas a configuración de dominio (`MatchingConfig`/`RankingPolicy`), con sus umbrales.
3. **Persistencia y evidencia.** Ajustar `resolution_store`/contratos de sesión para guardar la decisión de dominio y sus evidencias (hoy guarda dicts JSON de `decide()`).
4. **Tests.** Mantener la referencia de `test_search_intelligence_pipeline`, `test_merge_service`, `test_evidence_collector`, `test_knowledge_mining`. Actualizar los de sesiones: `test_resolution_universe_matching`, `test_resolution_lifecycle`, `test_resolution_acquisition`, `test_work_ranker`, `test_universe_composer_merge`, `test_platform*.py`. Añadir un test de integración sesión↔dominio.
5. **No tocar la búsqueda web** en esta fase (sigue en V1 legacy).

## F4 — Migración de la búsqueda web y retirada de V1 (post F3)
1. `platform.py:_run_search` (líneas 859–949) y `_focused_representations` (1243): sustituir el par `DefaultRankingEngine` + `work_merge_service.group()` por: grupos de dominio (`AggregatedProviderResult.groups`) → `DefaultWorkRanker` → consolidación `DefaultMergeService` para el DTO de resultados (resolve #2 del todo: un único `WorkGroup` en `domain/`).
2. Migrar consumidores restantes de `WorkResolutionEngine`: `cli/main.py`, `WorkComposerMatcher` (fase obra de compositores) y `app.py` (mientras viva).
3. **Retirada de V1** cuando no queden consumidores: `DefaultRankingEngine`, `domain/ranking_config.py` (`RankingConfig` V1), `domain/score_ranking.py` si queda huérfano, `evidence_engine` V1 si se sustituye por `DefaultEvidenceCollector`.
4. Ese es el momento de alinear la doc del pipeline (architecture book §5) con la realidad.

## F5 — Deuda estructural (P3, independiente y aplazable)
- Dividir `platform.py` (`PlatformApi`) y `platform_app.py` por dominio (works, composers, providers, jobs, knowledge, admin) con routers.
- Dividir `op_store.py`, `contracts.py`, `cli/main.py`, `generic_provider_adapter.py`.
- Mover tablas hardcodeadas (`lexicon.py`, `canonical_metadata.py`) a datos cargados (`lexicon/*.yaml`) — OCP.
- `_GENRE_MAP` no está duplicado (hallazgo 17 corregido): no hay acción.

**Orden recomendado:** F0 → F1 (quick wins, baja fricción) → F2 (deprecación) → F3 (integración, con su propia espiga de diseño) → F4 → F5.

**Verificación en cada fase:** `python -m ruff check src/osap tests/osap`, `python -m mypy src/osap`, `python -m pytest tests/osap -q` (frontend no afectado). Cualquier fase debe empezar y terminar con la suite verde.

---

# Anexo C — Estado de remediación (2026-09-09)

Estado de los 17 hallazgos y de las fases. Leyenda: ✅ cerrado · 🟡 en curso/parcial · ⏳ pendiente · ⏸ decidido-no-ahora.

## Hallazgos de la auditoría (cuerpo del documento)

| # | Hallazgo | Estado | Dónde / siguiente paso |
|---|----------|--------|------------------------|
| 1 | Dos `RankingConfig` homónimos | ✅ (ambiguidad resuelta) | V2.0 renombrada a `RankingPolicy` (F1.5). La V1 `ranking_config.py` se retirará con el flujo V1 en F4. |
| 2 | Dos `WorkGroup` | ✅ | `WorkGroup` canónico movido a `domain/` (F1.2) y **unificado en F4.A**: `WorkGrouper.group` emite ya el `WorkGroup` de dominio (con `key`/`primary` compatibles); eliminado el `__slots__` de `work_grouper.py`. Persiste un solo tipo en `domain/`. |
| 3 | Dependencia domain→application | ✅ | F1.2: `WorkGroup` ahora vive en `domain/`; puertos y `domain/ranking.py` referencian el tipo de dominio. |
| 4 | IDs no deterministas (`abs(hash)`) | ✅ | F1.1: `stable_id()` (SHA-256) en los 4 sitios. |
| 5 | Imports absolutos en domain | ✅ | F1.2/F1.5: relativos en `ranking.py` y `resolve_result.py`. |
| 6 | `_MysqlStore` sin `super().__init__()` + doble init | ✅ | F1.3. |
| 7 | `except Exception` en wiring (3 sitios) | ✅ | F1.4: estrechado + logging (`_DB_ERRORS`). |
| 8 | Dos entradas de API (`app.py` + `platform_app`) | ✅ | F2 deprecó `create_app`; **retirada ejecutada el 2026-09-09** (sin consumidores en runtime): eliminados `src/osap/api/app.py` y `tests/osap/test_api.py`. `platform_app.py` (V3.1) es la única entrada. |
| 9 | Módulos sobredimensionados | 🟡 | F5: ✅ `contracts` (paquete, F5.1), `op_store` (`op/`, F5.2), `generic_provider_adapter` (`generic/`, F5.3), `platform.py` (`api/platform/` mixins, F5.4) y `platform_app.py` (151 líneas + `api/http/` routers/shared, F5.5). Pendiente: `cli/main.py` (F5.6) y `resolution_store.py` (F5.8). |
| 10 | SRP: `platform.py` 50+ use-cases | ✅ | F5.4 (2026-09-10): `PlatformApi` dividido en paquete `api/platform/` con mixins por dominio (106 métodos) + `core` (estado/ayudas) + `_support`; `main.py` solo composición/init. Fachada y contratos intactos. |
| 11 | OCP: tablas hardcodeadas (sitio corregido) | ✅ | F5.7 (2026-09-11): `_GENRE_MAP`/`_VOICE_PATTERNS` y tablas de `lexicon.py` externalizadas a `resources/canonical/*.yaml` con valores idénticos (verificado programáticamente); añadir datos ya no exige tocar código. Último bloque de F5. |
| 12 | DIP: `WorkResolutionEngine` recibe concretos | ⏳ | Queda sin deuda real mientras el flujo V1 siga activo; se disuelve al retirar V1 en F4. |
| 13 | ISP: `IRankingEngine.rank`+`rank_detailed` | ⏳ | Menor; se retira junto a `DefaultRankingEngine` en F4. |
| 14 | Knowledge Mining no cableado | ⏸ | **Decisión D3**: intencional hasta V3.3 (ADR-0035). Clases y tests conservados. |
| 15 | Doc del pipeline ≠ flujo real | 🟡 | Nota de estado real añadida al architecture book (F0). Alineación definitiva en F4, cuando V2.1 sea el flujo. |
| 16 | `except` silencioso en provider HTTP | ✅ | F1.4: logging añadido (`generic_provider_adapter.py`). |
| 17 | `_GENRE_MAP` duplicado | ✅ (no aplica) | Falso: una sola definición en `canonical_metadata.py`. Sin acción. |

## Fases del plan (Anexo B)

| Fase | Estado | Contenido |
|------|--------|-----------|
| F0 | ✅ | ADR-0035 + nota architecture book §5. |
| F1 | ✅ | Quick wins (hallazgos 1, 3–7, 16). |
| F2 | 🟡 | Deprecación de `app.py`; borrado final pendiente (criterio: sin consumidores). |
| F3.1–3.2 | ✅ | `AcquiredPage.candidates` sin pérdida + `domain_adapter`. |
| F3.3 | ✅ | `ResolutionDecisionPolicy` + paridad con `decide()` (250 obras, 0 discrepancias). |
| F3.4 | ✅ | `IUniverseResolver`/`V21UniverseResolver` + serialización canónica determinista. |
| F3.5 | ✅ | Integrado en `AcquisitionService` (provisional/definitivo): las sesiones reales de `platform.py` usan `SessionUniverseResolver` (V2.1 + `ResolutionDecisionPolicy` + serialización canónica). `SimpleUniverseMatcher`/`decide()` conservados como referencia de paridad hasta F4. Tests de integración en `test_session_resolution_v21.py`. |
| F4 | ⏳ | Migrar búsqueda web a V2.1, unificar `WorkGroup`, retirar V1 (`DefaultRankingEngine`, `RankingConfig` V1, `evidence_engine` V1) y `app.py`. |
| F5 | ⏳ | Deuda estructural (hallazgos 9–11, 13). |

## Deudas preexistentes detectadas durante la verificación (fuera del alcance de la auditoría)

- ~~`test_platform_api.py::test_create_and_list_and_get_job` (501 vs 201)~~ → **resuelto el
  2026-09-09**: el 501 es deliberado (V3.2, evitar simular un "completed" falso en
  `platform_app.create_job`); el test se alineó con la especificación vigente
  (`test_create_job_is_pending_spec_501`).
- ~~`app.py`~~ → **retirado el 2026-09-09** (sin consumidores en runtime): eliminados
  `src/osap/api/app.py` y `tests/osap/test_api.py`; `api/__init__.py` queda solo
  documental (ADR-0035/D2).
- Hallazgos de seguridad en líneas NO modificadas por este trabajo → **ADR-0036
  (2026-09-09)** con severidad y decisión por hallazgo: S1 (SSRF `preview_source`)
  **mitigado** (guard + tests); S2/S6 fixture de desarrollo (bypass); S3/S4/S5 acciones
  de despliegue/entorno registradas, sin cambios de código.
- `test_golden_dataset` (7 casos) → **corregido el 2026-09-09** con el ajuste acotado del
  matcher (ver `docs/osap/f4-search-migration.md`).
- `test_openapi_generation::test_five_tags_grouped` → **resuelto el 2026-09-11**: el test
  estaba desactualizado (esperaba 5 tags); se corrigió al contrato real (12 tags) y se
  completó `_TAGS` en `api/http/shared.py` para que todos los tags usados estén declarados.
- Ranking V1 en el CLI → **retirado el 2026-09-11**: `cli/` usa `_ordered_candidates`
  (gather → WorkGrouper → DefaultWorkRanker, V2.1); `engine.rank()` queda solo para su test
  unitario y el harness `tests/fusion/`.
