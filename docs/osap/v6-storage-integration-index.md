# Integración OSAP-API con OSAP Storage V6

> **Estado:** especificación de impacto y checklist previo a implementación.  
> **Fecha:** 2026-10-30.  
> **Modelo objetivo:** `Work → Resource → File`.  
> **No implica que el código ni las bases de datos estén migrados.**

La especificación conjunta y el plan de corte exhaustivo se mantienen en [AI_osap-storage: V6 reconstruction, API, index and cutover](https://github.com/recursosformacion/AI_osap-storage/blob/main/docs/v6-reconstruction-api-index-cutover.md). Este documento recoge específicamente el impacto dentro de AI_GAMEPC2 para que los cambios de osap-storage no se realicen sin adaptar y validar sus consumidores.

## 1. Decisiones que debe respetar OSAP-API

1. El modelo de Storage es Work → Resource → File.
2. Representation deja de existir en V6. No se debe reintroducir en el consumidor como nivel obligatorio ni como sustituto nominal.
3. Resource pertenece directamente a Work.
4. Un Resource puede no tener Files (URL externa/inventario pendiente) o tener varios Files (formatos distintos).
5. File es un objeto físico individual perteneciente a un Resource.
6. SHA-256 es integridad, no identidad ni deduplicación.
7. Los punteros Cloudflare R2 permanecen intactos; OSAP-API no debe conocer ni construir claves R2.
8. La descarga se resuelve mediante el enlace que devuelve Storage. El cliente no debe inferir si un ID es Work, Resource o File.
9. Work se indexa aunque no tenga archivos descargables.
10. El índice de búsqueda es una proyección derivada reconstruible, no el catálogo maestro ni un inventario de objetos R2.

## 2. Superficies actuales identificadas

### 2.1 Proveedor OMR

- `src/osap/infrastructure/providers/fetchers/omr_fetcher.py` implementa `OmrStorageFetcher`.
- Actualmente consume `GET /api/search?q=...` y normaliza `works[].resources[].links.download`.
- Conserva Works sin material descargable, pero usa solo el primer Resource al construir el resultado normalizado.
- El ID remoto se obtiene de `record.id`, con fallback a `file_id` o a un hash de ruta/URL.
- `providers/omr/endpoints.yaml` declara `/api/v1/search`, mientras que el fetcher llama `/api/search`. Esta diferencia debe resolverse al definir el contrato V6.
- `providers/omr/mapping.yaml` y los transforms deben revisarse para eliminar rutas que esperen la estructura antigua.

### 2.2 Índice local

- `script/rebuild_index.py` orquesta el rebuild.
- `script/index_works.py` contiene la lectura y normalización de proveedores.
- `script/resolve_index_composers.py` resuelve compositor/person_id contra `persons` y `persons_aliases` de osap-storage.
- `script/sync_index.py` mantiene los cursores incrementales en `sync_state`.

El rebuild full actual trunca `index_works`, `index_representations` e `index_work_voicings`, luego indexa proveedores y limpia voicings huérfanos. La tabla `index_representations` es una dependencia que debe desaparecer o transformarse explícitamente: no puede seguir presentándose como índice de una entidad que V6 elimina.

### 2.3 Recursos y resolución

Revisar todas las referencias a Representation/representations en:
- `src/osap/application/representation_identity.py`;
- `src/osap/application/representation_selector.py`;
- `src/osap/application/resource_resolver.py`;
- `src/osap/domain/candidate_representation.py`;
- `src/osap/api/templates/representation.html`;
- `src/osap/api/http/omr.py` y contratos asociados;
- provider definitions, mapping/transforms y tests;
- flujos de adquisición, selección, descarga y presentación.

No todas las clases llamadas Representation tienen por qué corresponder al concepto de dominio retirado de Storage: debe inspeccionarse cada uso y decidir si modela Resource V6, una candidatura de matching, una agrupación de resultados de proveedores o una abstracción de interfaz. No se debe hacer un renombrado mecánico.

## 3. Diseño del adaptador OMR V6

El fetcher debe consumir un contrato versionado que identifique inequívocamente:

- Work: `id`, título, compositor/persona canónica, catálogo, alias y metadatos.
- Resource: `id`, tipo, origen/procedencia, licencia y características del material.
- File: identificador si es necesario, formato, MIME, tamaño/estado y enlace de descarga generado por Storage.
- Resource externo sin File: URL externa explícita y estado que no se confunda con un File alojado.
- Work sin Resources: resultado válido.

El adaptador no debe:
- elegir silenciosamente solo el primer Resource si hay varios;
- tratar File ID como si fuera Work ID;
- inventar un ID mediante hash de URL/ruta cuando el contrato debe proporcionar un ID estable;
- deducir la disponibilidad a partir de la mera presencia de un ID;
- construir URL física o de R2;
- descartar Work porque no tenga File.

La política para exponer múltiples Files debe preservar los formatos relevantes y dejar que el consumidor seleccione según el uso (visualización, edición, descarga, audio, etc.). La selección del File preferido y el contrato de descarga se deben cerrar conjuntamente con osap-storage.

## 4. Reconstrucción del índice V6

### 4.1 Separación de catálogo e índice

El índice debe continuar almacenando datos derivados para localizar Works y resolver identidades. No debe convertirse en una copia de la estructura de almacenamiento ni depender de File IDs para identificar obras.

La existencia de Resource/File es una característica adicional de la Work, no el criterio para indexarla. Deben indexarse también:
- Works con cero Resources;
- Works con Resources URL-only;
- Works con Resources cuyos Files están pendientes o temporalmente no disponibles.

### 4.2 Tablas derivadas

Antes de modificar el esquema del índice, inventariar sus lectores y escritores. El rebuild actual referencia:
- `index_works`;
- `index_representations`;
- `index_work_voicings`.

Decidir y documentar el destino de `index_representations`:
- eliminarla si no existe una consulta real que necesite índice de materiales;
- o sustituirla por una tabla explícita de Resources, si la búsqueda/selección necesita indexar materiales.

No dejar una tabla con semántica Representation solo por compatibilidad histórica. Si se crea `index_resources`, definir clave, cardinalidad, campos y estrategia de rebuild; una Work con varios Resources no debe duplicarse en `index_works`.

### 4.3 OMR y CPDL

Los iteradores de OMR y CPDL deben leer Works y relaciones de personas desde el modelo V6. Deben dejar de depender de:
- `representations`;
- `representation_id`;
- relaciones de editores ligadas a Representation sin migrar;
- IDs de File utilizados como identificadores del material;
- rutas de descarga construidas según la estructura antigua.

La información que antes estaba en Representation (procedencia, origen externo, licencia, editores, edición, arreglo, tipo) debe leerse de Resource cuando describa el material. La información de identidad, autoría principal y clasificación de la obra debe leerse de Work y sus relaciones.

### 4.4 Personas y voicing

La resolución canónica de compositores debe seguir usando la autoridad de personas de Storage, pero contra el esquema V6. Comprobar:
- roles de compositor y sus IDs/semántica;
- aliases y normalización;
- personas fusionadas;
- IDs estables;
- Works sin compositor resuelto;
- atribuciones anónimas/tradicionales sin crear personas ficticias.

El voicing debe proceder de las relaciones normalizadas de Work con ensembles/voices. No debe depender de Representation. `index_work_voicings` debe reconstruirse de manera completa y limpiar huérfanos tras indexar Works.

### 4.5 Cursores incrementales

`script/sync_index.py` usa:
- `index.imslp.start`;
- `index.omr.last_work_id`;
- `index.mutopia.start_at`;
- `index.cpdl.last_work_id`.

Después de la reconstrucción V6:
- si los IDs de Work se conservan, validar los cursores frente al máximo ID procesado;
- si cambian, reiniciar OMR/CPDL de forma controlada o aplicar la tabla de correspondencias;
- no copiar valores de `sync_state` sin comprobarlos;
- ejecutar rebuild full antes de habilitar incremental;
- comprobar idempotencia ejecutando dos veces una sincronización;
- no ejecutar full e incremental simultáneamente.

## 5. Contrato y despliegue coordinados

El contrato actual de Storage está documentado como Provider API v1.3, pero hay divergencias entre documentación, `api/routes/provider.py`, `api/schemas.py`, `endpoints.yaml` y el fetcher. V6 debe tener un contrato nuevo y único.

Checklist:
- [ ] definir DTO Work/Resource/File;
- [ ] definir endpoint de búsqueda y detalle;
- [ ] definir endpoint y semántica de descarga sin IDs ambiguos;
- [ ] definir URL externa y Resource sin File;
- [ ] definir múltiples Files y selección de formato;
- [ ] definir auth/scopes y errores;
- [ ] actualizar `OmrStorageFetcher`;
- [ ] actualizar `providers/omr/endpoints.yaml`, mapping y transforms;
- [ ] actualizar tests unitarios del fetcher;
- [ ] probar con instancia osap-storage V6 y base `storage_new`;
- [ ] desplegar Storage y consumidor coordinadamente;
- [ ] comprobar contrato/version al inicio del servicio o en smoke tests.

No desplegar Storage V6 mientras el consumidor de producción siga esperando el DTO anterior, ni desplegar el fetcher V6 contra el contrato V5.

## 6. Checklist del rebuild y aceptación

- [ ] snapshot congelado de Storage V5 disponible;
- [ ] transformación a V6 repetible;
- [ ] recuentos de Work/Resource/File conciliados;
- [ ] punteros R2 conservados sin mutaciones físicas;
- [ ] no existen joins a Representation en las consultas V6;
- [ ] no existen referencias a StorageLocation/StorageProvider como entidades de dominio;
- [ ] `index_representations` resuelta explícitamente;
- [ ] rebuild full completo desde Storage V6;
- [ ] compositores/person_id resueltos;
- [ ] voicings completos;
- [ ] Works sin File presentes en el índice;
- [ ] Resources múltiples sin duplicar Works;
- [ ] sincronización incremental idempotente;
- [ ] búsqueda y resolución OSAP probadas;
- [ ] descargas resueltas por Resource y sin exponer claves físicas;
- [ ] importadores permanecen suspendidos hasta la aceptación formal.

## 7. Referencias de la especificación conjunta

- [OSAP Storage V6 — reconstrucción, API, índice e implantación](https://github.com/recursosformacion/AI_osap-storage/blob/main/docs/v6-reconstruction-api-index-cutover.md)
- [Modelo Work → Resource → File](v6-work-resource-model.md)
- [Retirada de StorageLocation](v6-storage-locations-removal.md)

**Regla:** el índice debe poder borrarse y reconstruirse desde las fuentes V6 sin depender de Representation ni de la estructura física de R2. La prueba de aceptación es una reconstrucción completa y una sincronización incremental funcionales, no simplemente que el proceso termine sin error.
