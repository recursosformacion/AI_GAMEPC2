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

Sin cambios aplicados desde osap-api. Si en el futuro hay que tocar alguna tabla de
`osap-storage` (prod) durante una tarea de osap-api, se registra aquí **y** se reproduce en
dev con la migración equivalente de osap-storage.
