# osap-api → osap-storage v2 (`persons` / roles) — mapa de adaptación

**Rama de trabajo:** `fork-new-db` (la `v1` queda congelada en la rama `v1`).
**Estado:** osap-storage está cerrando la migración; **nada se sube a producción** hasta validar en
pre. La subida implica **BBDD modificada**.

## 1. Contexto

| Elemento | Valor |
|---|---|
| BD nueva (modelo `persons`) | `osap-storage` (dev): 289.036 works, 43.875 persons, 252.395 files |
| BD antigua (respaldo del modelo `composers`) | `osap-storage_v1` |
| Convención de nombres | **V3**: columnas con prefijo de tabla (`works_*`, `persons_*`, `representations_*`, `works_person_roles_*`, `wksta_*`) |
| Contrato de consulta | `GET /api/v1/persons?role=composer`, `role=composer,arranger` (los ejemplos usan nombres de rol) |

## 2. Mapa tabla → concepto de osap-api

| osap-storage v1 | osap-storage v2 | Concepto en osap-api |
|---|---|---|
| `composers` | `persons` (+ `works_person_roles`) | Composer/Persona (ficha, biografía, recuentos) |
| `composer_aliases` | `persons_aliases` (`person_id`, `person_aliases_alias`, `..._normalized_alias`, `..._name_type`, `..._language_id`, `..._source`) | Alias (pantalla Alias, fusión) |
| `composer_identifiers` | `persons_identity` (`identity_name`, `identity_name_norm`, `identity_type`, `identity_value`, `identity_source`, `identity_is_anchor`, `identity_strength`, `identity_channels`) | Identidad de persona (resolución, dedupe) |
| `composer_evidence` / `composer_merge_history` | `persons_evidence` / `persons_merge_history` (+ `persons_merge_snapshot`) | Evidencia y fusiones |
| `composer_authority*` | `persons_authority` / `persons_authority_name` (pendiente de enlace) | Autoridad (no consumir aún) |
| `catalogues` | `catalog` (13) | Catálogos |
| `women.composer`/`works.composer_id` | **`works_person_roles`** (`..._work_id`, `..._person_id`, `..._role_id`, `..._order`) | Atribución por rol (compositor=1, arreglista=3, intérprete=10, editor=6) |
| `works.title/catalogue/year/...` | `works.works_title/works_catalogue/works_year/...` | Obra (columnas renombradas) |
| `works.genre`, `genre_id` | `work_genres` (junction) | Géneros |
| `works.instrumentation` | `work_instruments`, `works_instruments` (LONGTEXT), `work_parts`, `work_voices`, `work_ensembles` | Plantilla/partes/voces |
| `works.tags` | `work_tag` + `tag_work` (catálogo) | Tags |
| — | `work_language` + `languages` | Idiomas |
| — | `works.works_voicing` (JSON), `works.works_key`, `works_origin`, `works_origin_id`, `works_created_at/updated_at` | Campos nuevos |
| `archive_entries` + `files` (por JOIN) | **`works_resources`** (`..._work_id`, `..._representation_id`, `..._type`, `..._name`, `..._relative_path`, `..._status`, `..._file_id`, `..._url`, `..._archive_id`) | Recurso descargable (fichero) por obra |
| — (nuevo) | `representations` (`..._origin`, `..._origin_id`, `..._type`, `..._source_name`, `..._license`) + `representation_persons` | Ediciones/representaciones (hoy solo CPDL: 81.983 `cpdl/edition`) |
| `votes` | `votes` (igual) | Votos (user_id, work_id, vote, voted_at, vote_day) |
| `work_statistics` | `work_statistics` con prefijo `wksta_*` | Agregados de votos |
| — | `works_person_import` (364.575) | **Staging** de atribución (no consumir) |
| — | `rism_*`, `cpdl_editions*`, `persons_correction_history`, `works_field_history`… | Fuentes/auditoría (fase posterior) |

## 3. Roles (tabla `roles`)

| id | role_name | uso en osap-api |
|---|---|---|
| 1 | Compositor/a | composer (principal) |
| 2 | Libretista / Letrista | librettist |
| 3 | Arreglista | arranger |
| 4 | Orquestador/a | orchestrator |
| 5 | Transcriptor/a | transcriber |
| 6 | Editor/a Musical | editor |
| 7 | Completador/a | completer |
| 8 | Director/a de Orquesta | conductor |
| 9 | Director/a de Coro | choir_conductor |
| 10 | Intérprete / Solista | performer |
| 11 | Maestro/a de capilla | kapellmeister |
| 12 | Preparador/a vocal | vocal_coach |
| 13 | Dedicatario/a | dedicatee |
| 14 | Mecenas / Patrocinador/a | patron |
| 15 | Inspirador/a / Musa | inspiration |

Categorías (`category`): 1 Composición, 2 Autoría textual, 3 Adaptación y edición, 4 Interpretación
(`roles_categoria` relaciona roles con categorías).

**Contrato a consumir:** `GET /api/v1/persons?role=composer[,arranger…]`. En osap-api traducimos
nombre de rol ↔ id con esta tabla (mapeo estable en código/config, no en la BD de osap-api).

