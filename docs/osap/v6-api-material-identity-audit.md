
# V6 — Auditoría del recorrido de identidad, ficha y descarga de materiales en OSAP-API

**Estado:** auditoría documental de código existente; no se ha modificado código ni base de datos.  
**Alcance:** búsqueda, contrato de respuesta, ficha de material, disponibilidad, detalle de Work y descarga.  
**Criterio:** V6 puede rediseñar OSAP-API; no se considera obligatorio preservar los contratos ni las abstracciones actuales.

## 1. Conclusión ejecutiva

El recorrido actual funciona, pero la identidad de un material se representa de varias maneras que no son equivalentes. El ID que se entrega en búsqueda no siempre contiene toda la identidad de origen, algunas rutas lo descomponen para recuperar datos y la resolución de materiales en vivo depende de una caché en memoria.

V6 debe establecer una identidad tipada y resoluble para cada material, separando:

- Work canónica OMR, Work provisional de búsqueda y grupo de resultados.
- Resource OMR y registro/material externo de proveedor.
- File OMR y variante/archivo ofrecido por un proveedor externo.
- ID interno de API e ID original estable del proveedor.
- URL de acceso y objeto/identidad que esa URL permite resolver.

No se debe reutilizar un ID de File como ID de Resource, ni interpretar partes de una cadena opaca para decidir proveedor, Work, Resource o cuota.

## 2. Recorrido HTTP actual

### 2.1 Búsqueda

- POST /api/v1/searches recibe SearchRequest y devuelve SearchResponse con estado inicial running.
- GET /api/v1/searches/{search_id} permite consultar el trabajo asíncrono hasta done o error.
- SearchResponse.results[] contiene work, representation (selección principal), representations[], score, evidence y relationships.
- WorkInfo expone work_id, title, composer, catalogue y collection.
- RepresentationInfo expone id, provider, format, confidence, url, title, available y metadata.

El nombre Representation no expresa de forma suficiente si el elemento es un Resource OMR, un registro de IMSLP/CPDL, una página de metadatos o una variante descargable. V6 debe sustituir esa ambigüedad por conceptos explícitos, no por un renombrado global y mecánico.

### 2.2 Ficha y disponibilidad de un material

Rutas actuales en src/osap/api/http/search.py:

- GET /api/v1/representations/{representation_id}: ficha del material, construida por build_representation_payload().
- GET /api/v1/representations/{representation_id}/probe: comprueba si hay URL de descarga propia o si el servidor puede leer la URL externa.
- GET /api/v1/representations/{representation_id}/download: entrega el fichero o redirige al proveedor; ?view=1 intenta servirlo inline.
- Ruta HTML heredada /representacion/{rep_id}: presenta la misma ficha.

La ruta de descarga distingue actualmente OMR de otros proveedores usando campos del diccionario y heurísticas sobre la URL (dominio/base Storage, rutas /api/download/, /api/v1/files/ y extensiones). Para externos, puede intentar proxy de vista y redirigir al navegador si el proveedor impide la lectura del servidor.

### 2.3 Detalle de Work

GET /api/v1/works/public/{work_id} entrega una ficha del índice federado.  
GET /api/v1/works/{work_id} consulta el detalle de Storage y después ejecuta _merge_index_resources().

Ese helper busca materiales del índice por título y compositor, extrae un número de download_url y los añade a doc["resources"] como si fueran Files de Storage. El propio comentario indica que Storage guarda un recurso por obra y el índice añade las demás representaciones.

Esta unión por título/compositor y la conversión de una URL a file_id son incompatibles con el modelo V6 Work → Resource → File: un material externo federado no es un Resource OMR, y un File no debe inferirse parseando una URL. V6 debe devolver por separado Resources OMR y materiales federados, con su procedencia explícita. El helper no debe sobrevivir con su semántica actual.

## 3. Cómo se construyen los IDs actuales

### 3.1 Candidatos procedentes del índice

IndexCatalogProvider consulta index_works y index_representations. Cada candidato lleva el proveedor real (por ejemplo omr, imslp, mutopia, musicbrainz o cpdl) aunque el proveedor que ejecuta la consulta sea el índice virtual.

Para candidatos cuyo candidate_id empieza por index-, PlatformApiCore._to_rep() construye:

idx-{index_work_id}-{provider}-{resource_id}-{format}

La tabla index_representations tiene una identidad de fila más rica: work_id, provider, source_rep_id, resource_id, format y title_provider participan en su clave única uq_idxrep.

**Hallazgo:** el ID público determinista no incluye source_rep_id ni title_provider. Por tanto, la identidad de la URL/API es más estrecha que la identidad admitida por la tabla. Dos filas distintas pueden generar el mismo ID si coinciden Work, proveedor, resource_id y formato, pero difieren en source_rep_id o título de proveedor. En ese caso el diccionario _representations y las fusiones por r.id pueden sobrescribir o colapsar materiales distintos.

