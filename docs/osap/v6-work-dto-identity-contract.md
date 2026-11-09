# V6 — propuesta de DTO Work e identidad persistente API–Storage

**Estado:** propuesta documental; no congelada.  
**Fecha:** 2026-11-02.  
**Alcance:** conciliación de la matriz SQL `works`, el contrato Storage V6 y los consumidores OSAP-API/web.  
**Restricción:** no modifica código, esquema, índice ni datos.

## 1. Decisiones que sí están fijadas

- El modelo de Storage es `Work → Resource → File`; `Representation` desaparece.
- Work representa la composición canónica. Resource representa material OMR incorporado; File representa un fichero concreto.
- Una Work del catálogo Storage publicada requiere al menos un Resource, pero una respuesta de búsqueda federada puede presentar una Work candidata sin Resources OMR. La API no inventa Resources para satisfacer una regla de Storage.
- Autoría/compositoría pertenece a Work. Créditos de edición, arreglo, adaptación, interpretación y traducción pertenecen a Resource.
- Procedencia y derechos se registran en el Resource al que realmente se refieren. Uploader, compositor y titular/licenciante son conceptos distintos.
- Los resultados externos no se convierten automáticamente en Resources. Una coincidencia de título/compositor no demuestra identidad.
- No se expone como identidad canónica `works_key`, `works_music_digest`, `works_obra_iden`, una URL ni un ID numérico extraído de una URL.

## 2. DTO Work propuesto

Este esquema define la **cobertura conceptual** del DTO, no todavía un JSON Schema definitivo. Los campos marcados «condicional» dependen de revisar valores y usos; no se deben migrar ni retirar automáticamente.

| Campo propuesto | Estado | Regla |
|---|---|---|
| `id` | requerido | ID opaco, estable y tipado de Storage. No reutilizar como ID del índice o de proveedor. |
| `title` | requerido | Título canónico de la composición. |
| `song_name` | condicional | Mantener si el dato legado es un nombre cantable/alternativo de la composición; confirmar mediante muestreo y búsqueda. |
| `subtitle` | condicional | Work solo cuando el subtítulo describe la composición; si identifica una edición/versión, Resource. |
| `attribution_type` | candidato a Work | Estado de atribución (p. ej. conocido, anónimo, tradicional) sin fabricar una persona para los estados no personales. Confirmar vocabulario existente. |
| `attribution_note` | candidato a Work | Nota sobre atribución de la composición; no mezclar con notas editoriales del Resource. |
| `composer_credits[]` | requerido como colección | Créditos de compositor/coautores vinculados a personas resueltas, con rol y orden. La colección puede estar vacía cuando la atribución no está resuelta. |
| `opus` | condicional | Referencia textual propia de la composición; conservar forma original. |
| `catalogue_references[]` | propuesto | Referencias catalográficas. Antes de reemplazar el campo actual `catalogue`, comprobar cardinalidad y consumidores. No perder formato legado. |
| `composition_year` o `date_text` | pendiente semántico | Solo fecha/año de composición. No llamar `year` sin documentar su significado si hoy mezcla fechas. No convertir texto incierto a fecha exacta. |
| `epoch_id` / relación de época | candidato a Work | Referencia normalizada al catálogo de épocas. Comprobar si el ID está disponible y cómo se resuelve el catálogo en API. |
| `description` | condicional | Solo descripción de la composición; separar notas sobre edición, arreglo o fichero. |
| `genres[]` | condicional | Clasificaciones de Work si el vínculo actual realmente clasifica la composición; evitar duplicar una relación normalizada en un JSON sin fuente de verdad. |
| `language` / idiomas | condicional | Work si el idioma pertenece al texto original de la composición; Resource si describe traducción o versión textual. Confirmar si el modelo requiere varios idiomas. |
| `tags[]` | pendiente de clasificación | Clasificar etiquetas una por una: catálogo/composición en Work, edición/material en Resource, o proyección calculada. |
| `musical_key` | pendiente semántico | Work si es tonalidad estructural de la composición; Resource si procede de transposición o edición. |
| `measure_count` | pendiente semántico | Work si cuenta la estructura de la composición; Resource si varía por arreglo, corte o edición. |
| `parts[]` | pendiente semántico | Work solo para partes constitutivas de la composición. Particellas o partes preparadas para una plantilla concreta pertenecen a Resource/File. |
| `complexity` | pendiente semántico | No migrar hasta conocer escala, fuente y sujeto de la valoración; puede ser atributo de Resource o proyección. |
| `instruments[]`, `voices[]`, `ensembles[]` | pendiente semántico | Solo Work cuando describan la composición, no una edición/arreglo concreto. Acordar relación normalizada y evitar doble almacenamiento. |
| `reference_resource_id` | opcional | Solo apunta a un Resource hijo; no significa «original histórico» ni se infiere por fecha u orden. |
| `created_at`, `updated_at` | recomendados | Fechas técnicas del registro, no fechas de composición/publicación. |

