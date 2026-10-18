# Recursos aportados por usuarios — diseño (propuesta, 2026-10-18)

> Estado: **propuesta pendiente de decisión**. No implementado.
> Preguntas abiertas al final del documento.

## Objetivo

Que los usuarios puedan aportar **recursos** (partituras, PDF, MIDI, imágenes…) al repositorio,
con tres niveles de audiencia: públicos, privados y visibles para un grupo. Los ficheros se
guardan en la **misma VPS** por coste, sin cerrar la puerta a un object storage (S3/Wasabi)
más adelante.

## Lo que ya existe (reutilizar)

- `works → representations → resources`: `works_resources` tiene `work_id`,
  `representation_id`, `type`, `relative_path`, `file_id`, `status`, `archive_id`.
- Storage separa **fichero físico** (`files` + `storage_locations(provider, object_key)`) del
  **recurso lógico**.
- Pipeline de aportaciones en osap-api: `POST /api/v1/contributions` (draft) →
  `POST /api/v1/contributions/{id}/upload` (a storage, privado) →
  `POST /api/v1/contributions/{id}/submit` → `POST /api/v1/contributions/{id}/review`
  (`accept`) → materializa `create_resource(...)`.
- No existe interfaz (UI) de aportaciones ni columnas de visibilidad/propiedad.

## 1. Modelo de datos (migración aditiva en `works_resources`)

| Campo | Tipo | Uso |
|---|---|---|
| `owner_user_id` | CHAR(36) NULL | autor de la aportación |
| `visibility` | ENUM('public','unlisted','group','private') DEFAULT 'private' | audiencia |
| `access_group_id` | CHAR(32) NULL | grupo con acceso cuando `visibility='group'` |
| `license` | VARCHAR(64) NULL | licencia del contenido |
| `attribution` | VARCHAR(255) NULL | atribución requerida (p. ej. CPDL, editor) |
| `origin_source` | VARCHAR(64) NULL | `cpdl`, `imslp`, `omr`, `user`… |
| `origin_id` | VARCHAR(128) NULL | id en el origen (nº de edición, etc.) |

**Separación de ejes**: `status` = flujo editorial (`draft/submitted/published/rejected`);
`visibility` = quién lo ve. Un recurso aprobado puede seguir siendo privado o de grupo.

Para varios grupos por recurso (futuro): tabla puente `resource_access(resource_id, group_id)`.
Para el MVP basta `access_group_id`.

> Nota operativa: el usuario de BD de la app **no tiene ALTER**; la migración se aplica como
> root (`sudo mysql`), como ya está documentado en `docs/osap/amigos.md`.

## 2. Almacenamiento en la VPS

Fuera del directorio de despliegue (el deploy rota releases y borra `assets`):

```
/srv/osap-storage/files/ab/cd/<sha256>   # content-addressed, 2 niveles
/srv/osap-storage/tmp/                   # subidas en curso
```

- **Nombre = sha256 del contenido**: deduplicación automática, integridad verificable y
  renombrados sin tocar disco. El nombre lógico vive en `works_resources.relative_path`.
- Nunca se sirve el directorio: **solo API con comprobación de permisos**.
- Los recursos privados **no** van al bucket público (`serve_directly: true` en producción).
- Monitorizar espacio y aplicar **cuota**; backups por `rsync`/`restic` (el direccionamiento por
  contenido hace los incrementales eficientes).
- Migración futura a S3: cambiar `provider` en `storage_locations`; el modelo no cambia.

## 3. Servido con permisos

Endpoint único, p. ej. `GET /api/v1/resources/{id}/content[?view=1]`:

- `public` / `unlisted` → stream o redirección a URL firmada; caché permitida si el nombre es
  hasheado.
- `private` → solo `owner` o admin.
- `group` → miembro del grupo o admin.
- `Cache-Control: private, no-store` en los no públicos.
- **Nunca** exponer `object_key` en URLs.

El visor (`/viewer?rep=…`) y el botón Descargar usan ese endpoint: un único punto de control
de acceso.

## 4. Flujo de aportación

1. `POST /contributions` → borrador con `visibility` solicitada, `license`, `attribution` y
   origen.
2. `POST /contributions/{id}/upload` → bytes a storage (privado).
3. `POST /contributions/{id}/submit`.
4. Admin acepta → recurso publicado con la visibilidad validada. El contribuidor puede pedir
   `group`/`private`; **nunca** `public` directo salvo grupo de confianza.

Controles mínimos: 25 MB por fichero, MIME permitido (pdf, mxl, musicxml, mid, imágenes),
cuota por usuario, rate limit, verificación sha256 y **ClamAV** para subidas de usuarios.

## 5. Fases

| Fase | Contenido | Esfuerzo |
|---|---|---|
| F1 | Columnas nuevas, almacenamiento content-addressed, endpoint con ACL, importación solo-admin | 1-2 días |
| F2 | UI de aportación, «Mis aportaciones», cola de revisión admin, cuotas/límites, ClamAV | 2-3 días |
| F3 | Varios grupos por recurso, URLs firmadas, migración a S3 | después |

## 6. Decisiones pendientes

1. **Grupos**: ¿reutilizar los corales de «Los amigos» como grupos de acceso o crear grupos
   genéricos?
2. **Visibilidad por defecto**: `private` hasta aprobación (recomendado) o `group` si el usuario
   pertenece a un grupo.
3. **Límites**: ¿25 MB y cuota por usuario? ¿ClamAV desde el principio?
