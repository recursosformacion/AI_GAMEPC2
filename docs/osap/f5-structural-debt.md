# F5 — Deuda estructural: inventario y plan de división

**Estado:** espiga read-only (2026-09-09). Sin cambios de código. Disciplina: inventario de
responsabilidades → división mecánica → **cero cambios funcionales** (cada extracción empieza
y termina con la suite verde; facades/re-exports para no romper imports; no se aprovecha el
refactor para tocar comportamiento). Referencia: `code-audit-2026.md` hallazgos 9–11, 13.

## Inventario de responsabilidades por módulo grande

### `api/platform.py` — 2 616 líneas (más crítico)
`PlatformApi` (~200 métodos) mezcla use-cases de todos los dominios con estado privado
(container, `_resolution_store`, cachés `_work_rep_cache`, votos, sesiones de fuentes,
KnowledgeStore/oidc):

| Grupo de métodos (aprox.) | Responsabilidad | Métodos |
|---|---|---|
| Search | búsqueda + modelo + intent + enrich | `create_search/get_search/search_model/_run_search/_enrich_search_results/_focused_representations/_merge_same_work/detect_intent/_paginate` (+ privados `_to_rep/_work_key/_dedupe_reps/_cache_work_reps/_search_signature/_selection_payload/_fetch_url_bytes/_validate_to_contract/_title_core_match`) |
| Resolution sessions | sesiones de resolución + selección/validación/score | `create_resolution_session/resolve_session/_build_acquisition_service/set_acquisition_acquirers/select_best_representation/get_work_selection/score_contract_for_session/run_resolution_worker/get_resolution_session/list_resolution_results` (+ `_validate_best_representation/_all_downloadable/_match_work_identity/_best_downloadable/_resolution_session_row/_resolution_item_row`) |
| Composers | catálogo/obras/aliases/fusión | `list_composers/get_composer/get_composer_biography/composer_works/get_work/merge_composers/create_composer/review_composer/add_alias/list_aliases/move_alias/promote_alias/set_attribution/composer_review_stats/catalogues` |
| Votes & usuarios | votos/estadísticas/auth | `votes/principal_for/current_user/require_can_vote/require_admin/cast_vote/work_statistics/composer_statistics/votes_overview/register_user/verify_email/_auth_result` |
| Providers & op-admin | configuración operativa | `list_providers/get_provider/_provider_response/list_op_providers/upsert_op_provider/delete_op_provider/set_op_provider_wired/get_op_config/set_op_config` |
| Sources | fuentes repo/sesión/descubrir | `list_repository_sources/get_repository_source/*_session_source/preview_source/suggest_source/list_source_suggestions/resolve_source_suggestion/discover_sources/_seed_sources` |
| Corrections | propuestas + resolución | `submit_correction/list_corrections/resolve_correction/_correction_*` |
| Knowledge & system | knowledge/health/dev/oidc/version/statistics/admin | `knowledge/health/storage_info/dev_auth_bypass/dev_session/oidc_*/version/statistics/storage_web/admin_overview/admin_users_*` |

Más clases/helpers de nivel de módulo: `KnowledgeStore`, `SourceCatalog`, `SessionSources`,
`_validate_preview_url`, DTOs auxiliares, `_genre_id_for_name`/`_format_for_name`.

### `api/platform_app.py` — 2 580 líneas
`create_platform_app` (1 closure) con ~79 endpoints y ~35 constructores DTO (`_*_dto`).
Agrupación por tags ya parcial: jobs, providers, sources, admin, knowledge, system, votes,
composers, catalogues, resolution, corrections. Los endpoints son closures que capturan
`api`/`ok`/`fail`.

### `api/contracts.py` — 842 líneas
~150 modelos Pydantic (`_Frozen`): search, providers, sources, jobs, knowledge, system,
votes, composers (mayor bloque), resolution/sessions, works, admin. Sin lógica; puro agrupado.

### `infrastructure/state/op_store.py` — 708 líneas
`_MemoryStore` (~20 métodos) y `_MysqlStore` (mismos ~20 con SQL + `_conn/_run`), `_init`+
`_migrate` (DDL, ~100 líneas), `_decode_provider_row`/`_encode_description` y fábrica
`build_op_store`. Responsabilidades: almacén en memoria, almacén SQL, esquema/migraciones,
serialización provider, composición.

