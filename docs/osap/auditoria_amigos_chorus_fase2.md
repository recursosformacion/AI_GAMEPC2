# Auditoría fase 2 — verificación física Amigos → Chorus (OSAP)

**Repositorio:** `osap-api` (y Chorus `0.14.0` en `D:\Proyectos\AI_OSAP\Chorus`)
**Base de datos origen (solo lectura):** `osap_api` — `127.0.0.1:3306`, usuario `osap2027`
**Fecha:** 2026-11-18
**Regla:** todo de solo lectura. No se modificaron tablas, datos, migraciones, código ni producción.

---

## 0. Resumen ejecutivo

- Se localizaron **17 tablas `amigos_*`** en `osap_api`. Ese es el número total de tablas distintas realmente encontradas.
- El script de migración `Chorus/scripts/migrate_osap_groups_articles.py` (Chorus 0.14.0) migra solo **5 de esas 17 tablas** hacia Chorus: `amigos_groups`→`groups`, `amigos_members`→`group_members`, `amigos_group_catalog`→`group_sections`, `amigos_articles` (solo `scope='group'` y `group_id NOT NULL`)→`group_articles`, `amigos_media`→`group_article_media`.
- Las otras **12 tablas no son tocadas por el script** (se quedan en OSAP por diseño de separación OSAP↔Chorus).
- `amigos_media`: **todos** los 16 registros pertenecen a un artículo (`article_id NOT NULL` + FK `ON DELETE CASCADE` a `amigos_articles`). No hay medios huérfanos. Los 16 pasan el filtro de migración (0 excluidos).
- El artículo general (`scope='general'`, 1 registro) **permanece en OSAP**; no se migra. Correcto.
- Destino Chorus 0.14.0 verificado estáticamente mediante sus migraciones MySQL (`001_schema.sql`, `003_group_articles.sql`): las columnas del script coinciden columna a columna con el esquema destino. No se conectó a la BD Chorus (no hay credenciales locales): verificación del código/migraciones solamente → marcado como "no verificable" en datos reales.

## 1. Inventario de tablas `amigos_*` (esquema real de MySQL)

`SHOW TABLES LIKE 'amigos_%'` devuelve 17 tablas. Ninguna inventada; ninguna falta.

| # | Tabla | Filas | PK | FKs (tabla→referencia) |
|---|-------|-------|----|------------------------|
| 1 | `amigos_groups` | 3 | `id` | — |
| 2 | `amigos_members` | 2 | (`group_id`,`user_id`) | `group_id`→`amigos_groups.id` |
| 3 | `amigos_articles` | 18 | `id` | `group_id`→`amigos_groups.id` |
| 4 | `amigos_media` | 16 | `id` | `article_id`→`amigos_articles.id` (CASCADE) |
| 5 | `amigos_coral_attributes` | 6 | `id` | `group_id`→`amigos_coral_details.group_id` (CASCADE) |
| 6 | `amigos_coral_details` | 2 | `group_id` | `group_id`→`amigos_groups.id` (CASCADE) |
| 7 | `amigos_group_history` | 6 | `id` | `group_id`→`amigos_groups.id` (CASCADE) |
| 8 | `amigos_group_links` | 1 | `id` | `group_id`→`amigos_groups.id` (CASCADE) |
| 9 | `amigos_group_types` | 48 | `code` | — |
| 10 | `amigos_group_catalog` | 12 | `id` | `group_id`→`amigos_groups.id` (CASCADE) |
| 11 | `amigos_section_templates` | 273 | `id` | — |
| 12 | `amigos_role_templates` | 409 | `id` | — |
| 13 | `amigos_actuaciones` | 1 | `id` | `organizer_group_id`→`amigos_groups.id` |
| 14 | `amigos_actuacion_groups` | 0 | (`actuacion_id`,`group_id`) | `actuacion_id`→`amigos_actuaciones.id` (CASCADE), `group_id`→`amigos_groups.id` |
| 15 | `amigos_authorizations` | 2 | `id` | — |
| 16 | `amigos_events` | 56 | `id` | — |
| 17 | `amigos_uploads` | 13 | `file_id` | — |

**Total tablas: 17** (coincide con el recuento real; ninguna tabla adicional ni inventada).

Columnas, tipos, valores por defecto, nulabilidad, claves e índices por tabla se detallan en el anexo (consultas `SHOW CREATE TABLE`, `DESCRIBE`, `SHOW INDEX`, `information_schema.KEY_COLUMN_USAGE`).

## 2. Contenido real de cada tabla (agregado, sin datos personales)