### Campos que no pertenecen al DTO Work

- Páginas de una partitura/documento: Resource o File según qué se cuente.
- Formato/MIME, tamaño, estado de disponibilidad, nombre de fichero e identificador de File: File.
- Licencia, titular, evidencia de derechos y dominio público: Resource, solo cuando haya evidencia y sujeto claro.
- Uploader/creador del material: procedencia/auditoría del Resource; nunca inferirlo del compositor.
- Proveedor externo, ID de registro externo, URL del proveedor y variantes nativas: `ExternalMaterial` de OSAP-API, no Work canónica de Storage.
- Ruta física, bucket, object key, hash de almacenamiento: no forman parte del DTO público Work.
- Estadísticas y contadores: proyección o estadísticas, no identidad ni metadatos maestros de Work.

La lista anterior no autoriza a borrar columnas V5. Los campos ambiguos deben conservarse en el proceso de reconstrucción hasta que la auditoría de valores y consumidores establezca su destino.

## 3. Diferenciar tres tipos de identidad

### 3.1 Work canónica OMR

La autoridad sobre el ID canónico OMR es Storage. Su identificador es `omr_work_id` (en el contrato externo puede serializarse como `Work.id`). Ese ID no debe derivarse de título, compositor, `works_key`, digest, URL ni ID de proveedor.

### 3.2 Registro del índice de OSAP-API

El índice puede contener documentos agregados, resultados importados o registros con fuentes distintas. Su `work_id` actual no debe asumirse igual a Storage Work ID. Debe conservarse como identidad propia de índice hasta auditar cómo se genera, si es estable y qué fuentes agrupa.

### 3.3 Registro de proveedor externo

Un registro externo se identifica mediante una combinación tipada como `provider_id + source_id + source_entity_type` (y los discriminantes de variante exigidos por ese adaptador). Esta identidad permite volver a consultar la fuente; no declara que exista una Work OMR equivalente.

## 4. Relación persistente API–Storage recomendada

Introducir conceptualmente un registro de correspondencia explícito, gestionado por OSAP-API o por su capa de reconciliación. El nombre físico de la tabla no queda fijado aquí.

Campos mínimos propuestos:

| Campo | Propósito |
|---|---|
| `index_record_id` | ID estable del documento/registro del índice, con su espacio de nombres. |
| `omr_work_id` | ID de Work Storage a la que se ha vinculado explícitamente, nullable mientras no exista vínculo. |
| `provider_id`, `source_id`, `source_entity_type` | Identidad nativa externa cuando el registro procede de un proveedor. No rellenar con valores OMR ficticios. |
| `match_status` | Estado explícito, por ejemplo `unreviewed`, `confirmed`, `rejected`, `conflict`, `unmatched`. Vocabulario final pendiente. |
| `match_method` | Método/evidencia: revisión humana, clave externa verificada u otra evidencia reproducible. El título/compositor puede ser pista, no prueba automática suficiente. |
| `reviewed_by`, `reviewed_at` | Auditoría de decisiones humanas, cuando aplique. |
| `created_at`, `updated_at` | Trazabilidad técnica. |

