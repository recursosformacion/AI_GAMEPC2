# Registro de cambios de esquema

Cambios de esquema aplicados fuera de los repos, con su equivalente reproducible en código
para que **dev y producción converjan**. (Obligatorio para cualquier cambio en tablas de
`osap-storage`, que está en reorganización.)

## osap-api (índice local)

| Fecha | Tabla | Cambio | Reproducible en | Estado |
|---|---|---|---|---|
| 2026-09-14 | `index_representations` | `content_hash CHAR(64) NULL` + índice `idx_rep_content_hash` (SHA-256 del MusicXML) | `src/osap/infrastructure/state/op/mysql.py` (DDL + `_migrate`) y `script/hash_index_representations.py` | aplicado en prod; migración idempotente cubre dev |

Notas:
- El valor lo rellena `script/hash_index_representations.py` (lectura R2/CDN, reanudable).
- `_migrate()` añade la columna/índice si faltan, así que arrancar osap-api en dev los crea.

## osap-storage

| Fecha | Tabla | Cambio | Reproducible en | Estado |
|---|---|---|---|---|
| 2026-09-20 | `rism_sources` | Índice `FULLTEXT ft_rism_search (rism_uniform_title, rism_title, rism_composer_name)`; la búsqueda RISM pasa de `LIKE '%q%'` (full scan ~17 s) a `MATCH … AGAINST` (~0,07 s) | `osap-storage/scripts/migrate_rism_fulltext.sql` + `infrastructure/repositories/sql_rism_source_repository.py` | aplicado en dev; **pendiente de aplicar en prod** al subir storage |

Sin otros cambios aplicados desde osap-api. Si hay que tocar alguna tabla de `osap-storage`
(prod) durante una tarea de osap-api, se registra aquí **y** se reproduce en dev con la
migración equivalente de osap-storage.