### `amigos_coral_attributes` (6 filas)
Multivalor normalizado por grupo: `(group_id, facet, value, position)`. Único `(group_id,facet,value)`.
- Facetas presentes: `language` (1 valor: `ca`), `place` (3 valores: sedes/recintos), `repertoire` (2 valores).
- **Nota:** el comentario de la tabla dice `'repertoire|language'`, pero existe también la faceta `place`; el comentario no describe el contenido real.
- `group_id` es FK a `amigos_coral_details` (no a `amigos_groups` directamente).

### `amigos_coral_details` (2 filas)
Ficha de coral por grupo: `foundation_date`, `dissolution_date`, `locality`, `region`, `country_code` (`ES`), `venue`, `formation_type` (`mixed` en ambas), `member_count` (20 y 30), `website`, `public_email`, `director_person_id`, `director_label`, `linked_entity`. PK = `group_id` (FK a `amigos_groups`).

### `amigos_media` (16 filas)
- `kind`: 100 % `video`. `provider`: 100 % `youtube`.
- `url`, `video_id`, `caption`, `credit`, `position` (por defecto 0), `created_at`.
- 16 artículos distintos con exactamente 1 medio cada uno. 2 artículos de los 18 no tienen medio.
- FK `article_id`→`amigos_articles.id` ON DELETE CASCADE, `NOT NULL`.

### `amigos_group_types` (48 filas)
Catálogo jerárquico `(code, parent_code, name, kind, sort_order)`. `kind` ∈ {`banda`, `coral`, `ensemble`, `grupo`, `orquesta`}. Ejemplos: `coral`→`Coral`, `coro_mixto`→`Coro Mixto (SATB)`, `orquesta_sinfonica`→`Orquesta Sinfónica`, `banda_musica`→`Banda de Música`.

### `amigos_group_history` (6 filas)
Todas son `event_type='director_join'`. Campos: `group_id`, `member_user_id`, `person_name`, `role`, `start_date`, `end_date`, `notes`. PK `id`. (No se publican `person_name` ni `notes`.)

### Plantillas de secciones y responsabilidades
- `amigos_section_templates` (273 filas): `(id, type_code, code, name, sort_order)`. `type_code` referencia los códigos de `amigos_group_types` (27 códigos distintos, 6–15 filas cada uno).
- `amigos_role_templates` (409 filas): `(id, type_code, scope, code, name, sort_order)`. `scope` ∈ {`admin`, `musical`}. 5 admin + 3–4 musical por tipo de grupo.

### `amigos_group_links` (1 fila)
`kind='instagram'`, 1 URL de red social, `position=0`. FK a `amigos_groups`.

### Otras tablas (contexto)
- `amigos_groups` (3): 2 activas (`coral`, editorial `direct`/`moderated`), 1 inactiva. Campos `admin_roles_json`, `musical_roles_json`, `join_code`, `join_code_expires_at`.
- `amigos_articles` (18): 15 `published` `group`, 1 `published` `general`, 2 `withdrawn` `group`. 1 artículo tiene `group_id NULL` (el general).
- `amigos_members` (2): 2 `admin`; 1 `active`, 1 `revoked`.
- `amigos_actuaciones` (1): `concert`, `onsite`, `scheduled`, `published`.
- `amigos_actuacion_groups` (0): sin datos.
- `amigos_authorizations` (2): scopes `blog`, `events`; `direct_publish=1`.
- `amigos_events` (56): `article_created` 17, `article_edited` 10, `article_withdrawn` 2, `coral_details_updated` 2, `editorial_mode_changed` 4, `image_uploaded` 14, `member_granted` 6, `member_revoked` 1.
- `amigos_uploads` (13): todas `image/png`.
- `amigos_group_catalog` (12): scopes `admin`/`musical`/`section` (4 cada uno), todas activas.

## 3. Verificación del script de migración (`Chorus/scripts/migrate_osap_groups_articles.py`, Chorus 0.14.0)

Contraste columna a columna origen (OSAP) → destino (Chorus).

### 3.1 `amigos_groups` → `groups` (3 registros, 3 seleccionados, 0 excluidos)
- Copiados: `id` (→`id` y `entity_id`), `name`, `slug`, `kind` (default `grupo`), `description`, `image_url`, `website`, `email`, `logo_url`, `status` (default `active`), `editorial_mode` (default `moderated`), `technical_description`, `created_by`, `created_at`, `updated_at`.
- Transformados/derivados: `timezone` = `'Europe/Madrid'` (hardcodado); `join_code` = `'LEGACY' + UPPER(SUBSTRING(id,1,6))` (el `join_code` original **no** se copia, se regenera).
- Perdidos (no se copian): `admin_roles_json`, `musical_roles_json`, `join_code` (original), `join_code_expires_at`.
- Condiciones de bloqueo: ninguna (sin `WHERE`; se migran los 3).

