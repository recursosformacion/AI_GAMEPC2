# Migración de esquema — Aportaciones (contributions)

**Estado:** script **preparado, NO ejecutado** (2026-10-04). No aplicar aún en Dev ni Prod.

## 1. Alcance

Crea cuatro tablas en la DB **`osap-api`** (modelo de aportación, aditivo):

1. `contributions` — la aportación (actor, operación, entidad destino, estado, revisión).
2. `contribution_relations` — relaciones declaradas (musicales | de aportación), varias por
   aportación, con su propio eje de validación.
3. `contribution_events` — histórico **append-only** (estados y relaciones; quién).
4. `contribution_artifacts` — vínculo aportación ↔ `file_id`(s) de osap-storage (1..n).

**Fuera de alcance (migración aparte):** `representation_id` en las métricas de impacto
(`download_usage`, `analytics_downloads`, `analytics_consults_daily`) y cualquier cambio en
osap-storage.

## 2. Recon del precedente

- `script/migrate_index_schema.py` es el patrón de osap-api: script lanzable que aplica
  DDL idempotente (delega en `_MysqlStore._migrate`), docstring con uso, y documentado en
  `docs/osap/scripts.md`.
- Conexión: `pymysql`, `charset=utf8mb4`, `autocommit`, `ssl_disabled` para localhost.
- Este script sigue ese estilo, pero con **`--dry-run`** y comprobaciones previa/posterior
  (el precedente no las tenía; se añaden por prudencia, ya que el DDL es nuevo).

## 3. Diseño

Ver DDL exacto en `script/migrate_contributions_schema.py` y en `_docs/aportaciones-esquema.md`.

Decisiones de esquema:
- **FKs solo dentro de osap-api**: `contribution_relations`, `contribution_events` y
  `contribution_artifacts` → `contributions(id)` con `ON DELETE RESTRICT` (no se borra la
  aportación; el histórico se conserva).
- **Sin FK cross-service**: `contribution_artifacts.file_id` (osap-storage) y
  `contribution_relations.person_id` (osap-storage) son **ids opacos** indexados, sin FK.
- **`target_id`**: id de la entidad destino en storage. Para `add_resource` es el
  **`representation_id`**. El **id de fichero NO va en `contributions`**, va en
  `contribution_artifacts` (evitar confundir destino de dominio con artefacto físico).
- **`operation`** cerrado a `create_work | add_representation | add_resource`.
- **Dos ejes de validación**: `contributions.status` (aportación) y
  `contribution_relations.validation_status` (condición musical).
- **Sin `published` en `files`** ni estado de publicación en storage (§9 del contrato).

### Índices (según los accesos de contrato / «Mi Actividad»)

| Tabla | Índice | Para qué |
|---|---|---|
| `contributions` | `(actor_user_id)` | «Mis aportaciones» |
| `contributions` | `(actor_user_id, created_at)` | actividad reciente del usuario |
| `contributions` | `(status)` | cola de revisión |
| `contributions` | `(target_kind, target_id)` | «quién aportó esto» |
| `contribution_relations` | `(contribution_id)` | leer relaciones de una aportación |
| `contribution_relations` | `(relation_kind, validation_status)` | cola de validación musical |
| `contribution_events` | `(contribution_id, created_at)` | reconstruir el histórico |
| `contribution_artifacts` | `(contribution_id)` | artefactos de una aportación |
| `contribution_artifacts` | `(file_id)` | refs de un fichero (impacto/GC) |

## 4. Invariantes

- `contributions.operation ∈ {create_work, add_representation, add_resource}`.
- `target_kind ∈ {work, representation, resource}`; en `add_resource`, `target_kind=representation`.
- `contribution_relations.relation_kind ∈ {musical, contribution}`;
  `validation_status ∈ {pending, accepted, rejected}`.
- `contribution_events`: **solo INSERT** (append-only); nunca UPDATE/DELETE.
- `contribution_artifacts`: 1..n ficheros por aportación; mismo `file_id` puede repetirse en
  aportaciones distintas (dedup por `sha256` en storage).
- `status=withdrawn` **no** borra la aportación ni sus eventos.

## 5. Ejecución (cuando se autorice) — hoy NO ejecutar

```powershell
# 1) Revisión sin tocar la BD:
PYTHONPATH=<osap-api> python script/migrate_contributions_schema.py --dry-run

# 2) Aplicar (idempotente) — solo tras autorización explícita:
PYTHONPATH=<osap-api> python script/migrate_contributions_schema.py
```

Comprobaciones que hace el script: qué tablas existían ya (se omiten), creación idempotente, y
verificación posterior (tablas presentes + nº de FKs por tabla = 1).

## 6. Rollback

- Al ser aditivo, el rollback es un `DROP TABLE` **manual** de las cuatro tablas
  (`contribution_artifacts`, `contribution_events`, `contribution_relations`, `contributions`,
  en ese orden por FK), **solo si están vacías**. No se automatiza ni se ejecuta aquí.

## 7. Verificación prevista (tras aplicar, en su caso)

- `SHOW TABLES LIKE 'contribution%'` → las cuatro.
- Conteo de FKs por tabla = 1.
- Prueba de humo: insertar una `contributions` `draft` + una `contribution_relations` y borrar
  la aportación debe **fallar** por `ON DELETE RESTRICT` (invariante de no borrado).
- Suites `ruff`/`mypy`/`pytest` sin cambios (la migración no toca código de la app todavía).

## 8. Siguiente paso (separado)

- Impacto: `representation_id` en métricas + propagación del id de representación en descarga
  (`download_usage`), en su propio cambio.
- `add_resource` end-to-end (upload API→storage) cuando se cierre el contrato de upload.