### `infrastructure/resolution/…resolution_store.py` — 533 líneas
Análogo (memoria + MySQL + esquema de sesiones/provider_results/items). No se dividió en la
auditoría original pero aplica el mismo criterio (onda posterior).

### `providers/adapters/generic_provider_adapter.py` — 603 líneas
Responsabilidades mezcladas: modelos YAML (`Endpoint`/`ProviderDefinition`/`ProviderQuery`),
HTTP (`ProviderHttpClient`), mapeo genérico (mappings, transforms, coacciones `_as_*`,
`_build_metadata/_build_resource/_build_work/_resolve_url`), loading de definiciones YAML
(`load_definition*`, `_parse_endpoints`, auth), y el adaptador (`GenericProviderAdapter`,
`ProviderFetcher`).

### `cli/main.py` — 679 líneas
Parser + comandos (`resolve`, `download`, `search`, `catalog`, `chorus`, `validate`) con
helpers de UI/impresión en el mismo fichero.

### Datos hardcodeados (OCP, hallazgo 11 corregido)
`application/canonical_metadata.py` (`_GENRE_MAP`, `_voices`, normalización) y tablas de
`lexicon.py` son datos-en-código. `Lexicon` ya carga `lexicon/*.yaml`; el resto se externaliza
a ficheros de datos cargados en arranque (onda posterior, sin cambio de comportamiento).

## Plan de división (orden por riesgo, cada slice = suite verde)

| Slice | Contenido | Riesgo |
|---|---|---|
| **F5.1 contracts** | `contracts.py` → paquete `api/contracts/{base,search,jobs_system,sources_corrections,admin_selection,votes,composers,works_resolution}.py` con `__init__` facade re-exportando los 97 modelos (imports existentes intactos). | Bajo |

**Progreso F5.1 (2026-09-09):** ✅ **completo** — división generada por AST (orden original,
sin referencias hacia delante) con imports cruzados calculados por módulo. Verificación:
ruff ✅, mypy ✅, imports de `platform`/`platform_app` ✅, 82 tests ✅ (único fallo
`test_openapi_generation::test_five_tags_grouped`, **preexistente en HEAD**: el test espera
5 tags y la app ya tiene Admin/Support).
| **F5.2 op_store** | `op_store.py` → `infrastructure/state/op/{memory.py, mysql.py, schema.py, factory.py}` + facade re-export. Mismo comportamiento (incl. herencia actual). | Bajo |

**Progreso F5.2 (2026-09-09):** ✅ **completo** — `state/op/memory.py` (`MemoryStore`+`now`),
`state/op/mysql.py` (`_MysqlStore` SQL + schema + helpers decode/encode),
`state/op/factory.py` (`build_op_store`) y `state/op/__init__.py`; `op_store.py` queda como
facade pura re-exportando `build_op_store`, `_MemoryStore`, `_MysqlStore`, `_now`.
Verificación: ruff ✅, mypy ✅, 38 tests ✅ (op_store/corrections/selección).
| **F5.3 generic adapter** | `generic_provider_adapter.py` → `adapters/generic/{models,http,mapping,loader,adapter}.py`; privados compartidos pasan a `mapping.py`; facade re-export. | Bajo-medio |
| **F5.4 platform.py** | `PlatformApi` → `api/platform/` con `core.py` (contexto compartido: container/stores/cachés/fábricas) + grupos `search.py`, `resolution.py`, `composers.py`, `votes.py`, `providers_admin.py`, `sources.py`, `corrections.py`, `knowledge_system.py`; `PlatformApi` pasa a fachada de delegación (move puro). | Alto (mayor) |
| **F5.5 platform_app** | Rutas y DTOs → `api/http/` por dominio + `shared.py`/`context.py`; `platform_app.py` compone con `include_router`. | Alto |
| **F5.6 cli** | `cli/main.py` → `cli/{parser,resolve,download,search,catalog,chorus,validate,ui}.py` con helpers compartidos. | Medio |
| **F5.7 datos (OCP)** | Externalizar `_GENRE_MAP`/tablas a `resources/canonical/*.yaml` cargadas en arranque. | Medio |
| **F5.8 resolution_store** | Mismo patrón que F5.2 (onda posterior). | Bajo-medio |

