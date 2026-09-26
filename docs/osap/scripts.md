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

### import_cpdl_works.py
Ingiere exports MediaWiki de ChoralWiki (CPDL) como filas de `works`
(`works_origin='CPDL'`, `works_origin_id`=id de página MediaWiki). Normaliza plantillas wiki
(Title/Composer/Voicing/Instruments/Genre/Language/Copy) y ediciones (`CPDLno`, editor,
ficheros, licencia). El voicing se escribe como **formación vocal**: `ensembles`
(`ensembles_code` en MAYÚSCULAS, dedupe) + `work_ensembles`; también
`works_person_import` y `languages`/`work_language`. Requiere las migraciones `007`/`008`.
Uso: `python scripts/import_cpdl_works.py --dir G:\cpdl_chunks` (o `--files`, `--dry-run`).


### analyze_works_content.py
Barrido offline (sin R2) del contenido de los `.mxl` de `G:\osap-storage`: calcula el
`sha256`+tamaño reales y los **guarda en `files`** (vía `storage_locations`), valida el
MusicXML y guarda el "número mágico" musical (`works.music_digest`, md5 de notas) para
detectar obras equivalentes entre ediciones. Reanudable con `--only-missing`.
Uso: `python scripts/analyze_works_content.py --only-missing --root G:\osap-storage`
(progreso cada 2000; probar con `--limit N`). Requiere la migración `034_works_music_digest`.