### 3.2 `amigos_members` → `group_members` (2 registros, 2 seleccionados, 0 excluidos)
- Copiados: `group_id`, `user_id`→`user_sub`, `admin_role_id`, `musical_role_id`, `section_id`, `created_at`→`joined_at`, `updated_at`.
- Transformados: `role` → `manager` si `admin`, si no `collaborator`; `status` → `active` si `active`, si no `revoked`.
- Perdidos: `granted_by`.
- Columnas destino no rellenadas (quedan `NULL`): `voice_code`, `voice_label`, `section`, `display_name` (no existen en origen).
- Condiciones de bloqueo: ninguna.

### 3.3 `amigos_group_catalog` → `group_sections` (12 registros, 12 seleccionados, 0 excluidos)
- Copiados: `id`, `group_id`, `code`, `name`, `scope` (default `section`), `parent_id`, `sort_order`, `active`, `created_at`, `updated_at`.
- Perdidos: ninguna. (Las plantillas `amigos_section_templates` y `amigos_role_templates` no se migran aquí; son catálogos de referencia asumidos como seed en Chorus.)
- Condiciones de bloqueo: ninguna.

### 3.4 `amigos_articles` → `group_articles` (18 existentes, 17 seleccionados, 1 excluido)
- **Filtro del script:** `WHERE scope='group' AND group_id IS NOT NULL`.
  - Seleccionados: 17 (15 `published` + 2 `withdrawn`, todos `scope=group` con `group_id`).
  - Excluidos: 1 (`scope='general'`, `group_id=NULL`) — permanece en OSAP. Correcto.
- Condición adicional: `SELECT 1 FROM groups WHERE id=group_id`; si el grupo no existe en Chorus, el artículo se **omite**. En este dataset los 3 grupos se migran primero, así que 0 omitidos por grupo ausente.
- Copiados: `id`→`id` y `legacy_id`, `group_id`, `title`, `slug`, `summary`, `body`, `cover_url`, `event_date` (→`VARCHAR`), `status`, `author_user_id`, `reviewed_by`→`publisher_user_id` **y** `reviewed_by`, `reviewed_at`, `review_note`, `published_at`, `created_at`, `updated_at`.
- Perdidos: `scope` (es el filtro; en destino siempre implícito `group`).
- Columnas destino no en origen: ninguna relevante.

### 3.5 `amigos_media` → `group_article_media` (16 registros, 16 seleccionados, 0 excluidos)
- **Verificación clave:** `amigos_media.article_id` es `NOT NULL` con FK a `amigos_articles.id` (ON DELETE CASCADE). **Todo medio pertenece a un artículo.** Consulta de huérfanos: 0 resultados. No existen medios que no pertenezcan a artículos.
- Condición del script: `SELECT 1 FROM group_articles WHERE id=article_id`; medios de artículos no migrados se excluyen. Consulta de medios cuyo artículo no esté en el conjunto migrado (`scope='group' AND group_id NOT NULL`): 0 resultados. **Los 16 medios se migran.**
- Copiados: `id`→`legacy_id` (y `id='legacy-'+legacy_id`), `article_id`, `kind`, `url`, `provider`, `video_id`, `caption`, `credit`, `position`.
- Perdidos: `created_at` (se reemplaza por el sello de migración `stamp`, no se conserva el original).
- Condiciones de bloqueo: medio cuyo artículo no exista en `group_articles` (no ocurre aquí).

### 3.6 Tablas NO migradas por el script (quedan en OSAP)
| Tabla | Filas | Motivo |
|-------|-------|--------|
| `amigos_actuaciones` | 1 | Eventos se mantienen en OSAP (separación) |
| `amigos_actuacion_groups` | 0 | Idem (sin datos) |
| `amigos_authorizations` | 2 | No migradas |
| `amigos_coral_attributes` | 6 | No migradas |
| `amigos_coral_details` | 2 | No migradas |
| `amigos_events` | 56 | No migradas |
| `amigos_group_history` | 6 | No migradas |
| `amigos_group_links` | 1 | No migradas |
| `amigos_group_types` | 48 | No migradas (catálogo de referencia) |
| `amigos_section_templates` | 273 | No migradas (catálogo de referencia) |
| `amigos_role_templates` | 409 | No migradas (catálogo de referencia) |
| `amigos_uploads` | 13 | No migradas (ficheros se mantienen en OSAP) |