### 3.2 Candidatos obtenidos en vivo

Para candidatos no procedentes del índice, _to_rep() genera:

r-{stable_id(provider, download_url o view_url o candidate_id, format)}

La identidad se apoya en URL/candidate_id y formato, no necesariamente en el ID nativo de la fuente. Además, la información completa se guarda en _representations, una caché en memoria.

**Hallazgo:** el ID de un candidato vivo no tiene un mecanismo general de reconstrucción tras reiniciar el proceso. get_representation_download() consulta primero la caché y después intenta resolver IDs del índice; no reconstruye de forma genérica un ID r-... mediante el adaptador original. Una ficha o descarga puede dejar de resolverse tras reiniciar API aunque el resultado se hubiera mostrado antes.

### 3.3 Resolución de IDs del índice

IndexCatalogProvider.get_representation() interpreta el ID separándolo por guiones:

- Si resource_id > 0, consulta por work_id + provider + resource_id, sin incluir source_rep_id ni format en el WHERE.
- Si resource_id = 0, busca por work_id + provider y prioriza el formato solicitado, pero el desempate final es por ID de fila.

Esto no recupera necesariamente la misma fila que originó el ID. En particular, cuando hay varios registros con resource_id=0 y mismo formato, la resolución puede seleccionar una fila arbitraria; cuando resource_id>0, tampoco distingue source_rep_id ni formato.

La misma construcción reducida del ID aparece en get_work_with_representations(), que alimenta la ficha pública/SEO. Por tanto, el problema no está limitado al endpoint de búsqueda.

## 4. Otros acoplamientos a eliminar o rediseñar

1. **Deduplicación:** _rep_identity_key() y _dedupe_reps() usan resource_id, después source_rep_id + format, y finalmente URL. Sin embargo, el ID final que se utiliza en varios diccionarios y fusiones no conserva necesariamente esos mismos discriminantes.
2. **Fusión de resultados:** _merge_same_work() acumula representaciones en un diccionario indexado por r.id. Una colisión de ID elimina una representación distinta.
3. **Enriquecimiento:** _work_rep_cache se indexa por título+compositor normalizados, no por Work canónica. La caché puede fusionar materiales de grupos distintos o no seguir una reconciliación posterior.
4. **Cuotas:** _resource_id_from_rep() extrae el Resource ID de una posición de la cadena del ID. La cuota OMR debe recibir un Resource ID tipado y resuelto, nunca parseado del identificador público.
5. **Analítica:** _analytics_target() intenta reconstruir proveedor, Work y formato desde el ID. La analítica debe consumir la identidad resuelta, no interpretar el ID.
6. **Detalle Storage:** _merge_index_resources() busca por título/compositor y convierte una URL en File ID. Debe desaparecer en favor de una composición explícita de Work + Resources OMR + materiales federados.
7. **Acceso:** la clasificación Storage/proveedor se apoya parcialmente en URLs y nombres de proveedor. V6 debe resolver por tipo de origen y adaptador registrado; la URL es un destino de acceso, no una prueba de propiedad.
8. **Probe:** la caché temporal de disponibilidad se indexa por URL. Es una observación temporal del acceso, no identidad del material; conviene asociarla a la identidad de origen y su caducidad.

## 5. Qué significa hoy el índice y por qué no es el catálogo maestro

El índice persistente de API contiene index_works, index_representations e index_work_voicings.

- script/index_works.py ingiere varias fuentes y agrupa Works por reglas de catálogo, anclaje y finalmente title_key + person_id.
- La clave única de index_works es title_key(191) + person_id.
- index_representations conserva identificadores de origen y discriminantes adicionales.
- script/rebuild_index.py permite reconstrucción completa o incremental.
- script/sync_index.py mantiene cursores/estado por proveedor.

El índice es una proyección federada y normalizada, no una autoridad de identidad equivalente al catálogo OMR. El agrupamiento batch y el agrupamiento dinámico de work_merge_service().group() son procesos distintos. V6 debe definir una autoridad canónica para Works OMR y una reconciliación explícita para asociar registros externos; no debe convertir automáticamente cada grupo del índice en una Work OMR.

**Precaución de migración:** el indexador actual documenta que el corpus CPDL está materializado en tablas de Storage (works_origin='CPDL') y lo indexa como fuente. La clasificación de esos registros en V6 debe basarse en su estado real de incorporación, Resource y File, y en la decisión de catálogo OMR; no basta con mirar el valor provider='cpdl'. No se deben perder materiales ya incorporados ni convertir automáticamente cualquier fila del proveedor en Resource OMR.

## 6. Contrato objetivo recomendado para V6

### 6.1 Identidad de Work

Cada resultado debe indicar si representa:

- una Work OMR canónica, con su ID canónico;
- una Work externa aún no reconciliada;
- un grupo provisional de búsqueda que reúne candidatos posiblemente relacionados.