| Script | Propósito |
|--------|-----------|
| `backfill_works_pdmx.py` | Backfill de metadatos de obras desde `pdmx_index.db`. |
| `populate_ensemble_voices.py` | Puebla `ensemble_voices` descomponiendo `ensembles.ensembles_code` en voces (SSATTB → S×2, A×1, T×2, B×1), usando el catálogo `voices`. Solo procesa códigos íntegramente de símbolos de voz; idempotente (reemplaza por ensemble). `--dry-run`. |
| `normalize_ensembles.py` | Canonicaliza `ensembles.ensembles_code` y fusiona duplicados reales (mismo conjunto con distinto separador): `SATB-SATB`≡`SATB.SATB`, `SA / TB`≡`SA.TB`, `SOLO MEZZO-SOPRANO`≡`SOLO MEZZO SOPRANO`. Solo toca grupos con más de una forma; no renombra códigos únicos. `--dry-run`. Tras ejecutar: `populate_ensemble_voices.py` + reindexar CPDL. |
| `fill_language_names.py` | Rellena `languages.languages_name` desde `languages_code` (BCP-47) para las filas sin nombre (60/132). Idempotente. `--dry-run`. |
| `backfill_attribution.py` | Mueve atribuciones no-persona (anónima/tradicional/popular/atribuida) de `works.composer` a `attribution_type`+`attribution_note`. |
| `resolve_persons.py` | Pipeline de resolución: normaliza `works_person_import` (rol composer), busca por `persons_name`, `persons_aliases` y `persons_identity` (ancla), y crea las relaciones `works_person_roles` (rol 1). `--dry-run`. |
| `populate_persons_from_import.py` | Da de alta los compositores PDMX de `works_person_import` que no casan con nadie: limpia ruido/mojibake, agrupa por forma normalizada del nombre y crea persona + alias. `--roles` (def. `composer`), `--dry-run`. |
| `merge_duplicate_persons.py` | Fusiona personas duplicadas por **clave limpia de nombre** (sin acentos ni sufijos de ruido, ≥2 tokens), **no** por anclas de identidad; registra en `persons_merge_history`. `--like`, `--dry-run`. |
| `cleanup_person_duplicates.py` | Limpieza dirigida por **apellido exacto** (no subcadena): valida cada variante contra un keeper fiable y sólo fusiona los duplicados mal formados (AUTO); multi-autor y personas distintas quedan en REVIEW. Mueve a alias y repunta `works_person_roles`/`persons_aliases`/`persons_identity`/`persons_evidence`/`cpdl_edition_persons`/`representation_persons`. `--like`, `--plan-out`, `--apply` (por defecto dry-run). |
| `review_persons_ai.py` | Revisión de personas con **IA (Gemini)**: `--generate` envía lotes de nombres con esquema JSON (`is_person`, `action` keep/correct/merge/split/not_person/traditional, años, nacionalidad, ficha) y guarda la respuesta; `--apply` la ejecuta sobre `persons`/`works` (rename+alias, merge, split multi-compositor, tradicional/desconocido) con umbral de confianza, backups e historial. Requiere `GEMINI_API_KEY`. Modelo por defecto `gemini-flash-latest` con reintentos (429/503). |
| `normalize_identity_names.py` | Recalcula `persons_identity.identity_name_norm` con la clave sin acentos (iniciales + apellido), la que usan los enlazadores. Sustituye `normalize_authority_names.py` (**retirado**). |
| `mark_anonymous_attr.py` | Marca en **`works`** (no en `persons`) las obras sin rol 1 cuyo título/nota declara anonimato/tradición: `works_attr_type` (TRADICIONAL/ANONIMA/POPULAR/DESCONOCIDO). `--apply` (por defecto dry-run). |
| `mark_pseudo_persons.py` | Saca de "Compositores" las fichas que no son personas (`(trad.)`, `(Attributed to) …`, `(?)`): localiza el pseudo-autor en el rol 1 y lo retira. `--apply` (por defecto dry-run). |
| `mark_persons_difficulty.py` | Marca `persons_review_status` por **dificultad de revisión**: `not_reviewed_1` (fácil), `_2` (medio: grupos/dúos/múltiples), `_3` (difícil: mojibake/CJK). |
| `save_biographies.py` | Vuelca a `persons_biography_*` la base `BIOGRAPHIES` escrita a mano en el propio script (compositor → resumen/era/nacionalidad). **Sin argparse ni docstring de resumen** (pendiente de formalizar). |
| `clean_persons.py` | Limpieza genérica de `persons`: sanea caracteres/mojibake, extrae años `(1815-1852)`/`(*1815 †1852)` a `persons_birth_year`/`persons_death_year` y normaliza el nombre. Reglas, no casos. |
| `clean_person_names_chars.py` | Saneado de **caracteres** en `persons_name` de TODAS las personas (NFKC, controles, ancho cero, espacios colapsados, años pegados). Sin decisiones semánticas. |
| `link_works_person_import.py` | Enlaza `works_person_import` con personas **existentes** (`persons`/`persons_aliases`), normalizando y compactando el nombre; **no crea** personas. |
| `link_import_by_identity.py` | Mapa nombre normalizado → persona desde `persons_identity` para enlazar las filas pendientes de `works_person_import` **sin crear alias ni personas**. `--roles`, `--dry-run`. |
| `verify_merge_1a.py` | Verificador **read-only** del Lote 1A: estado de merges, snapshots y referencias. |
| `split_tonality_from_person.py` | Separa la tonalidad pegada al nombre (`"B minor Jeremiah Ingalls"`) y la devuelve a la obra (`works_musical_key`). |
| `refine_sin_destino.py` | Clasificador **read-only** de los `sin_destino` del mapa de identidad CSV (persona_real / duplicado_fuzzy / ambigua / no_persona / descartado). No escribe BBDD. `--identity`, `--csv`, `--md`. |
| `diagnose_haydn_person.py` | Diagnóstico **read-only** de la persona Haydn `f1f53fb0…`. |
| `correct_haydn_person.py` | Corrige la identidad de la persona Haydn `f1f53fb0…` (Joseph con nombre de Michael). **No toca obras ni atribuciones**; dry-run por defecto, `--apply`, auditable y reversible. |
| `fix_person_from_score.py` | Corrige los **roles de autoría** de una obra leyendo `<creator type="…">` del MusicXML de su recurso (separa arreglistas/intérpretes/editores pegados al compositor). |
| `candidate_resolver.py` | **(retirado)** Resolvía candidatos a Composer en `composer_candidate`. |
| `candidate_cleanup.py` | **(retirado)** Clasificaba candidatos `unknown` en `composer_candidate`. |
| `candidate_priority.py` | **(retirado)** Priorizaba candidatos por impacto en `composer_candidate`. |
| `catalog_statistics.py` | **(retirado)** Estadísticas del catálogo de la fase de identidad anterior. |
| `incorporate_candidates.py` | **(retirado)** Incorporaba candidatos de `composer_candidate` al Maestro. |
| `incorporate_resolutions.py` | **(retirado)** Materializaba `composer_identity_resolution` en el Maestro. |
| `ingest_authority.py` | **(retirado)** Ingería snapshots JSON en `authority_identifiers` (tabla eliminada). |
| `ingest_app_responses.py` | Llevar la respuesta de APP a la tabla de proveedores (simulado). |
| `load_composer_authority.py` | **(retirado)** Cargaba la autoridad de compositores en `composer_authority`. |
| `run_works_matching.py` | Pasada de matching de obras contra el Maestro Composer (storage es el escritor). |
| `test_authority_coverage.py` | **(retirado)** Probaba la cobertura de `composer_authority` sobre las primeras obras. |

