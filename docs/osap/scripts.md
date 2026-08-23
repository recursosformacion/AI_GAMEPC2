# Scripts de OSAP

Documento de referencia de los scripts lanzables de OSAP. **Regla permanente:** todo
script que se quede en `scripts/` (o `script/`) y sea lanzable debe llevar un resumen
corto al principio (docstring en Python, comentario en PowerShell) y estar documentado
aquí. Esta regla aplica también a los scripts nuevos.

Convenciones:
- Los scripts de **osap-storage** se ejecutan con el venv de storage
  (`osap-storage/.venv/bin/python scripts/<script>.py`), y por defecto usan `config.yaml`
  (la BD se elige con `OSAP_CONFIG=config.production.yaml` o `--db`).
- Los scripts de **osap-api** se ejecutan con `PYTHONPATH=<osap-api>` y su venv.
- Muchos scripts admiten `--dry-run` para validar sin escribir.

---

## osap-storage/scripts

| Script | Propósito |
|--------|-----------|
| `backfill_works_pdmx.py` | Backfill de metadatos de obras desde `pdmx_index.db`. |
| `backfill_attribution.py` | Mueve atribuciones no-persona (anónima/tradicional/popular/atribuida) de `works.composer` a `attribution_type`+`attribution_note`. |
| `candidate_resolver.py` | Resuelve candidatos a Composer minimizando red: prolíficos (≥N obras) aceptados sin red; el resto solo con autoridad local. Propuestas en `composer_candidate`. |
| `candidate_cleanup.py` | Clasifica los candidatos `unknown` (mojibake/no_persona/qualifier/real/review) y persiste los accionables en `composer_candidate`. |
| `candidate_priority.py` | Prioriza los candidatos por impacto (nº de obras), agrupando por identidad (`name_key`). |
| `catalog_statistics.py` | Estadísticas del catálogo tras la pasada de identidad (cobertura, resolución, gaps, candidatos). |
| `incorporate_candidates.py` | Incorpora los candidatos resueltos de `composer_candidate` al Maestro (crea Composer por `name_key`, aliases + evidence, asocia obras). |
| `incorporate_resolutions.py` | Materializar `composer_identity_resolution` en el Maestro (crear Composer por identidad, asociar obras). |
| `ingest_app_responses.py` | Llevar la respuesta de APP a la tabla de proveedores (simulado). |
| `ingest_authority.py` | Ingerir snapshots JSON (`data/authority/*.json`) en `authority_identifiers`. |
| `load_composer_authority.py` | Cargar la autoridad de compositores desde `compositores_wikidata.json`. |
| `run_works_matching.py` | Pasada de matching de obras contra el Maestro Composer (storage es el escritor). |
| `test_authority_coverage.py` | Probar la cobertura de la autoridad local sobre las primeras obras. |

### candidate_cleanup.py
Clasifica las atribuciones `unknown` de `composer_identity_resolution` en categorías
(`mojibake`, `no_persona`, `qualifier`, `real`, `review`) y persiste solo los accionables
(`real` + `review`) en `composer_candidate` (migración 027). Reusa `classify_composer_name`,
`is_mojibake` y `clean_composer_name` de osap-storage. Mojibake/no_persona/qualifier NO crean Composer.
```
python scripts/candidate_cleanup.py --db osap_storage [--db-user U] [--db-password P] \
    [--test prod-10000-001] [--dry-run]
```

### candidate_priority.py
Prioriza los candidatos de `composer_candidate` por impacto (nº de obras), agrupando las
variantes por `name_key` (misma normalización que identity_resolver). Devuelve el top N de
compositores que concentran más obras → los que darán mayor cobertura por resolución.
```
python scripts/candidate_priority.py --db osap_storage [--db-user U] [--db-password P] \
    [--label real|review|all] [--limit 200]
```

