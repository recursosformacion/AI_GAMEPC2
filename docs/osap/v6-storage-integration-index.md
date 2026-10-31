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
- Resource: `id`, tipo, procedencia/aportante (PDMX, IMSLP, CPDL o usuario autenticado), derechos/licencia conocidos y características del material.
- File: identificador si es necesario, formato, MIME, tamaño/estado y enlace de descarga generado por Storage.
- Resource externo sin File: URL externa explícita y estado que no se confunda con un File alojado.
- Work sin Resources: inválida en V6; cada Work debe tener al menos un Resource.

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

La información que antes estaba en Representation (procedencia/aportante, identificador externo del material, derechos/licencia, edición, arreglo y tipo) debe leerse de Resource cuando describa ese material. La autoría/compositoría pertenece a Work y es común a todos sus Resources; un Resource no puede introducir un compositor alternativo para la misma Work.

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

## 8. Área personal y aportaciones de usuarios

OSAP-API debe integrar en V6 el área privada del usuario y el flujo de aportación/revisión/publicación. El catálogo sigue siendo Work → Resource → File; el espacio personal mantiene relaciones privadas con Works existentes y borradores separados, sin duplicar el catálogo. Solo las entidades publicadas se incorporan al índice general. Véase [especificación funcional en AI_osap-storage](https://github.com/recursosformacion/AI_osap-storage/blob/main/docs/v6-user-workspace-contributions.md) y [impacto de integración en OSAP-API](v6-user-workspace-contributions.md).


## 9. Regla vinculante de autoría, procedencia y derechos

- **Work:** contiene la autoría/compositoría de la obra. Todos sus Resources comparten esa autoría. Si dos materiales tienen compositores incompatibles porque son obras distintas, debe revisarse la identidad Work.
- **Resource:** contiene la procedencia/aportante (PDMX, IMSLP, CPDL o usuario autenticado) y los derechos/licencia aplicables a ese material, cuando se conocen.
- En altas directas de usuario, el aportante se obtiene automáticamente de la sesión autenticada; no se pregunta ni se acepta una identidad arbitraria del cliente.
- El titular de derechos puede ser el compositor o un tercero. No se deduce del compositor ni del aportante.
- Se conservan solo datos disponibles y necesarios. No se crean estructuras de titularidad, historiales o evidencias para escenarios hipotéticos; lo desconocido queda sin determinar.

## Permisos independientes de Work y Resource

Solo el compositor autenticado puede modificar los metadatos catalográficos de Work. Cada Resource solo puede modificarlo su creador. Cualquier otro usuario aporta un nuevo Resource a la misma Work. No se duplica Work ni se infiere permiso desde el aportante inicial. Toda Work debe tener al menos un Resource, aunque este sea URL-only y no tenga File.


## Regla vinculante: Resource original, arreglos y compositoría

- Toda Work se crea junto con un primer Resource que representa el material original de la obra. No existe Work sin ese Resource.
- Los Resources que se incorporan después a esa Work representan arreglos de la obra original. Si el material tiene una composición distinta, corresponde a otra Work.
- El compositor y los coautores se relacionan exclusivamente con Work. Resource **no tiene compositor ni admite el rol compositor**. No se duplica la relación de compositor en cada Resource.
- Los créditos personales propios de cada material (arreglista, editor, adaptador, intérprete, traductor, etc.) se relacionan con su Resource cuando se conocen.
- No se selecciona un Resource principal mediante un campo adicional: el primer Resource es el original por definición del proceso de creación. Su clase debe distinguirse explícitamente de los Resources de arreglo.
- En registros históricos no se presume que el primer registro encontrado, el más antiguo por fecha técnica o el único que tenga File sea el original. Solo se clasifica como original con evidencia; si no puede demostrarse, se registra un conflicto de migración y no se inventa un original.

El esquema y los servicios deben garantizar un único Resource original por Work, permitir cero o más Resources de arreglo, impedir el rol compositor en créditos de Resource y crear Work + Resource original como una operación lógica atómica. La migración debe señalar Works sin original demostrable, candidatos originales múltiples y créditos de compositor incompatibles.

---

## Corrección vinculante: Resource de referencia opcional

Esta regla sustituye las frases anteriores de este documento que declaren inválida una Work sin Resources o exijan un Resource original.

- Work puede existir con cero, uno o varios Resources. El índice debe indexar Works aunque no tengan Resources ni Files.
- Work puede seleccionar opcionalmente uno de sus Resources como Resource de referencia. La selección destaca un material útil para consultar la obra y no implica que sea el original histórico.
- El Resource de referencia puede ser la partitura original conocida, una edición crítica u otro material elegido. En repertorio clásico puede no conocerse el original; la referencia puede ser otra edición o quedar vacía.
- No inferir originalidad/referencia por orden de alta, antigüedad técnica, proveedor o presencia de File.
- No etiquetar automáticamente como arreglos los Resources añadidos después del primero.
- work_id identifica Work; resource_id identifica el material. La selección de referencia no sustituye el ID de Work.
- El adaptador y los DTO deben exponer la referencia como dato opcional y conservar todos los Resources; no elegir silenciosamente el primero.
- La presencia o ausencia de referencia no debe afectar a la indexación, autoría, permisos, disponibilidad ni descarga.
- Compositor y coautores siguen perteneciendo exclusivamente a Work; Resource no admite rol compositor.

Cualquier regla anterior de “Work sin Resources inválida” o “primer Resource original” queda reemplazada por esta corrección.
