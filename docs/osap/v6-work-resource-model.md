# V6 — Replanteo Work / Resource / File

Documento de planificación. **No implementado.** V6 es un cambio de modelo y de contratos, por
tanto **A (major)**: antes de empezar exige punto de control (tag de la línea actual + rama de
mantenimiento) y no se mezcla con entregas B/C.

## Problema actual

Hoy conviven **tres representaciones del mismo concepto**:

1. `osap-storage`: `works` + `work_genres`/`work_ensembles`/`work_instruments`/`work_language`
   y `resources`/`files`.
2. `osap-api` (índice): `index_works` + `index_representations` + `genres`.
3. La ficha pública mezcla ambos: datos del índice (`/works/public/<id>`) y datos ricos de
   storage (`/details`), con IDs distintos (`index-*`, `work-*`, `file_id`, `resource_id`).

Consecuencias: campos duplicados, sincronización implícita, `download_url` con host del
entorno, joins distintos según la pantalla y dificultad para saber qué dato manda.

## Modelo propuesto: dos entidades + el objeto físico

### 1. Work (obra intelectual)

- `work_id` estable (UUID), independiente del proveedor y del índice.
- Título, subtítulo, compositor(es) por rol, catálogo/opus, año, tonalidad.
- Géneros, época, descripción. Atribución: pendiente de definir.
- Instrumentación, ensembles e idioma pasan a **Resource**.
- Duración/compases: a decidir si Work o Resource.
- Campos de obra que no cambian entre ediciones: duración/compases si son de la obra, no de
  una edición concreta.
- Estadísticas agregadas de la obra.

### 2. Resource (representación/edición concreta)

- `resource_id` estable, `work_id` FK.
- Proveedor, `provider_resource_id`, formato, URL pública o referencia de fichero.
- Licencia y notas de atribución **si varían por recurso**.
- Voz/ensemble/plantilla de esa representación si es específica.
- Páginas, partes, calidad/confianza, disponibilidad.
- Un Work puede tener N Resources.

### 3. File (objeto en R2/CDN)

- `file_id`, `resource_id`, clave en R2, MIME, bytes, checksum, fecha.
- Solo almacenamiento; no se expone como nivel editorial.

El **índice** (`index_works`/`index_representations`) deja de ser una tercera fuente: pasa a
ser una **proyección reconstruible** para búsqueda/SEO, con `work_id` y `resource_id` como
claves, no IDs sintéticos `index-*`.

## Reparto de campos (borrador para discutir)

| Campo | Work | Resource | File |
|---|---|---|---|
| título/subtítulo | sí | — | — |
| compositor/roles | sí | — | — |
| catálogo/opus/año | sí | — | — |
| tonalidad/época | sí | — | — |
| géneros | sí | — | — |
| instrumentación/ensembles/idioma | — | sí | — |
| descripción/atribución | sí | notas si son de la fuente | — |
| duración/compases | sí (si son de la obra) | si la edición difiere | — |
| páginas/partes | — | sí | — |
| licencia | por defecto de la obra | puede sobrescribir | — |
| proveedor/id de proveedor/URL | — | sí | — |
| formato/calidad/disponibilidad | — | sí | — |
| voz/ensemble de la representación | — | sí | — |
| R2 key/MIME/bytes/checksum | — | — | sí |
| estadísticas | agregadas | por resource | — |

## Identidad y URLs

- Un único `work_id` público; se elimina `index-*` como identificador de obra.
- `/obras/<work_id>/<slug>` (ficha) y `/representacion/<resource_id>`.
- Los `provider_resource_id` se guardan en una tabla de correspondencia
  (`provider`, `provider_resource_id`, `resource_id`) para reimportaciones idempotentes.
- `download_url` deja de guardarse absoluta: `file_id`/clave R2 + base de storage en config.

## Migración (fase crítica)

1. Congelar el modelo actual y hacer backup.
2. Crear `work`/`resource`/`file` canónicos en storage.
3. Mapear `index_representations` a `resource` por `(provider, provider_resource_id)`.
4. Mapear `index_works` a `work` por **evidencia fuerte** (resource ya asociado; si no,
   título+compositor exactos y revisión). No fusionar por parecido débil.
5. Revisar colisiones (misma obra en varios proveedores, arreglos, anónimos).
6. Reconstruir el índice como proyección; conservar el anterior para rollback.
7. Cambiar API/UI; mantener endpoints antiguos como adaptadores durante la transición.

## Preguntas para cerrar antes de implementar

- ¿`osap-storage` es la fuente de verdad y el índice solo proyección? (recomendado).
- ¿Dos niveles editoriales (Work + Resource) y File como detalle técnico? ¿O hace falta un
  nivel intermedio de “expresión” para arreglos/versiones?
- ¿Licencia y atribución a nivel Work, Resource o ambos con herencia?
- ¿Duración/compases son de la obra o de la edición?
- ¿Se mantiene `work-genres` normalizado o se pasa a JSON de campos?
- Estrategia de IDs públicos y redirecciones desde `index-*`.
- Ventana de migración y tolerancia a pérdida temporal de búsqueda/SEO.

## Entrega V6 (propuesta)

- Esquema nuevo + migración + reconciliación.
- API v6 (`/works`, `/resources`, `/files`) con adaptadores de compatibilidad.
- Índice como proyección; reindexación reproducible.
- Ficha HTML/React: campos de Work + lista de Resources; sin `/details` mezclado.
- Búsqueda por Work, filtros por Resource.
- Tests de identidad, correspondencia y no-duplicación; rollback documentado.