### catalog_statistics.py
Reporte SOLO LECTURA de lo descubierto tras la pasada de identidad: cobertura de
compositor, distribución de la resolución, forma del catálogo, gaps de datos de las obras
(año/instrumentación/idioma) y candidatos a ampliar (compositores con nombre sin Composer,
priorizados por nº de obras). Sirve para priorizar la siguiente fase sin tocar obras.
```
python scripts/catalog_statistics.py --db osap_storage [--db-user U] [--db-password P] \
    [--test prod-10000-001]
```

### backfill_attribution.py
Mueve las atribuciones no-persona de `works.composer` (anónima/tradicional/popular/atribuida)
a los campos nuevos `attribution_type` (ANONIMA/TRADICIONAL/POPULAR/ATRIBUIDA) y
`attribution_note` (texto original, ej. "Traditional English"), y limpia composer/composer_id.
Idempotente.
```
python scripts/backfill_attribution.py --db osap_storage [--db-user U] [--db-password P] [--dry-run]
```

### backfill_works_pdmx.py
Backfill de metadatos de obras desde PDMX.
```
python scripts/backfill_works_pdmx.py [--db BD] [--pdmx pdmx_index.db] [--limit N] [--dry-run]
```
`--limit 0` = todas; `--dry-run` no escribe.

### incorporate_resolutions.py
Convierte el resultado persistido de la pasada de identidad (`composer_identity_resolution`)
en Composer reales del Maestro, agrupando **por identidad** (no por obra):
- `matched_existing` → asocia obras al Composer existente.
- `resolved_*` → agrupa por VIAF/MBID/QID, crea un Composer una sola vez (aliases +
  identifiers + evidence), asocia todas sus obras. Fuertes (VIAF/MBID) → `visible=1`;
  débiles (solo QID) → `visible=0` (revisión).
- `ambiguous` → placeholder hidden (`visible=0`, revisión), sin obras.
- `unknown` → conserva el resultado, no crea entidad.
- Idempotente: si ya existe por MBID/VIAF/nombre, enlaza en vez de crear.
```
python scripts/incorporate_resolutions.py --db osap_storage \
    [--db-user U] [--db-password P] --test prod-10000-001 [--dry-run]
```

### ingest_app_responses.py
Ingestor que lleva la respuesta de APP a la tabla de proveedores (flujo simulado).
```
python scripts/ingest_app_responses.py --in <archivo> [--out provider_results.jsonl]
```

### ingest_authority.py
Ingiere los snapshots JSON de autoridad (`data/authority/*.json`) en `authority_identifiers`.
```
python scripts/ingest_authority.py [--archive data/authority]
```

### load_composer_authority.py
Carga la autoridad de compositores en `composer_authority` desde
`compositores_wikidata.json`. Filtra personas, indexa por clave canónica.
```
python scripts/load_composer_authority.py --source <compositores_wikidata.json> \
    [--db BD] [--dry-run] [--stats]
```
En prod: `OSAP_CONFIG=config.production.yaml ... --db osap_storage`.

### run_works_matching.py
Pasada de matching de obras contra el Maestro Composer (storage es el escritor).
```
python scripts/run_works_matching.py [--config config.yaml] [--db BD] \
    [--api http://127.0.0.1:8001] [--limit 200]
```

### test_authority_coverage.py
Probar la cobertura de la autoridad local (`composer_authority`) sobre las N primeras obras.
```
python scripts/test_authority_coverage.py [--db BD] [--limit 100] [--from-id 0]
```

---

## osap-api/script