**F5.5 ✅ CERRADO (2026-09-10, incl. F5.5-clean):**
- `platform_app.py` = **151 líneas**: solo configuración/inicialización, `Container`,
  `HttpContext`, `VERSION` y **15 `include_router`**; **0 `@app.`**, **0 `_pa.`**.
- Infraestructura compartida movida a `api/http/shared.py` (DTO mappers, `_resp/_example/
  _error`, `_standard_errors`, `_*_200`, `_TAGS`) y `api/http/context.py` (`HttpContext`:
  `api`+`container`, `ok`/`fail`).
- Routers en `api/http/`: `system`, `jobs`, `knowledge`, `auth`, `providers`, `sources`,
  `support`, `votes`, `search`, `composers`, `works`, `sessions`, `admin`, `admin_ops`,
  `omr` (migrado desde `support.py`).
- Eliminados todos los `# type: ignore[misc]` (0 restantes) y los imports perezosos `_pa`.
- Verificación: ruff global ✅ · mypy ✅ (282 fuentes) · OpenAPI **70 paths / 0 duplicados**
  · `test_platform`+`test_platform_api` 36 ✅ · `test_composers`+`test_votes` 37 ✅ ·
  correcciones/auth/sesión/genre/preview/score 47 ✅.
- Pendiente posterior: F5.6 (CLI), F5.7 (datos OCP), F5.8 (resolution_store).

## F5.6–F5.8 — Análisis de deuda (2026-09-11, read-only)

### F5.6 — CLI (`cli/main.py`, 680 líneas, 28 defs, 8 comandos)
Comandos: `resolve`, `list`, `info`, `search`, `download`, `catalog`, `chorus-generate`,
`validate`. Mezcla: parser (`_build_parser`), construcción de request (`_build_request`),
resolución/selección (`_run_resolve`, `_choose_candidate`, `_choose_work_then_repr`),
presentación (`_print_summary`, `_print_work_detail`, `_print_result`, `_work_list_line`,
`_status_note`), y un enricher (`MetadataEnricher`, import directo). Sin uso de
`PlatformApi`/`WorkResolutionEngine` (usa container/use-cases).
- **Deuda:** un fichero con parser+comandos+UI; duplicación de helpers de request con otros
  consumidores.
- **Plan:** `cli/{parser,resolve,search,download,catalog,chorus,validate,ui}.py` con
  `parser`/`ui` compartidos y `main.py` como entrypoint de composición. Move literal.
- **Riesgo:** medio (es interacción de usuario; no toca contratos REST).
- **Aceptación:** `test_cli` + smoke manual de `--help`/comandos; ruff/mypy.

### F5.7 — Datos OCP (`lexicon.py` 500 líneas, `canonical_metadata.py` 241)
Tablas hardcodeadas: `lexicon.py` (`_STOPWORDS`, `_PROPER_NAMES`, `_PROVIDER_WORDS`,
`_CATALOGUE_PREFIXES`, categorías…) y `canonical_metadata.py` (`_GENRE_MAP`,
`_VOICE_PATTERNS`). Existe `resources/canonical/` (datos ya externalizados para el
`Canonicalizer`). `Lexicon`/`MetadataEnricher` son los consumidores.
- **Deuda OCP:** añadir géneros/dicción exige tocar código.
- **Plan:** externalizar a `resources/canonical/*.yaml` (o `lexicon/*.yaml`) y cargar en
  arranque con **valores idénticos**; sin tocar semántica.
- **Riesgo:** medio-alto (afecta normalización/agrupación); hacerlo al final.
- **Aceptación:** tests de normalización/metadata/grouping + golden 27/27 sin cambios.

### F5.8 — `resolution_store.py` (534 líneas, 7 defs; `_MemoryStore`, `_MysqlStore`, schema,
`_item_same`, `_json_eq`, `build_resolution_store`)
Consumido por `api/platform/main.py` (sesiones) y tests de resolución. Persiste
`resolution_sessions`/`provider_results`/`resolution_items` (ADR-0033) con semántica
delicada: etapas `provisional/definitive`, **bump de `revision` solo si el contenido cambia**
(`_item_same`/`_json_eq`) y paginación de items.
- **Deuda:** mismo problema que `op_store.py` (dos stores + schema + factory en un fichero).
- **Revisión arquitectónica previa (recomendada):** confirmar que la división no altera
  orden/igualdad de items ni la lógica de revisión; documentar invariantes antes de tocar.