Reglas:
1. Una fila de índice no puede quedar vinculada a una Work OMR solo porque coincidan título y compositor normalizados.
2. Un vínculo confirmado debe referenciar una Work existente; la restricción exacta de cardinalidad (uno-a-uno o muchos-a-uno) se decide tras revisar si el índice agrupa varias fuentes/registros en un único documento.
3. Si varias fuentes se agrupan en una ficha de índice, mantener sus identidades de proveedor individualmente; no perderlas al vincular la ficha a OMR.
4. Los vínculos no confirmados no enriquecen el detalle canónico de Work. La API puede presentar resultados por separado o mostrar una asociación candidata claramente no confirmada.
5. Un vínculo rechazado/conflictivo se conserva como decisión auditada para evitar repetir el mismo emparejamiento automático.
6. Cambiar/reconstruir el índice no debe cambiar el ID de Work Storage ni borrar la correspondencia confirmada.
7. La ausencia de vínculo no impide que una Work externa aparezca en búsqueda; solo impide presentarla como la misma Work OMR.
8. No se debe crear una Work OMR automáticamente por cada fila externa ni crear un Resource por cada URL de proveedor.

No se recomienda usar directamente `works_origin + works_origin_id` como correspondencia universal: primero hay que establecer para cada fila qué entidad identifica `works_origin_id` (Work externa, página, edición o fichero). Puede alimentar la tabla de correspondencias solo después de clasificar su semántica.

## 5. Forma de respuesta federada en OSAP-API

La API debe separar las identidades dentro de la respuesta, en lugar de reutilizar `RepresentationInfo` como recipiente universal.

Contrato conceptual de un resultado:

```json
{
  "omr_work": {
    "id": "wrk_opaque",
    "title": "Ave verum corpus",
    "resources": []
  },
  "external_materials": [
    {
      "provider_id": "provider_example",
      "source_id": "source_record_123",
      "source_entity_type": "score",
      "title": "Ave verum corpus",
      "access": []
    }
  ],
  "provisional_group": null,
  "identity_links": [
    {
      "omr_work_id": "wrk_opaque",
      "external_identity": {
        "provider_id": "provider_example",
        "source_id": "source_record_123",
        "source_entity_type": "score"
      },
      "status": "confirmed"
    }
  ]
}
```

Es un ejemplo ilustrativo, no una obligación de devolver todas las claves en cada resultado. Una respuesta puede tener solo `omr_work`, solo `external_materials`, o un `provisional_group` sin identidad canónica. El contrato final deberá definir si la API usa una unión discriminada por tipo de resultado o una envoltura con campos opcionales; la regla obligatoria es que los tipos no se mezclen.

`identity_links` solo se incluye cuando hay una correspondencia persistente registrada; no se genera durante cada búsqueda por similitud textual. Los datos y enlaces externos siguen perteneciendo al adaptador/proveedor.

## 6. Cambio requerido en el enriquecimiento actual

El detalle actual de API que busca Storage por título/compositor debe sustituirse por:
1. resolver el ID estable del registro de índice;
2. consultar la correspondencia persistente;
3. si el vínculo está confirmado, solicitar el detalle de la Work OMR mediante su ID Storage;
4. si no existe vínculo confirmado, no llamar a Storage para fingir una identidad; devolver el registro externo/provisional según su tipo;
5. si la referencia confirmada apunta a una Work inexistente, registrar conflicto de integridad y degradar el enriquecimiento de forma explícita, sin hacer fallback por título;
6. retirar la mezcla de materiales del índice dentro de `resources` y la extracción de IDs desde URLs.

## 7. Pruebas de contrato necesarias