### candidate_cleanup.py
Clasifica las atribuciones `unknown` de `composer_identity_resolution` en categorías
(`mojibake`, `no_persona`, `qualifier`, `real`, `review`) y persiste solo los accionables
(`real` + `review`) en `composer_candidate` (migración 027). Reusa `classify_composer_name`,
`is_mojibake` y `clean_composer_name` de osap-storage. Mojibake/no_persona/qualifier NO crean Composer.
```
python scripts/candidate_cleanup.py --db osap_storage [--db-user U] [--db-password P] \
    [--test prod-10000-001] [--dry-run]
```

> **Nota de migración (2026-09-17, ver `osap-storage/docsNew/fork-plan-migracion.md` §8)** — scripts de la
> fase de identidad anterior **retirados** (apuntaban a tablas ya inexistentes
> `composer_candidate`/`composer_identity_resolution`/`composer_authority`/`composer_identifiers`/
> `persons_authority*`/`persons_identifiers`):
> `candidate_cleanup.py`, `candidate_priority.py`, `catalog_statistics.py`,
> `incorporate_candidates.py`, `incorporate_resolutions.py`, `load_composer_authority.py`,
> `test_authority_coverage.py`, `normalize_authority_names.py`, `ingest_authority.py`.
>
> Los scripts de reconstrucción se **repuntaron** a `persons_identity`/`persons_evidence`
> (`resolve_persons.py`, `link_works_person_import.py`, `resolve_import_ai.py`, …);
> `normalize_authority_names.py` quedó obsoleto y lo sustituye `normalize_identity_names.py`.
> Las secciones detalladas de abajo para esos scripts son **legacy** y se conservan solo como
> referencia histórica.

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
| `list_providers.py` | Lista proveedores registrados en BD (`provider_id`, `name`, `wired`). |
| `check_providers.py` | Alias de `list_providers.py` para comprobaciones rápidas. |
| `enrich_provider_descriptions.py` | Reconstruye las descripciones multi-idioma de `providers` (nº de obras + formatos, sin estado de conexión). |
| `seed_missing_providers.py` | Siembra proveedores faltantes desde `providers/*/provider.yaml` en BD (usa mapping procesado; no recomendado para proveedores nuevos). |
| `reseed_providers.py` | Re-siembra proveedores desde `providers/{id}/` usando el mapping crudo de YAML. Recomendado para (re)crear `hymnary`, `iiif`, `zenodo` con su configuración completa. |
| `build_composers_index.py` | Fusionar fuentes de compositores en `composers_index.json`. |
| `confidence_report.py` | Reporte de `resolution_confidence` sobre los 30 (FASE 5.8). |
| `cross_attribution.py` | Atribución cruzada reusando la capa de proveedores (FASE 5.8). |
| `diagnose_not_found.py` | Diagnóstico de los `not_found` de la autoridad local sobre N obras. |
| `download_composers.py` | Descargar fichero de compositores desde Wikidata (SPARQL). |
| `enrich_identifiers.py` | Enriquecer identificadores de obras/compositores desde fuentes abiertas. |
| `extract_composers_from_dump.py` | Extraer compositores del dump completo de Wikidata. |
| `fichas_30.py` | Fichas de ground truth de los 30 (evidencia, procedencia, conflictos). |
| `ground_truth_30.py` | Ground truth de resolución de los 30. |
| `index_works.py` | **Indexador local de obras multi-proveedor** (paso 1 del índice): lee OMR y CPDL (osap-storage), IMSLP (Worklist API), Mutopia (make-table.cgi) y MusicBrainz (dump local) y puebla `index_works`+`index_representations`+`index_work_voicings` (osap-api) con normalización y dedupe. CPDL **sí** se indexa (su corpus ya está materializado en `works`), consumiendo el voicing de `ensembles`/`work_ensembles` (`kind='ensemble'`). Uso: `python script/index_works.py --providers omr,cpdl,imslp,mutopia,musicbrainz`. OMR construye `download_url={storage}/api/download/{file_id}` y `available=1`. MusicBrainz filtra a tipos de música artística (`--mb-types art`) por defecto. |
| `drop_cpdl_index_rows.py` | Elimina las representaciones `provider='cpdl'` del índice local y las `index_works` huérfanas (limpieza heredada de cuando CPDL era provider vivo; ya no es necesario porque CPDL se indexa, pero sigue siendo idempotente). Uso: `python script/drop_cpdl_index_rows.py`. |
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
| `predeploy_backup.ps1` | **Copia de seguridad antes de subir** (host `RemoteIA`): crea `/home/ocw/backups/<fecha>/` con dump comprimido de las 4 BBDD (`osap_api/auth/storage/support`) y tar de los 5 programas (`app`, `osap-api/auth/storage/support`, sin `.venv`). Punto de rollback. |
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