- **Plan:** `state/resolution/{memory,mysql,schema,factory}.py` + `resolution_store.py`
  como facade (mismo patrón que F5.2), conservando literalmente `_item_same`/`_json_eq`.
- **Riesgo:** bajo-medio (movimiento, no lógica), pero alto impacto si se rompe la igualdad.
- **Aceptación:** `test_resolution_*`, `test_session_resolution_v21`, `test_platform_api`.

**F5.6 ✅ CERRADO (2026-09-11):** `cli/main.py` (680 líneas) → paquete `cli/`:
`parser.py` (`_build_parser`), `requests.py`, `ui.py`, `resolve.py`, `commands.py`;
`main.py` (53 líneas) = entrypoint/composición. Move literal; `test_cli` ✅; ruff/mypy ✅
(288 fuentes). Eliminado `entry.py` duplicado generado durante el split.

**F5.8 ✅ CERRADO (2026-09-11):** `resolution_store.py` (534 líneas) →
`state/resolution/{memory,mysql,factory}.py` + `__init__`; `resolution_store.py` queda como
**facade** re-exportando `build_resolution_store`, `_MemoryStore`, `_MysqlStore`, `_now`,
`_j`, `_item_same`, `_json_eq`. **Invariantes preservadas literalmente**: `_item_same`,
`_json_eq`, lógica de `revision` provisional→definitiva y etapas. Verificación: ruff ✅ ·
mypy ✅ (291 fuentes) · resolución/sesión/universe 43 ✅ · `test_platform_api` 21 ✅.

**F5.7 ✅ CERRADO (2026-09-11):** tablas externalizadas a `resources/canonical/`:
`genre_map.yaml` (`_GENRE_MAP`), `voice_patterns.yaml` (`_VOICE_PATTERNS`, con flags
re-compilados) y `lexicon.yaml` (categorías, stopwords, nombres propios, palabras de
proveedor, prefijos de catálogo y `_NUMBERING_RE`). Carga en import con valores
**idénticos** verificados contra baseline (comparación programática exacta: sets/dicts/
patrones/iguales). Añadir géneros/dicción ya no exige tocar código (OCP). Verificación:
ruff ✅ · mypy ✅ (291 fuentes) · canonical/metadata/lexicon/golden/grouping/search-pipeline
**68 ✅** · platform/sesión/universe/matcher **56 ✅** · golden 27/27 sin cambios.

**Bloque F5.6–F5.8 ✅ completo** (F5.6 CLI, F5.8 resolution_store, F5.7 datos OCP).

**Orden recomendado:** F5.6 → F5.8 (con la revisión de invariantes) → F5.7 (el más
sensible a comportamiento). Cada fase con ruff/mypy + suites específicas + golden.

## F5.4 — Plan de ejecución de `PlatformApi` (dedicado, alto riesgo)

**Estado:** ⏳ preparado (2026-09-09). Iteración dedicada; sin cambios aún.

**Estado:** ✅ **CERRADO (2026-09-10)** — los 9 dominios (más `jobs`, descubierto al
inventariar) están físicamente separados y la fachada `PlatformApi` no cambia.

### Fotografía final
```
src/osap/api/platform/
├── __init__.py      # fachada: re-exporta PlatformApi, VERSION y helpers de soporte
├── main.py          # PlatformApi(solo __init__) + composición de mixins + VERSION
├── core.py          # PlatformApiCore: estado tipado + helpers transversales reales
│                    #   (_paginate/_to_rep/_work_key) + stubs cruzados
│                    #   (list_providers/_require_admin/composers/composer_review_stats/_auth_result)
├── _support.py      # KnowledgeStore/SourceCatalog/SessionSources + helpers/constantes
├── search.py        # SearchMixin (13)   ├── resolution.py  ResolutionMixin (16)
├── composers.py     # ComposersMixin (16)├── votes_users.py VotesUsersMixin (13)
├── providers.py     # ProvidersMixin (9) ├── sources.py     SourcesMixin (13)
├── corrections.py   # CorrectionsMixin (5)├── knowledge.py   KnowledgeMixin (1)
├── system.py        # SystemMixin (17)   └── jobs.py        JobsMixin (3)
```
106 métodos de negocio repartidos en mixins; `main.py` solo inicialización; sin duplicados.