- Mismo título y compositor, IDs distintos y sin vínculo: no se fusionan.
- Diferencias de acentos/puntuación no crean ni confirman vínculo automáticamente.
- Vínculo confirmado: el detalle se resuelve por ID OMR persistente, aunque cambie el título visible.
- Dos registros externos de proveedores distintos pueden apuntar a una Work OMR confirmada sin convertirse en Resources.
- Work OMR sin vínculo externo sigue disponible en Storage.
- Registro externo sin Work OMR sigue visible en búsqueda federada.
- Reconstruir el índice preserva los vínculos confirmados si el ID de registro está diseñado para ser estable; si no lo es, se necesita una clave estable de origen antes de automatizar la reconstrucción.
- Un URL con sufijo numérico no genera File ID ni Resource ID.
- Material externo no aparece en `resources[]` de Storage.
- Una correspondencia obsoleta o rota se informa como conflicto; no activa matching textual de respaldo.

## 8. Pendientes de evidencia antes de congelar

1. Muestrear los valores reales de `works_song_name`, subtítulo, tonalidad, año, duración, compases, partes, complejidad, descripción, voicing e instrumentación.
2. Auditar creación/estabilidad de IDs de documentos de índice y si cada documento representa una sola Work, varias fuentes o un grupo provisional.
3. Clasificar `works_origin_id` por tipo de entidad y proveedor.
4. Revisar cardinalidad de los vínculos índice↔OMR y necesidad de historial de decisiones.
5. Auditar importadores, consultas SQL, informes y administración más allá de los consumidores API/web ya documentados.
6. Acordar nombres finales de campos y vocabularios; este documento no congela `catalogue` frente a `catalogue_references[]`, `year` frente a `composition_year`, ni los campos musicales ambiguos.

**Criterio de cierre:** no hay matching silencioso por texto; cada campo Work tiene semántica y consumidores identificados; cada vínculo API–Storage es persistente, tipado y auditable; la federación no fabrica Resources; y el DTO final se refleja en OpenAPI 3.1 y pruebas de contrato antes de implementar el corte.


## 9. Revisión del sistema de indexación y URLs públicas (2026-11-08)

Esta sección actualiza la hipótesis anterior sobre la estabilidad de los IDs. Se ha revisado el historial reciente de `AI_GAMEPC2` y el código vigente de indexación y SEO.

### 9.1 Identidad pública de Work del índice

- La URL canónica utiliza `/obras/index-{id}/{slug}`.
- El prefijo `index-` distingue el ID de ficha del índice de IDs numéricos heredados.
- El slug se deriva del título y es descriptivo; no es identidad. Si cambia, la ruta redirige con 301 conservando el ID.
- Las rutas numéricas antiguas se redirigen a `/obras/index-{id}`.
- El resolver dual consulta el índice actual y la instantánea antigua. Solo redirige una URL antigua a otra ficha cuando existe correspondencia inequívoca; evita redirigir a una obra distinta cuando el ID numérico se ha reutilizado.

Por tanto, la propuesta V6 no debe describir el ID de índice como necesariamente efímero ni proponer sustituirlo por matching textual. Hay una estrategia deliberada de IDs públicos estables y conservación de URLs.

### 9.2 Reconstrucción shadow segura

El commit `3984beb833d3587d471bb4ac16d6e477eadde4f5` introduce `script/rebuild_index_safe.py`:
- construye primero en una base de datos shadow;
- empareja principalmente mediante `provider + source_rep_id`;
- actualiza las filas vivas conservando sus `index_works.id`;
- inserta una nueva fila viva cuando no encuentra una identidad de origen inequívoca;
- sustituye las representaciones/voicings de las obras mapeadas y deja intactas las obras ausentes para una poda explícita posterior.

La descripción del script menciona `title_key + person_id + catalogue`, pero la implementación revisada no usa ese fallback: el merge implementado utiliza `provider + source_rep_id` y comenta expresamente que el título no es identidad. Debe corregirse esa discrepancia documental en el propio script antes de considerarlo especificación fiable.