### 3.7 Campos que se pierden en la migración (resumen)
- `amigos_groups`: `admin_roles_json`, `musical_roles_json`, `join_code` (original), `join_code_expires_at`.
- `amigos_members`: `granted_by`.
- `amigos_articles`: `scope`.
- `amigos_media`: `created_at` (sobreescrito por sello de migración).
- Tablas no migradas: todos sus campos se pierden para Chorus (quedan en OSAP).

## 4. Verificación de Chorus 0.14.0

**Versión confirmada:** `ai-chorus 0.14.0` (`Chorus/pyproject.toml`).

**Esquema destino (migraciones MySQL, lectura estática):**
- `migrations/mysql/001_schema.sql`: crea `groups` y `group_members` (entre otras).
- `migrations/mysql/003_group_articles.sql`: añade columnas a `groups` (`slug`, `kind`, `description`, `image_url`, `website`, `email`, `logo_url`, `status`, `editorial_mode`, `technical_description`) y crea `group_sections`, `group_articles`, `group_article_media`.

**Coincidencia columnas script ↔ esquema destino:** verificada columna a columna para `groups`, `group_members`, `group_sections`, `group_articles`, `group_article_media`. El script no inserta columnas que no existan, y cubre todas las columnas NOT NULL del destino (con valores por defecto o derivados). Las columnas destino `voice_code`, `voice_label`, `section`, `display_name` (`group_members`) quedan `NULL` (no hay origen en OSAP).

**Fechas como VARCHAR:** en Chorus 0.14.0 las fechas/timestamps se guardan como `VARCHAR(64)`; el script convierte `datetime`/`date` de OSAP a `str(...)`. Coherente con el esquema destino.

**No verificable en datos reales:** no hay credenciales ni acceso local a la BD Chorus (`osap_chorus`), y el trabajo es de solo lectura. La verificación se limita al código del script y a los ficheros de migración de Chorus 0.14.0. No se ha ejecutado el script contra ninguna base de datos.

## 5. Revisión de conclusiones y corrección de contradicciones

- **Número total de tablas = 17**, coincidente con las tablas `amigos_*` realmente encontradas. No se infla ni se reduce.
- La migración **no es completa**: migra 5 tablas (grupos, miembros, secciones/catálogo, artículos de grupo, medios) y deja 12 tablas sin migrar en OSAP. Clasificarla como "completa" sería incorrecto.
- `amigos_media` **no contiene medios ajenos a artículos** (FK + NOT NULL); y **ningún registro de medio queda excluido** (16/16 migrados). Cualquier informe previo que diga lo contrario es incorrecto.
- El artículo general (`scope='general'`) **permanece correctamente en OSAP** y no se migra. Correcto.
- Distinción de estado (categorías exigidas):

| Categoría | Tablas / registros | Detalle |
|-----------|--------------------|---------|
| Migrado y verificado | `amigos_groups`(3), `amigos_members`(2), `amigos_group_catalog`(12), `amigos_articles` scope=group(17), `amigos_media`(16) | Origen inspeccionado, script leído, destino contrastado con migraciones Chorus 0.14.0. Datos reales de Chorus no accesibles (no verificable en destino). |
| Migrado parcialmente | `amigos_articles` (1 general excluido), `amigos_media` (`created_at` perdido) | Parte de los registros/campos no viaja. |
| No migrado | `amigos_actuaciones`, `amigos_actuacion_groups`, `amigos_authorizations`, `amigos_coral_attributes`, `amigos_coral_details`, `amigos_events`, `amigos_group_history`, `amigos_group_links`, `amigos_group_types`, `amigos_section_templates`, `amigos_role_templates`, `amigos_uploads` | Quedan en OSAP por diseño de separación; el script no las toca. |
| Sin datos | `amigos_actuacion_groups` (0 filas) | Tabla existe, sin registros. |
| No verificable | Destino Chorus BD (`osap_chorus`) | Sin credenciales/acceso local; solo verificación estática de migraciones y script. |

## 6. Conclusión

La verificación física confirma la estructura y el contenido real de las 17 tablas `amigos_*` de OSAP. El script de migración de Chorus 0.14.0 migra correctamente grupos, miembros, catálogo de secciones, artículos de grupo (`scope='group'`) y medios, respetando los filtros documentados (no migra el artículo general; omite artículos sin grupo en Chorus; omite medios de artículos no migrados). No hay medios huérfanos y todos los 16 medios son elegibles. Doce tablas de OSAP permanecen sin migrar por diseño de la separación OSAP↔Chorus, por lo que la migración es **parcial, no completa**. El destino Chorus 0.14.0 coincide a nivel de columnas con el script, pero no se pudo comprobar contra datos reales de Chorus (sin acceso de solo lectura a esa BD).