El identificador de grupo provisional no se presenta como ID canónico y no crea una asociación persistente. Cuando la reconciliación confirma una relación, API vincula el registro externo con la Work canónica sin cambiar la identidad nativa del proveedor.

### 6.2 Identidad de material

El contrato debe distinguir, como mínimo:

- **Material OMR:** referencia a un Resource V6 de Storage; si tiene Files, estos se ofrecen como opciones de acceso con su formato.
- **Material externo:** referencia a un registro/objeto nativo de un proveedor, conservando provider_id y source_id originales y cualquier discriminante de edición/variante necesario.
- **Material de metadatos:** registro que permite abrir una ficha externa pero no ofrece fichero descargable.

El ID público de API debe ser opaco, estable y resoluble después de reinicios. No debe exigir que el cliente conozca ni reconstruya IDs internos de Storage o del proveedor. La resolución interna conserva explícitamente el tipo de origen y el ID nativo.

### 6.3 Acceso y formatos

Un material puede tener cero, uno o varios accesos/archivos. Para OMR, API obtiene los Files del Resource mediante el contrato V6 de Storage. Para un proveedor externo, el adaptador devuelve las opciones que la fuente ofrece.

Cada opción de acceso debe indicar el formato y la acción disponible (descarga, vista, apertura en el proveedor o solo metadatos). No se debe usar un único booleano available para mezclar “el registro existe”, “el servidor puede leerlo”, “el navegador puede abrirlo” y “hay un fichero descargable”.

### 6.4 Rutas

Las rutas actuales pueden conservarse temporalmente como fachada HTTP, pero sus parámetros deben resolver un ID opaco mediante un servicio de identidad/material. El contrato V6 debe ser semánticamente explícito (material/ficha/acceso), no depender del nombre heredado representation.

La descarga debe despacharse por tipo de origen:

- OMR → Storage resuelve Resource/File y entrega el acceso autorizado.
- Externo → adaptador del proveedor resuelve el registro nativo y aplica su estrategia de acceso.
- Solo metadatos → no se ofrece una ruta de descarga ficticia.

Las cuotas OMR, la analítica y los permisos reciben IDs tipados ya resueltos. Nunca extraen IDs de segmentos de URL o de cadenas públicas.

## 7. Requisitos de aceptación V6

- Una Work OMR con cero Resources puede aparecer en resultados junto a materiales externos sin crear Resources ficticios.
- Una Work con varios Resources OMR y varios Files por Resource presenta todos los materiales y opciones pertinentes.
- Dos registros externos distintos de un mismo proveedor no colisionan aunque compartan título, URL o formato si la fuente los identifica como distintos.
- Cada ID de material emitido por búsqueda sigue resolviéndose tras reiniciar API.
- La ficha, el probe, la vista y la descarga resuelven exactamente el mismo material que originó el ID.
- Los IDs de Work, Resource, File, registro externo y grupo provisional no se intercambian.
- La búsqueda inmediata puede agrupar provisionalmente; solo la reconciliación confirma asociaciones persistentes.
- El índice se puede reconstruir sin convertir materiales externos en Resources OMR.
- La migración conserva los Files OMR actuales y sus punteros físicos sin mover, copiar, borrar ni renombrar objetos R2.
- No se usa coincidencia por título/compositor como sustituto silencioso de una asociación persistente entre Work y fuente.

## 8. Límites de esta auditoría

Esta revisión confirma el recorrido de búsqueda, contratos, rutas HTTP, resolución del índice, composición del detalle de Work e indexación batch. No valida el contenido real de la base de datos de producción, la unicidad efectiva de los IDs nativos de cada proveedor ni la accesibilidad actual de todas las URLs. Esos puntos requieren inventario y pruebas controladas en entorno de desarrollo durante la fase de diseño/migración; no se han ejecutado aquí.



## 9. Precisiones adicionales del parsing heredado

- get_representation_download() tiene además un fallback que acepta cualquier representation_id numérico y lo interpreta como File ID de Storage. V6 debe eliminarlo: el endpoint de material no debe aceptar silenciosamente un ID de File como ID de material.
- _analytics_target() interpreta el ID idx-...-resource_id-format y usa todos los segmentos desde la posición del resource_id como formato. Con el formato actual, puede registrar un valor compuesto resource_id-format en vez del formato real. Este es otro efecto de usar parsing de cadenas como contrato.
- _merge_index_resources() no comprueba primero que el provider de cada fila sea OMR antes de extraer el número final de download_url como file_id. Por ello, además de mezclar dominios conceptuales, puede confundir una URL externa cuyo path termine en número con un File de Storage.

Estos hallazgos refuerzan la regla: ninguna ruta, cuota, analítica ni composición de detalle debe deducir la identidad de un material a partir de posiciones de texto o del aspecto de su URL. El servicio de resolución debe devolver un objeto tipado y todas las operaciones posteriores deben usar sus campos ya resueltos.