Esta estrategia conserva el ID de una Work existente cuando al menos una identidad de representación de origen permite mapearla inequívocamente. No demuestra por sí sola estabilidad universal para registros sin `source_rep_id`, cambios de identificadores nativos, divisiones/fusiones de grupos o proveedores que alteren su identidad.

### 9.3 Reconstrucción completa y tabla de alias

El commit `745d7df01f0210079132be28f1b798c5c40deb02` modifica `script/rebuild_index.py --full`:
- crea `index_id_aliases(old_id, new_id, method)`;
- toma una instantánea de `provider, source_rep_id, resource_id`;
- trunca `index_works`, `index_representations` e `index_work_voicings`;
- reconstruye el índice y calcula correspondencias antiguas→nuevas por `provider + source_rep_id`.

Esto conserva una relación de alias cuando la correspondencia es inequívoca, pero **no conserva el ID original como ID vivo**: el ID nuevo se asigna después del truncado. Es distinto de la reconstrucción shadow segura.

Además, el servicio programado `deploy/osap-index-full.service` sigue ejecutando `script/rebuild_index.py --full`, no `rebuild_index_safe.py`. Por tanto, el procedimiento periódico desplegado en el repositorio sigue siendo el destructivo con generación de alias. No se ha comprobado aquí qué servicio está instalado/activo realmente en producción.

### 9.4 Resolver de URLs antiguas: punto de integración por verificar

El resolver dual añadido en noviembre consulta `legacy_index_map` mediante `legacy_target_id()`, mientras que el script de reconstrucción completa escribe `index_id_aliases`. En el código revisado no se ha localizado la creación/copia de `index_id_aliases` hacia `legacy_index_map`, ni la creación de las tablas `legacy_index_works` / `legacy_index_representations` que el resolver consulta para servir instantáneas antiguas.

No se debe asumir que ambas tablas son equivalentes. Hay que localizar el proceso de snapshot/cutover y demostrar que:
1. la instantánea antigua se conserva antes del truncado;
2. el mapa `index_id_aliases` se publica como `legacy_index_map` o el resolver lee la tabla real de alias;
3. las URLs antiguas se resuelven después de reinicios y despliegues;
4. los alias ambiguos/no resueltos no redirigen a otra obra.

### 9.5 Efecto sobre el diseño V6

- El ID público actual `index-{id}` debe tratarse como identificador persistente de ficha API mientras se mantenga el contrato de URLs.
- No debe equipararse automáticamente con el ID de Work de Storage. Son identidades de dos dominios, aunque una ficha indexada pueda estar asociada a una Work OMR.
- Si V6 sustituye o reconstruye el índice, debe preservar los IDs públicos existentes o mantener un registro permanente de alias/redirecciones, con una política explícita para colisiones y ambigüedad.
- La correspondencia API↔Storage propuesta en la sección 4 sigue siendo necesaria, pero su clave de API debe ser el ID público estable de ficha (o una identidad interna estable que lo resuelva), no un ID temporal de reconstrucción.
- La correspondencia con proveedor sigue usando la identidad nativa tipada. `provider + source_rep_id` es clave de reconstrucción valiosa, pero debe validarse por proveedor, tipo de entidad y cardinalidad; no se debe asumir universalmente que `source_rep_id` es globalmente único.
- No se debe cambiar un ID publicado por cambios de título, compositor, catálogo, agrupación de proveedores ni migración de Storage.

**Conclusión revisada:** OSAP ya contiene mecanismos explícitos para conservar URLs y IDs de índice, y la reconstrucción shadow evita reemplazar IDs vivos en el caso de mapeo por origen. Sin embargo, el servicio programado del repositorio sigue usando la reconstrucción completa que reasigna IDs y depende de un mapa de alias. Hasta verificar el puente `index_id_aliases`→`legacy_index_map` y el snapshot histórico, no puede afirmarse que todos los IDs publicados sean inmutables en cualquier reconstrucción.

### 9.6 Verificación detallada del resolver, alias y casos de reconstrucción (8-11-2026)