### list_providers.py
Lista los proveedores registrados en `providers` con su estado `wired`. Útil para verificar
rápidamente qué proveedores están activos en la BD.
```
PYTHONPATH=<osap-api> python list_providers.py
```

### check_providers.py
Alias práctico de `list_providers.py` con el mismo comportamiento.
```
PYTHONPATH=<osap-api> python check_providers.py
```

### enrich_provider_descriptions.py
Reconstruye la descripción multi-idioma de cada proveedor de la BD operativa a partir
de la reseña base (YAML) + datos reales del índice (nº de obras y formatos). Idempotente:
re-ejecutarlo reescribe las descripciones con datos actualizados. **No** incluye el estado
de conexión en el texto; si quedó un sufijo "conectado / no conectado" de una ejecución
antigua, basta re-ejecutarlo para limpiarlo.
```
PYTHONPATH=<osap-api> python script/enrich_provider_descriptions.py [--db-api osap_api]
```

### seed_missing_providers.py
Siembra proveedores faltantes desde `providers/*/provider.yaml`. Guarda el mapping
**procesado** (`definition.work_mapping`), que para algunos proveedores queda vacío.
No recomendado para proveedores nuevos; usar `reseed_providers.py` en su lugar.
```
PYTHONPATH=<osap-api> python seed_missing_providers.py
```

### reseed_providers.py
Re-siembra proveedores desde `providers/{id}/` tomando el mapping **crudo** de YAML
(`mapping.yaml`, `endpoints.yaml`, `resources.yaml`, `provider.yaml`). Es el script
correcto para (re)crear proveedores como `hymnary`, `iiif` o `zenodo` con su
configuración completa. Por defecto los deja en `wired=False` (preparados, no activos).
```
PYTHONPATH=<osap-api> python reseed_providers.py
```

### Otros scripts (resumen)
- **Integridad del índice**: `hash_index_representations.py` (`--limit`, `--sleep`,
  `--composer-like`/`--title-like`, `--dedupe [--apply]`) descarga cada representación una
  vez (lectura de R2/CDN con coste), guarda su **SHA-256** en
  `index_representations.content_hash` y detecta ficheros **byte-idénticos** que hoy
  aparecen como obras duplicadas; con `--apply` consolida. Reanudable (`content_hash IS NULL`).
