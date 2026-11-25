# Scripts de osap-api

Esta carpeta se divide por **frecuencia de uso**. La regla es simple:

- **Estables**: los usa la aplicación, el despliegue, un timer o una operación recurrente.
  Deben mantenerse, documentarse en `docs/osap/scripts.md` y tener pruebas cuando aplique.
- **One-off** (`oneoff/`): análisis, experimentos, backfills históricos y utilidades de una
  ejecución. No forman parte del ciclo normal; si se vuelven recurrentes, se promocionan a
  `script/` con docstring, documentación y prueba.

## Estables / operativos

| Script | Uso |
|---|---|
| `index_works.py` | Indexador base; lo invocan el sync y el rebuild seguro. |
| `sync_index.py` | Sincronización incremental programada. |
| `rebuild_index_safe.py` | Rebuild shadow + merge; conserva IDs y `public_id`. |
| `rebuild_index.py` | Upsert incremental. `--full` exige `--allow-id-change`. |
| `weekly_novelties.py` | Rutina semanal; reindexa con el rebuild seguro. |
| `migrate_index_schema.py` | DDL idempotente del índice. |
| `finalize_index_identity.py`, `resolve_index_composers.py` | Identidad del índice. |
| `audit_index_associations.py` | Diagnóstico SQL de solo lectura de números de obra incompatibles en una Work. |
| `repair_index_split_pieltain.py`, `test_repair_index_split_pieltain.ps1` | Split No.1/No.3 de Pieltain: reparación dirigida y prueba en dev (conserva IDs/aliases de la No.3). |
| `export_api_schema_inventory.py` | Exporta tablas, columnas, índices y claves foráneas desde information_schema, solo lectura. |
| `indexnow.py`, `notify.py` | Avisos posteriores al reindexado. |
| `backfill_source_ids.py`, `backfill_index_url_aliases.py` | Backfills de la migración de IDs. |
| `deploy.ps1`, `deploy_all.ps1`, `deploy_with_maintenance.ps1` | Despliegue. |
| `deploy_ads.ps1`, `deploy_blog.ps1` | Despliegue de `ai_publicidad` y `osap-blog` con verificación del handoff POST. |
| `backup`, `check-*`, `smoke-*` | Verificación y operación. |
| `maintenance.html`, `restart-dev.*`, `osap-tunnel.ps1` | Desarrollo local. |

## One-off

`script/oneoff/` contiene evaluaciones, muestras, trazas y scripts retirados. No se referencia
desde servicios, timers ni código de producción. No añadir aquí nada que use la aplicación
en tiempo de ejecución.