| Script | Propósito |
|--------|-----------|
| `build_composer_index.py` | Construir índice de compositores desde el dump de MusicBrainz (artists). |
| `build_composers_index.py` | Fusionar fuentes de compositores en `composers_index.json`. |
| `confidence_report.py` | Reporte de `resolution_confidence` sobre los 30 (FASE 5.8). |
| `cross_attribution.py` | Atribución cruzada reusando la capa de proveedores (FASE 5.8). |
| `diagnose_not_found.py` | Diagnóstico de los `not_found` de la autoridad local sobre N obras. |
| `download_composers.py` | Descargar fichero de compositores desde Wikidata (SPARQL). |
| `enrich_identifiers.py` | Enriquecer identificadores de obras/compositores desde fuentes abiertas. |
| `extract_composers_from_dump.py` | Extraer compositores del dump completo de Wikidata. |
| `fichas_30.py` | Fichas de ground truth de los 30 (evidencia, procedencia, conflictos). |
| `ground_truth_30.py` | Ground truth de resolución de los 30. |
| `index_works.py` | **Indexador local de obras multi-proveedor** (paso 1 del índice): lee OMR (osap-storage), IMSLP (Worklist API), Mutopia (make-table.cgi) y MusicBrainz (dump local) y puebla `index_works`+`index_representations` (osap-api) con normalización y dedupe. Uso: `python script/index_works.py --providers omr,imslp,mutopia,musicbrainz`. OMR construye `download_url={storage}/api/download/{file_id}` y `available=1`. MusicBrainz filtra a tipos de música artística (`--mb-types art`) por defecto. |
| `sync_index.py` | **Sincronización incremental del índice** con estado persistido en `sync_state` (tabla de osap-api): relanza `index_works.py` reanudando donde terminó (IMSLP desde `start`, OMR desde el último `work_id`, Mutopia completo). Para programar con cron/crontab cada X tiempo. Uso: `python script/sync_index.py --providers imslp,omr,mutopia [--omr-base-url https://...]`. |
| `identity_resolver.py` | **Resolver de identidad escalonado** (evidencia acumulada) sobre obras de storage. |
| `inventory_title_noise.py` | Inventario de patrones de ruido en títulos (FASE 5.7.2). |
| `process_250_batch.py` | Procesar 250 obras (`works250.json`) → resultados + resumen. |
| `process_250_identifiers.py` | works250 con enriquecimiento de identificadores. |
| `reconstruct_works.py` | Reconstrucción por obra (FASE 5.7). |
| `reeval_30.py` | Re-evaluar los 30 con el matcher nuevo (FASE 5.7.1). |
| `resolution_eval.py` | Evaluación guiada por evidencia (offline, FASE 5.6). |
| `resolution_regression.py` | Regresión de resolución sobre `works250.results.json`. |
| `simulate_storage_call.py` | Simulación del proceso completo storage → APP → respuestas. |
| `song_fusion_report.py` | Reporte de fusión de canciones (seguridad de la canción, luego compositor). |
| `trace_candidate_missing.py` | Diagnóstico de `candidate_missing`: dónde desaparece una obra. |
| `trace_candidate_missing_5.py` | Investigar los `candidate_missing` supervivientes (19,130,112,108,18). |
| `validation_report.py` | Validación de compositor → `resolved` seguro (FASE 5.8). |
| `works_resolve_experiment.py` | Experimento v1 de `/works/resolve` (250 obras). |
| `deploy.ps1` | Deploy de OSAP a producción (frontend + backend + reinicio). |
| `sync_db_down.ps1` | **Sincroniza la BD operativa de osap-api desde el VPS a desarrollo** (solo lectura): exporta de `osap_api` (excepto `app_config`) y restaura en la BD local `osap-api`. Permite que las pruebas locales trabajen con el índice real + storage/auth reales (`dev_mode=1`). Uso: `powershell -File script/sync_db_down.ps1`. |
| `pre_dbadmin_tunnel.ps1` | Túnel SSH para administración de BD. |

### candidate_resolver.py
Resuelve los candidatos de `composer_candidate` minimizando red: los prolíficos (≥ `--threshold`
obras, por defecto 20) se aceptan como `resolved_by_prolific` **sin red** (muchas obras en el
corpus = evidencia real); los de menos obras se resuelven solo con fuentes locales
(maestro + `composer_authority`, cero red). Registra `resolved_status` como propuesta en
`composer_candidate` (no crea Composer). Reusa `IdentityResolver` (con `local_only`).
```
PYTHONPATH=<osap-api> python script/candidate_resolver.py --limit 100 \
    --db-user osap --db-password osap2027 --db-name osap_storage [--threshold 20]
```

