# Scripts de OSAP API

**Estado:** VIGENTE, inventario contrastado con [script/README.md](../../script/README.md).  
**Revisión:** 2026-11-24.

La fuente de verdad para saber qué scripts existen y cuáles son estables es `script/README.md`. Este documento explica su función y las precauciones operativas. No ejecutar un script solo porque aparezca en un informe histórico.

## 1. Clasificación

- **Estables / operativos:** forman parte de la aplicación, de un timer, del despliegue o de una operación recurrente. Deben tener documentación y pruebas cuando corresponda.
- **One-off:** análisis, experimentos, trazas y backfills históricos. No forman parte del ciclo normal y no deben ejecutarse automáticamente en producción.

El contenido de `script/oneoff/` es histórico. Antes de reutilizar una herramienta de esa carpeta hay que revisar su código, dependencias, alcance y destino de datos.

## 2. Índice de búsqueda

| Script | Función | Precaución |
|---|---|---|
| `index_works.py` | Construye/actualiza obras y representaciones del índice local | Puede modificar datos del índice |
| `sync_index.py` | Sincronización incremental | Verificar origen, rango y destino antes de ejecutarlo |
| `rebuild_index_safe.py` | Rebuild en shadow y merge, conservando IDs y public_id | Revisar backup, métricas y mapa de IDs antes del corte |
| `rebuild_index.py` | Upsert del índice; `--full` exige `--allow-id-change` | No usar `--full` sin plan explícito de IDs, aliases y redirects |
| `weekly_novelties.py` | Rutina de novedades y reindexado seguro | Verificar timer y última ejecución |
| `migrate_index_schema.py` | DDL idempotente del esquema del índice | Es una operación de esquema; revisar migraciones aplicadas primero |
| `finalize_index_identity.py`, `resolve_index_composers.py` | Normalización y resolución de identidad | Validar muestra, duplicados y relaciones antes de aceptar cambios |
| `backfill_source_ids.py`, `backfill_index_url_aliases.py` | Backfills de identificadores y aliases | No repetir sin comprobar idempotencia y estado previo |

## 3. Despliegue y comprobación

El inventario operativo incluye:

- `deploy.ps1`, `deploy_all.ps1`, `deploy_with_maintenance.ps1`: procedimientos de despliegue.
- Scripts de backup, comprobación y smoke test.
- `restart-dev.ps1`, `restart-dev.*` y `osap-tunnel.ps1`: desarrollo local.

La existencia de estos scripts no demuestra que fueran el mecanismo utilizado en el último despliegue. Para conocer el procedimiento efectivo hay que revisar los registros de ejecución y comprobar la aplicación pública y los servicios desplegados.

No ejecutar un script de despliegue ni un smoke test que realice escrituras sin autorización expresa. El backup debe preceder a cualquier migración o cambio de datos.

## 4. Reglas de seguridad

1. Identificar el entorno efectivo y la base de datos de destino antes de ejecutar.
2. Revisar argumentos, defaults y conexiones que el script realmente utiliza; no fiarse solo del nombre del fichero.
3. Para producción, disponer de backup verificable y plan de rollback.
4. Distinguir un rebuild en shadow de un rebuild que cambia IDs públicos.
5. No ejecutar backfills ni migraciones repetidamente sin confirmar idempotencia.
6. No usar datos ni credenciales de producción desde un entorno local con permisos de escritura.
7. Después de un cambio de índice, comprobar obras, representaciones, IDs públicos, aliases, sitemaps y rutas antiguas.
8. Registrar commit, comando exacto, entorno, resultados y cualquier escritura realizada.

## 5. Documentación relacionada

- [Inventario de scripts](../../script/README.md).
- [Entorno de desarrollo](dev-environment.md).
- [Versionado y releases](versioning.md).
- [Auditoría de asociaciones del índice](auditoria-index-2026-11-24.md).
- [Arquitectura actual](current-architecture.md).