La revisión de la implementación actual confirma estos elementos:

- `src/osap/api/seo/slug.py` declara explícitamente que el slug nunca es identidad. `normalize_work_id()` acepta tanto `index-123` como `123` y normaliza a `index-123`.
- `src/osap/api/http/seo.py::_resolve_work()` consulta la ficha actual y la instantánea antigua por separado. Si el mismo número existe en ambas generaciones y el slug no coincide con ninguna, devuelve no encontrado en vez de redirigir a una obra potencialmente distinta.
- Cuando el slug coincide con la ficha antigua, `_legacy_redirect()` solo redirige si `legacy_target_id()` devuelve un destino y ese destino existe en el índice actual. Si no hay destino inequívoco, sirve la instantánea antigua.
- `IndexCatalogProvider.legacy_target_id()` consulta exactamente `legacy_index_map(old_id,new_id)`. La lectura de fichas antiguas consulta `legacy_index_works` y `legacy_index_representations`.
- Los tests SEO prueban el 301 para un alias inequívoco y el servicio de una ficha antigua sin equivalente. No prueban la creación/publicación de las tablas legacy ni el paso de `index_id_aliases` a `legacy_index_map`.

**Hallazgo crítico adicional:** en el árbol actual no aparece ninguna migración, script o función que cree/pueble `legacy_index_map`, `legacy_index_works` o `legacy_index_representations`. El script full crea `index_id_aliases` y `index_rebuild_old_reps`, pero no crea ni rellena las tablas que lee el resolver. Por tanto, el mecanismo SEO de compatibilidad está implementado en lectura y probado con dobles de test, pero su preparación operativa no está demostrada en el repositorio. No se puede concluir que los enlaces antiguos estén protegidos después de un full rebuild real.

#### 9.7 Casos de identidad y cobertura efectiva

| Cambio / operación | Comportamiento del código revisado | Garantía |
|---|---|---|
| Cambio de título o slug | El ID forma parte de la URL; el slug canónico nuevo produce 301 desde el slug anterior cuando la ficha se resuelve. | **Sí**, mientras el ID vivo no cambie. |
| Incremental `sync_index.py` | Reanuda por IDs de origen/estado y hace upsert en el índice; no reconstruye IDs de las filas ya reconocidas. | **Preservación esperable**, sujeta a la clave única y al matching del indexador. |
| Full rebuild programado | Hace snapshot de representaciones, trunca las tres tablas y vuelve a insertar; los IDs AUTO_INCREMENT se asignan de nuevo. | **No conserva IDs vivos**. Depende de alias y snapshot. |
| Alias old→new inequívoco | El full rebuild inserta en `index_id_aliases` cuando todas las coincidencias del old work apuntan a un solo new work. | **Parcial**; el resolver no consulta esa tabla directamente. |
| Una obra antigua se divide en varias nuevas | La consulta de alias exige `COUNT(DISTINCT n.work_id)=1`; no crea alias para ese old_id. | No hay redirección automática; solo sería recuperable si se conserva la instantánea antigua y el resolver puede leerla. |
| Varias obras antiguas se fusionan en una nueva | Cada old_id puede apuntar al mismo new_id si su correspondencia es inequívoca. | Válido como redirección muchos-a-uno, pero falta probar el puente operativo. |
| Cambia/desaparece el ID nativo de una fuente | No hay match por `provider + source_rep_id`; full rebuild no genera alias por título. | No garantizado. |
| Fuente desaparece del catálogo | El full rebuild elimina la fila viva al truncar; alias solo se calcula para las representaciones antiguas que encuentran destino. | Depende de snapshot/legacy; el safe rebuild conserva filas ausentes y no poda. |
| Colisión o clave de origen duplicada | Los scripts usan `provider + source_rep_id`, con cardinalidades distintas en cada etapa. | Requiere validación por proveedor; no asumir unicidad global. |

#### 9.8 Límites detectados en la reconstrucción shadow segura