---

## Anexo — consultas SQL utilizadas y resultados (sin datos personales)

Todas ejecutadas contra `osap_api` con conexión de solo lectura (`SELECT`/`SHOW`/`DESCRIBE` únicamente). No se modificó nada.

### A.1 Listado de tablas
```sql
SHOW TABLES LIKE 'amigos_%';
```
Resultado: 17 tablas (sección 1).

### A.2 Esquema completo (por tabla)
```sql
SHOW CREATE TABLE <tabla>;
DESCRIBE <tabla>;
SHOW INDEX FROM <tabla>;
SELECT CONSTRAINT_NAME, COLUMN_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
FROM information_schema.KEY_COLUMN_USAGE
WHERE TABLE_SCHEMA='osap_api' AND TABLE_NAME='<tabla>' AND REFERENCED_TABLE_NAME IS NOT NULL
ORDER BY CONSTRAINT_NAME, ORDINAL_POSITION;
```
Resultado: guardado en `create_<tabla>.txt` (columnas, tipos, default, Null, PK, índices, FKs). Ver ficheros del anexo.

### A.3 Recuentos
```sql
SELECT COUNT(*) FROM <tabla>;
```
Resultado (sección 1): 17 tablas con sus filas (3, 2, 18, 16, 6, 2, 56, 12, 6, 1, 48, 3, 16, 2, 409, 273, 13, 1, 0).

### A.4 Distribuciones de contenido (agregadas)
```sql
SELECT kind,status,editorial_mode,COUNT(*) FROM amigos_groups GROUP BY 1,2,3;
SELECT status,scope,COUNT(*) FROM amigos_articles GROUP BY 1,2;
SELECT kind,COUNT(*),GROUP_CONCAT(DISTINCT provider) FROM amigos_media GROUP BY kind;
SELECT facet,COUNT(*),GROUP_CONCAT(DISTINCT value) FROM amigos_coral_attributes GROUP BY facet;
SELECT event_type,COUNT(*) FROM amigos_group_history GROUP BY event_type;
SELECT type_code,COUNT(*) FROM amigos_section_templates GROUP BY type_code;
SELECT type_code,scope,COUNT(*) FROM amigos_role_templates GROUP BY type_code,scope;
SELECT kind,modality,event_status,editorial_status,COUNT(*) FROM amigos_actuaciones GROUP BY 1,2,3,4;
SELECT event_type,COUNT(*) FROM amigos_events GROUP BY event_type;
SELECT scope,COUNT(*),SUM(active) FROM amigos_group_catalog GROUP BY scope;
```
Resultados: sección 2 (sin nombres, emails ni datos personales).

### A.5 Verificación amigos_media (clave)
```sql
-- Medios huérfanos (debería ser 0 por FK)
SELECT m.id, m.article_id FROM amigos_media m
LEFT JOIN amigos_articles a ON a.id=m.article_id WHERE a.id IS NULL;
-- Resultado: 0 filas.

-- Medios cuyo artículo NO está en el conjunto migrado (scope='group' AND group_id NOT NULL)
SELECT m.id, m.article_id, a.scope, a.group_id FROM amigos_media m
LEFT JOIN amigos_articles a ON a.id=m.article_id
WHERE NOT (a.scope='group' AND a.group_id IS NOT NULL);
-- Resultado: 0 filas (los 16 medios son elegibles).

-- Artículos sin medio
SELECT a.id, a.scope, a.group_id, a.status FROM amigos_articles a
LEFT JOIN amigos_media m ON m.article_id=a.id WHERE m.id IS NULL;
-- Resultado: 2 filas (1 scope='general' group_id NULL, 1 scope='group' publicado).
```

### A.6 Artículo general (permanece en OSAP)
```sql
SELECT id, slug, scope, group_id, status FROM amigos_articles WHERE scope='general';
-- Resultado: 1 fila, scope='general', group_id NULL (no migrado).
```

### A.7 Código Chorus 0.14.0 inspeccionado (estático)
- `Chorus/pyproject.toml` → versión `0.14.0`.
- `Chorus/migrations/mysql/001_schema.sql` → `groups`, `group_members`.
- `Chorus/migrations/mysql/003_group_articles.sql` → `group_sections`, `group_articles`, `group_article_media` (+ columnas de `groups`).
- `Chorus/scripts/migrate_osap_groups_articles.py` → script de migración leído y contrastado (sección 3).

--- 
Fin del informe. Todo el trabajo fue de solo lectura; no se eliminó ni renombró tabla alguna.