## 4. Impacto en osap-api (qué hay que tocar)

| Zona | Ficheros | Cambio |
|---|---|---|
| Cliente de storage | `infrastructure/storage/storage_composer_client.py` | `composers` → `persons` (+ `role`), alias/identidad, biografía |
| Servicio/contratos | `application/composers_service.py`, `api/contracts/composers.py`, `api/http/composers.py`, `api/platform/composers.py` | `works_count` por rol, campos de persona, recuento de alias |
| Obras | `infrastructure/storage/work_store.py` | columnas `works_*`, atribución por `works_person_roles`, recursos (`works_resources`) |
| Votos | `infrastructure/persistence/storage_vote_store.py`, `application/votes_service.py`, `domain/votes.py` | `work_statistics` con prefijo `wksta_*`; `votes` igual |
| Índice | `script/index_works.py`, `script/sync_index.py`, `script/normalize_index_identity.py`, `infrastructure/catalogs/index/index_catalog_provider.py` | Origen de obras/ficheros: `works` + `works_resources` (+ `persons`) en vez de `works`+`archive_entries` |
| OMR | `infrastructure/providers/fetchers/omr_fetcher.py` (+ test nuevo) | Revisar de dónde lee el dump/ids con el modelo nuevo |
| Web | `web/src/pages/AdminComposersPage.tsx`, `AdminComposerDetailPage.tsx`, `AliasPage.tsx`, `ComposersPage.tsx`, `ComposerDetailPage.tsx`, `ComposerSearchSelect.tsx`, `state/composers.ts`, `api/ApiClient.ts`, `api/types.ts` | Pantallas de personas/roles (WIP ya en la rama) |

Estado de la rama `fork-new-db`: estos cambios están **consolidados** (ruff/mypy limpios, 47 tests
clave en verde) pero la adaptación funcional completa depende de que storage exponga `persons`.

## 5. Decisiones abiertas (necesarias antes de la puesta en marcha)

> **Nota (arquitectura de fuentes):** para **CPDL y RISM la búsqueda la hace osap-storage en sus
> índices independientes** (`cpdl_editions*`, `rism_persons`, `rism_sources`…). osap-api no debe
> indexarlos ni replicarlos: consume los endpoints de storage. Esto afecta al punto 6.

1. **`works_count`**: ¿obras distintas con `role_id=1`, o total de filas de `works_person_roles`?
   (una obra puede tener varios compositores).
2. **Ficha de persona**: ¿un único payload (`persons` + biografía + alias + roles) o endpoints
   separados (`/persons/{id}`, `/persons/{id}/aliases`, `/persons/{id}/works`)?
3. **Alias**: ¿se mantienen los endpoints de fusión (`merge`) con `persons_id` y validación de
   identidad (`persons_identity.identity_is_anchor`)?
4. **Recursos**: `works_resources.works_resources_status` (visto `stored`) → ¿`available` = status? y
   ¿la URL pública (CDN) se compone como hasta ahora a partir de `file_id`/`relative_path`?
5. **Índice**: ¿se reconstruye leyendo la BD nueva (`works` + `works_resources`) o el dump OMR?
   Afecta a `script/index_works.py` y al normalizador de identidad.
6. **Representaciones**: las `representations` actuales son solo CPDL (`cpdl/edition`). ¿Se abrirán
   también omr/imslp/mutopia con el mismo modelo, o el índice seguirá derivando de `works_resources`?
7. **Compatibilidad**: ¿se elimina `/api/v1/composers` (404) o se mantiene como alias temporal?

## 6. Puesta en marcha (cuando storage cierre `person`)

### 6.0 Ya implementado en osap-api (`fork-new-db`)
- **Endpoints nuevos** (`api/http/persons.py`):
  - `GET /api/v1/persons?role=composer[,arranger…]` (rol desconocido → 400)
  - `GET /api/v1/persons/{person_id}`
  - `GET /api/v1/persons/{person_id}/works`
- **Mapeo de roles** en `domain/person_roles.py` (tabla `roles` 1..15; parseo y validación).
- **Cliente de storage** con **puente**: intenta `/persons` y cae a `/composers` si aún no existe
  (`_call` / `_call_persons_first`), y anota `roles` a partir de `role_ids` cuando storage los envíe.
- `roles` añadido a `ComposerSummaryResponse`/`ComposerDetailResponse` (aditivo, default `[]`).
- Tests: `tests/osap/test_person_roles.py`, `tests/osap/test_persons_client.py` (8 en verde).

Verificado en instancia local: `?role=composer` → 200; `?role=pianist` → 400;
`?role=composer,arranger` → 200; detalle y obras → 200 (con fallback a la v1).

1. Confirmar BD destino en pre y que la migración está cerrada.
2. Adaptar osap-api en `fork-new-db` con las rutas/roles definitivos.
3. Levantar el stack en pre y verificar: búsqueda, ficha de persona (por rol), obras, alias, votos,
   visor y descargas; y el **índice** reconstruido si aplica.
4. Solo entonces, plan de subida a producción (incluye migración de BBDD).