### Comprobación de cierre (todos verdes)
- `main.py` → solo `__init__` (fachada + composición + inicialización).
- `core.py` → estado compartido tipado + ayudas realmente transversales; sin métodos de
  dominio escondidos.
- Cada método de negocio en un único mixin; **0 duplicados** (escaneo AST).
- `platform.py` monolítico ya no existe (`Test-Path src/osap/api/platform.py → False`);
  el paquete lo sustituye y la fachada conserva contratos (imports de `platform_app` y
  tests intactos).
- ruff global ✅ · mypy global (265 fuentes) ✅ · `test_platform_api` 36 ✅ ·
  composers/votes/auth/identity 57 ✅ · corrections/resolution/sesión/genre/preview 53 ✅ ·
  golden 27/27 ✅. Único rojo: `test_openapi_generation::test_five_tags_grouped`
  (**preexistente en HEAD**, tags Admin/Support), ajeno a F5.4.
- Incidencia resuelta: `test_score_contract_producer` parcheaba `_fetch_url_bytes`/
  `_validate_to_contract` en el paquete; el mixin de resolución los referencia vía
  `_platform_module` para conservar ese monkeypatch (sin tocar tests).

**Aprendizajes del patrón (registrados):** extraer decoradores en el corte (`@staticmethod`);
contratos de estado añadidos solo por dominio; los helpers cruzados se exponen como stub en
`core` con su firma real; los métodos transversales terminan en `core`, no en `main`.

### Estado compartido real (`PlatformApi.__init__`, platform.py:660)
`_container`, `_knowledge`, `_catalog`, `_sessions`, `_searches`, `_search_cache`,
`_work_rep_cache`, `_work_rep_order`, `_jobs`, `_representations`, `_job_counter`,
`_oidc_pending`, `_oidc_pending_path`, `_oidc_pending_lock`, `_suggestion_counter`,
`_store`, `_resolution_store`, `_acquisition`.

### Patrón de división (sin cambiar contratos)
- `PlatformApi` se convierte en **fachada compuesta por mixins** (una sola instancia):
  `PlatformApi(CoreMixin, SearchMixin, ResolutionMixin, ComposersMixin, VotesUsersMixin,
  ProvidersMixin, SourcesMixin, CorrectionsMixin, KnowledgeMixin, SystemMixin)`.
- `CoreMixin` (nuevo `platform/core.py`) contiene `__init__` (estado compartido) y los
  helpers transversales (`_paginate`, `_require_admin`, `_auth_result`, `_to_rep`,
  `_work_key`, `_to_rep`/dedupe donde apliquen) con sus dependencias.
- Cada mixin agrupa los métodos de su dominio (move literal, sin tocar cuerpos). Las
  llamadas cruzadas entre dominios siguen siendo `self.…` (la instancia compone todo).
- Helpers de nivel de módulo (p. ej. `_search_signature`, `_selection_payload`,
  `_validate_preview_url`, `_fetch_url_bytes`, `_validate_to_contract`) y las clases de
  soporte (`KnowledgeStore`, `SourceCatalog`, `SessionSources`, `_seed_sources`) van a un
  módulo compartido del paquete importado por los mixins.
- Antes de mover: verificar que no hay **colisión de nombres de método** entre dominios y
  listar las dependencias de helpers por mixin (imports explícitos en cada módulo).

### Criterios de cierre F5.4
1. `ruff` y `mypy` globales limpios.
2. Suite completa de `platform`/`platform_api` (búsqueda, resolución/sesiones, compositores,
   providers/sources, corrections, knowledge/system, jobs, selection) ✅.
3. Imports de `platform_app` intactos y goldens sin cambios.
4. `test_openapi_generation::test_five_tags_grouped` sigue rojo **solo por su deuda
   preexistente** (tags Admin/Support), nunca por F5.4.

## Guardas (sin cambios funcionales)
1. Cada slice mueve código **literalmente**; nada de mejoras, renombrados funcionales ni
   cambios de contrato. Los re-exports/facades mantienen los imports públicos.
2. Antes/después de cada slice: `ruff`, `mypy`, y suite del dominio afectado; los golden de
   plataforma/búsqueda/resolución deben quedar idénticos.
3. `platform.py`/`platform_app.py` son los de mayor riesgo: se recomienda F5.4/5.5 como slices
   independientes, con `test_platform*` + `test_platform_api` verdes en cada paso (mover
   grupos completos de métodos, no a medias).