### sync_index.py
Sincronización incremental del índice con el estado persistido en `sync_state` (tabla de
osap-api, creada automáticamente). Relanza `index_works.py` por proveedor reanudando donde
terminó: IMSLP desde `start` (la Worklist API no expone cambios recientes → se relanza
completo y es idempotente), OMR desde el último `work_id` de storage, Mutopia completo.
Pensado para programarse con cron/crontab.
```
PYTHONPATH=<osap-api> python script/sync_index.py --providers imslp,omr,mutopia \
    --db-user osap --db-password osap2027 --db-api osap_api --db-omr osap_storage \
    --omr-base-url https://storage.openmusicrepository.com
```
Ejemplo cron (cada 6 h en el VPS):
```
0 */6 * * * cd ~/osap-api && PYTHONPATH=. .venv/bin/python script/sync_index.py \
    --providers omr,mutopia --db-user osap --db-password osap2027 \
    --db-api osap_api --db-omr osap_storage \
    --omr-base-url https://storage.openmusicrepository.com >> ~/sync_index.log 2>&1
0 3 * * *   cd ~/osap-api && PYTHONPATH=. .venv/bin/python script/sync_index.py \
    --providers imslp --db-user osap --db-password osap2027 \
    --db-api osap_api --db-omr osap_storage >> ~/sync_imslp.log 2>&1
```

### identity_resolver.py (script principal de la pasada)
Resolver de identidad escalonado (evidencia acumulada) sobre obras de osap-storage.
Persiste en `composer_identity_resolution`. Concurrencia por compositor único, cache,
autoridad local primero, reanudación (omite obras ya persistidas para el `test_id`).
```
PYTHONPATH=<osap-api> python script/identity_resolver.py \
    --limit 90000 --named-only --workers 8 --batch 250 \
    --db-user U --db-password P --db-name BD --test <test_id>
```
Flags: `--limit` (obras), `--named-only` (solo compositores no anónimos), `--from-id`,
`--workers` (concurrencia), `--batch` (persistencia incremental), `--test` (id de la pasada).
En prod: `--db-user osap --db-password osap2027 --db-name osap_storage`.

### Otros scripts (resumen)
- **Autoridad / datos**: `download_composers.py` (`--out`, `--limit`),
  `extract_composers_from_dump.py` (`--in <dump>` obligatorio, `--out`),
  `build_composer_index.py` (`--in artist.tar.xz`, `--out`),
  `build_composers_index.py` (`--src fuente=fichero` repetible, `--out`).
- **Evaluación de los 30 / 250**: `ground_truth_30.py` (`--sample`, `--out`),
  `fichas_30.py` (`--results`, `--gt`), `reeval_30.py`, `confidence_report.py` (`--gt`),
  `cross_attribution.py` (`--gt`, `--limit`), `validation_report.py` (`--gt`),
  `song_fusion_report.py` (`--gt`, `--limit`), `process_250_batch.py` (`--limit`, `--out`),
  `process_250_identifiers.py` (`--results`, `--archive`, `--limit`),
  `resolution_regression.py` (`--results`, `--table`, `--tsv`, `--emit-evaluation`),
  `resolution_eval.py` (`--results`, `--evaluation`, `--tsv`), `reconstruct_works.py` (obras...),
  `works_resolve_experiment.py` (`works_file`, `--base`, `--concurrency`, `--samples`).
- **Diagnóstico / traza**: `diagnose_not_found.py` (`--limit`, `--from-id`, `--works`),
  `trace_candidate_missing.py` (ids..., `--results`, `--live`),
  `trace_candidate_missing_5.py`, `inventory_title_noise.py`,
  `simulate_storage_call.py` (`--base`, `--in`, `--out`, `--limit`),
  `enrich_identifiers.py` (`--composer`, `--work`, `--works`, `--archive`).
- **Operaciones**: `deploy.ps1` (despliegue a producción, host `RemoteIA`),
  `pre_dbadmin_tunnel.ps1` (túnel SSH de phpMyAdmin del entorno PRE — script residual de
  otro proyecto, no parte de la operación de OSAP).