La inspección de `rebuild_index_safe.py` confirma que la implementación no coincide con su docstring:

- El docstring todavía anuncia `title_key + person_id + catalogue`; el código no usa ese fallback. Solo usa `provider + source_rep_id`.
- Para cada obra del build, agrupa las coincidencias de representaciones contra las filas vivas y acepta el mapeo solo si encuentra exactamente un `live work_id` distinto.
- Si las representaciones de una obra del build corresponden a más de una obra viva (posible fusión/división previa), esa obra del build no se mapea y se inserta con un ID nuevo. Las filas vivas antiguas permanecen, por lo que puede quedar duplicidad.
- No se valida que el mapeo sea biyectivo ni se impone unicidad de `live_id` en la tabla temporal. Dos obras del build podrían apuntar al mismo ID vivo si comparten identidades de origen.
- El merge actualiza metadatos seleccionados de `index_works`, pero no todos los campos de identidad (`title_key`, `person_id`, `catalogue_key`) en la sentencia UPDATE. La sincronización de representaciones y voicings se hace en sentencias posteriores.
- El procedimiento no usa una transacción única para el merge y opera con autocommit; un fallo intermedio podría dejar el índice vivo parcialmente actualizado.
- No borra las obras vivas ausentes del shadow build (esto está documentado y evita bajas implícitas), pero tampoco hay aquí un paso explícito de poda con política de alias.

Por tanto, el shadow rebuild evita el truncado y conserva IDs para los casos que mapea, pero no es todavía una reconstrucción segura universal ante fusiones, divisiones o fallos parciales.

#### 9.9 Servicio programado y despliegue

En el repositorio actual:

- `deploy/osap-index-full.service` ejecuta semanalmente `script/rebuild_index.py --full --providers omr,cpdl`.
- `deploy/osap-index-full.timer` programa ese servicio los domingos a las 03:30.
- `deploy/osap-index-sync.service` ejecuta `script/sync_index.py`; su timer lo programa cada 30 minutos.
- No hay evidencia en el repositorio de que el servicio semanal haya sido cambiado a `rebuild_index_safe.py`. Tampoco se puede deducir desde GitHub qué unidad está instalada/activa realmente en el servidor.

#### 9.10 Requisitos antes de afirmar inmutabilidad de las URLs

1. Definir el ID de la ficha pública como identidad persistente independiente de los IDs de proveedores y de Storage.
2. Hacer que la reconstrucción normal preserve ese ID; un full rebuild no debe truncar/reasignar IDs públicos.
3. Si se requiere reagrupación, registrar una decisión explícita de identidad: continuidad, fusión o división. No resolver divisiones con una redirección arbitraria.
4. Mantener un registro histórico durable y consultado por el resolver, con restricciones de unicidad y detección de ciclos/conflictos.
5. Crear/publicar snapshot y alias de forma atómica antes de cambiar el índice activo. Verificar que el resolver consulta el mismo registro que produce el rebuild.
6. Añadir pruebas de integración contra MySQL real para el proceso completo: snapshot → reconstrucción → publicación de alias → resolución HTTP, incluyendo colisión de IDs numéricos entre generaciones, fusiones, divisiones, fuentes desaparecidas y fallos intermedios.
7. No reutilizar jamás un ID público retirado para una obra distinta. Si no existe correspondencia inequívoca, mantener el histórico o responder 404/410; nunca redirigir por similitud de título.

**Conclusión:** la política de URL es correcta en concepto y el resolver intenta evitar redirecciones incorrectas. Sin embargo, la garantía integral de inmutabilidad todavía no está demostrada: el full rebuild semanal del repositorio reasigna IDs y el puente de alias/snapshot que necesita el resolver no está implementado en los archivos revisados. El shadow rebuild es menos arriesgado, pero tiene límites ante agrupaciones no biyectivas y fallos parciales. Para V6 debe preservarse la identidad pública existente como contrato independiente y no diseñar la API/Storage suponiendo que el ID de índice equivale al ID canónico de Work.