- **Normalización de identidad del índice**: `normalize_index_identity.py`
  (`--apply`; por defecto dry-run) consolida `index_works` duplicados con el criterio
  catálogo completo + compositor + título (con marcadores de movimiento y anclaje de
  obras sin catálogo/compositor). **No** toca el agrupador en runtime.
- **Esquema vs datos del índice** (desacoplados):
  - `migrate_index_schema.py` — aplica el **DDL de esquema** idempotente (ALTER/index) una
    vez por despliegue. El arranque de la app **ya no migra** (`_init` solo crea tablas).
  - `rebuild_index.py` — **procedimiento oficial de reindexado**: `--full` (vacía las tablas
    derivadas y reindexa) o incremental (upsert); limpia huérfanos de voicing. No toca el
    esquema. Añadir ficheros = relanzar este job.
- **Resolución a persona / cierre de identidad**: `resolve_index_composers.py` resuelve
  `index_works.person_id`/`composer_name` a la persona canónica del Maestro (autoridad
  `persons`, sin variantes de orden). `finalize_index_identity.py` hace **resolución +
  fusión en un solo paso** (agrupa por `(title_key(191), person_id)` y consolida) —
  imprescindible porque reescribir el `person_id` antes de fusionar viola la clave única.
  Ambos con `--apply` (dry-run por defecto). La columna del índice es **`person_id`**
  (clave de `persons`), no `composer_id`.
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
- **Reinicio de dev**: `restart-dev.ps1` (y su lanzador `restart-dev.cmd`) mata todos los
  procesos de los servicios locales (por puerto 8000/8001/8200/8300 y por command line) y
  los vuelve a arrancar en segundo plano esperando su healthcheck; se autoeleva (UAC).
  Con `-NoWait` arranca y **devuelve el control** sin esperar healthchecks (los lanzadores
  lo usan para no colgarse). No toca Apache (osap-app). Logs en
  `%LOCALAPPDATA%\osap-dev\logs`. Lanzador de escritorio: `OSAP-Dev-Restart.cmd`.
- **Comprobar dev sin reiniciar**: `check-dev.ps1` (no bloquea) muestra, en segundos, puerto/PID y
  healthcheck de 8000/8001/8200/8300, la SPA `osap-app`, las últimas líneas de `restart.last.log`
  (con hora por fase) y los errores de cada servicio. Úsalo para saber si algo está caído/colgado.
- **Mantenimiento web**: `web/scripts/maintenance.ps1` (`-On`, `-Off`, `-Status`, y
  `-LocalOnly`/`-RemoteOnly`) activa el modo mantenimiento en local (flag en `web/dist`,
  Apache responde 503 con `maintenance.html`) y en producción (flag remoto en el root de la
  SPA, nginx vía `RemoteIA`). El bypass de revisión es `?preview=<TOKEN>` (cookie
  `osap_preview`, 1 día). El vhost nginx versionado es
  `deploy/app.openmusicrepository.com.conf` y lo despliega `script/deploy.ps1`.

---

## osap-support/scripts

### release.ps1 (raíz del repo)
Libera osap-support a producción (91.134.255.134). Corre tests/lint/mypy, sube el código por
tar+ssh a `~/openmusicrepository.com/osap-support`, asegura el venv (`pip install -e .`),
despliega `osap.production.toml` como `osap.toml`, aplica migraciones Alembic
(`upgrade head`) y reinicia `osap-support.service` verificando `/health` en 8300.
Uso: `pwsh osap-support/release.ps1 [-SkipTests] [-SkipMigrations]`

### backfill_founder.py
Backfill de reconocimientos **FOUNDER** (históricos) desde `memberships.is_founder`
(ADR-015, criterio congelado). Crea reconocimientos `historical/active` permanentes en el
proyecto canónico `ecosystem` con `origin = criterion:founder.<id>`; **idempotente** (si ya
existe el par user+ecosystem+founder se omite, nunca duplica) y con `--dry-run` para
validar sin escribir. `granted_at` = `MIN(started_at)` de las membresías founder del
usuario. Requiere la migración `0002` de osap-support (tablas de reconocimientos).
Uso: `python scripts/backfill_founder.py [--dry-run] [--criterion-id founder-2026]`
