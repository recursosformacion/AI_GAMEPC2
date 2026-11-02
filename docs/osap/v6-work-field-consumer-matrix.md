# V6 — Matriz de consumidores de los campos de Work

**Estado:** auditoría documental de código existente y propuesta de contrato.  
**Fecha:** 2026-11-02.  
**Alcance:** OSAP-API, su contrato público, la ficha web, el índice y la integración con osap-storage.  
**Restricción:** solo documentación; no se modifica código, esquema, índice ni datos.

Este documento complementa la matriz de migración SQL de Storage `docs/v6-work-field-mapping.md`. La matriz de Storage clasifica el destino semántico de las columnas; esta matriz identifica qué consumidores actuales se han podido verificar en OSAP-API y qué debe cambiar en V6.

## 1. Hallazgo principal: hoy no existe una única respuesta Work

OSAP-API sirve actualmente tres vistas distintas que no deben confundirse:

1. **Work de búsqueda/índice:** `SearchResultItem.work` (`WorkInfo`) contiene `work_id`, `title`, `composer`, `catalogue` y `collection`. Se utiliza en resultados y en `WorkDetailTabs`.
2. **Ficha pública/SEO:** `GET /api/v1/works/public/{work_id}` devuelve una Work derivada del índice (`title`, `composer`, `catalogue`, `year`, `instrumentation`, estadísticas) y una lista de materiales federados llamada `representations`.
3. **Detalle enriquecido OMR:** `GET /api/v1/works/public/{work_id}/details` llama a `osap_work_details()`. Actualmente busca por título en Storage y acepta la fila si título y compositor coinciden tras normalización. No existe una correspondencia estable Work índice ↔ Work OMR. La ficha `WorkPage` mezcla los datos de ambas respuestas y conserva el índice como fallback.

Además, `GET /api/v1/works/{work_id}` entrega el detalle crudo de Storage para inspección y ejecuta `_merge_index_resources()`, que incorpora materiales del índice dentro de `resources` mediante título/compositor y extrae un número de `download_url` como `file_id`. Este comportamiento es incompatible con la separación V6 entre Resources OMR y materiales externos federados y debe retirarse.

**Consecuencia:** el DTO Work V6 no debe intentar representar a la vez la Work canónica de Storage, una Work externa de índice y un grupo provisional de búsqueda. La respuesta federada de API debe expresar esas identidades por separado.

## 2. Matriz columna → destino → consumidores actuales

Los consumidores se citan por ruta de código. “No localizado” significa que no se ha encontrado un uso explícito en los recorridos de Work revisados; no demuestra que no existan consumidores en importadores, administración, consultas SQL o procesos externos. Esos casos requieren ampliar el inventario antes de retirar columnas.

| Columna V5 | Destino semántico V6 | Consumidor actual verificado en API/web | Tratamiento V6 |
|---|---|---|---|
| `id` | Work | `StorageComposerClient.get_work()`; `OsapWorkDetails.id`; `WorkPage` muestra el ID OMR | ID opaco de Work; no mezclar con el ID de índice ni con Resource/File. |
| `works_title` | Work.title | `WorkInfo.title`, ficha pública SEO, `WorkPage`, `WorkDetailTabs`, SEO SSR | Campo canónico obligatorio según reglas del catálogo; los títulos de fuente quedan en federación cuando proceda. |
| `works_song_name` | Work.song_name, sujeto a validar semántica | `OsapWorkDetails.song_name` está tipado; no se ha localizado uso visual explícito en la ficha revisada | Mantener solo si es un nombre cantable/alternativo propio de la composición; no confundir con título de edición. |
| `works_subtitle` | Work o Resource | `OsapWorkDetails.subtitle`; no aparece en el render actual de `WorkPage` | Work si es subtítulo de la composición; Resource si identifica edición/versión. Muestreo antes de cerrar. |
| `works_attr_type` | Work.attribution_type | `OsapWorkDetails.attribution_type`; `WorkPage` lo presenta junto al compositor | Mantener estado de atribución de la composición; no crear personas para anónimo/tradicional/desconocido. |
| `works_attribution_note` | Work.attribution_note | `OsapWorkDetails.attribution_note`; `WorkPage` lo presenta como atribución/notas | Mantener como nota de autoría de Work. |
| `works_opus` | Work.opus | `OsapWorkDetails.opus` está tipado; uso visual actual no confirmado | Incluir en Work si identifica la composición; conservar texto original. |
| `works_catalogue` | Work.catalogue_references | `WorkInfo.catalogue`, ficha pública, `WorkPage`, SEO y lista de obras de compositor | Work; contrato debe permitir referencias estructuradas/múltiples si los datos lo requieren. |
| `works_musical_key` | Work o Resource | `OsapWorkDetails.musical_key`; `WorkPage` muestra tonalidad como dato de obra | Work solo si describe la composición; Resource si depende de transposición/edición. Mover la presentación al nivel Resource cuando corresponda. |
| `works_year` | Work.composition_year/date_text o Resource | `PublicWork.work.year`, `OsapWorkDetails.year`, `WorkPage`, SEO SSR | Solo año de composición en Work; fecha de publicación/edición/interpretación no se presenta como fecha de composición. |
| `works_epoch_id` | Work.epoch_id / relación de época | El cliente tiene catálogo `Epoch`; `WorkPage` muestra `work.epoch` como texto, no ID | Work; DTO debe exponer referencia/objeto de catálogo, no texto ambiguo si ya existe catálogo normalizado. |
| `works_duration` | Work o Resource | `OsapWorkDetails.duration`; `WorkPage` muestra duración | Work si es estimación estructural de la composición; Resource si se mide sobre interpretación/audio/edición. |
| `works_measures` | Work o Resource | `OsapWorkDetails.measures`; `WorkPage` muestra compases | Work si es estructura de composición; Resource si cambia por arreglo, corte o edición. |
| `works_pages` | Resource o File | `OsapWorkDetails.pages`; `WorkPage` lo presenta hoy como característica de la obra | No incluir en Work. Determinar si cuenta páginas del documento File o páginas de la edición Resource. |
| `works_parts` | Work o Resource | `OsapWorkDetails.parts`, `parts_names`; `WorkPage` muestra partes | Partes estructurales de la composición pueden ser Work; particellas/partes preparadas para plantilla concreta son Resource. |
| `works_complexity` | Work o Resource | `OsapWorkDetails.complexity`; `WorkPage` muestra complejidad | Definir escala y sujeto de valoración; no migrar sin muestreo. |
| `works_description` | Work o Resource | `OsapWorkDetails.description`; `WorkPage` muestra descripción | Separar descripción de la composición de notas de edición/arreglo/material. |
| `works_license` | Resource.rights.license | `OsapWorkDetails.license`; `WorkPage` la muestra hoy como dato de obra | Retirar de Work. No heredar a todos los Resources; asociar solo con evidencia al material correspondiente. |
| `works_public_domain` | Resource.rights.public_domain o revisión | `OsapWorkDetails.public_domain` está tipado; no se muestra en la ficha revisada | No exponer como booleano global de Work. Exige sujeto, jurisdicción y evidencia; desconocido permanece null. |
| `works_origin` | Federación/API o Resource.provenance | No es campo de `WorkInfo`; el detalle crudo de Storage puede devolverlo | Si identifica fuente de material incorporado, procedencia del Resource; si identifica una ficha externa, registro federado. No es autoría ni titular. |
| `works_origin_id` | Federación/API o Resource.provenance.source_record_id | No es campo de `WorkInfo`; no se consume desde la UI de Work revisada | Preservar con provider y tipo de entidad solo si es necesario para reconciliar/volver a consultar. No convertir en Work ID. |
| `works_type_file` | File.format/MIME | `OsapWorkDetails` no lo tipa como campo de Work; la UI deriva formatos desde `representations[].format` | Retirar de Work; cada File OMR tiene formato/MIME propio. Para externo, el formato pertenece a la opción de acceso/material federado. |
| `works_obra_iden` | Reconciliación/API o staging | No se ha localizado como campo de respuesta de Work | No usar como identidad canónica ni FK; resolver grupos históricos con trazabilidad. |
| `works_relative_path` | File.puntero físico interno / staging | No forma parte de `WorkInfo`; la API actual tiene lógica heredada de Storage/descarga | No exponer ni reconstruir rutas. Migrar el puntero físico existente según contrato de Storage, sin mover objetos R2. |
| `works_music_digest` | Evidencia técnica / revisión | No se ha localizado en DTO público de Work | No usar como ID, clave de deduplicación ni sustituto de checksum File. Retener solo si existe consumidor demostrado. |
| `works_key` | No migrar como identidad canónica | No se ha localizado en DTO público de Work | Solo evidencia auxiliar de reconciliación si el análisis de datos demuestra utilidad. |
| `works_voicing` | Work o Resource / relación normalizada | `SearchRequest.voices` filtra el índice/CPDL; `WorkPage` no consume un campo `voicing` explícito | Separar plantilla inherente a la composición de plantilla de edición/arreglo. No duplicar en JSON opaco. |
| `works_instrumentation` | Work o Resource / relaciones normalizadas | `PublicWork.work.instrumentation`, `OsapWorkDetails.instrumentation`, `WorkPage`, `WorkView` SEO; filtros de búsqueda | Work si es instrumentación de la composición; Resource si describe la plantilla de esa realización. El filtro federado debe indicar a qué nivel aplica. |
| marcas `created_at`, `updated_at` | Work.created_at/updated_at | `OsapWorkDetails.created_at/updated_at`; `WorkPage` muestra fechas de registro | Fechas técnicas de Work; no confundir con fecha de composición/publicación. |

## 3. Relaciones y consumidores que no se resuelven desde la fila Work

| Origen | Consumidor actual | Destino/acción V6 |
|---|---|---|
| `works_person_roles` | Compositor mostrado en búsqueda, ficha Work y páginas SEO; consulta de obras de compositor | Work.credits / composer_credits. Es autoría de la composición, no crédito de Resource. |
| `work_genres` y `genres` | `SearchRequest.genres`, filtros del índice y `OsapWorkDetails.genres`; `WorkPage` muestra géneros | Relación normalizada Work o Resource según semántica; no JSON duplicado. |
| `work_instruments`, `instruments`, `ensemble_voices` | filtros y presentación de instrumentación/partes; `WorkPage` usa `instruments` o `parts_names` | Relaciones normalizadas; decidir Work/Resource por contexto musical concreto. |
| `work_language` | `SearchRequest.language`; el tipo de detalle admite `language` | Work si es idioma inherente de la composición; Resource si corresponde a traducción/versión textual. |
| `work_tags` | `OsapWorkDetails.tags`; `ComposerWorks` añade tags; búsqueda y presentación | Clasificar etiquetas semánticamente; no migrar etiquetas de edición al Work. |
| estadísticas/contadores | ficha pública `PublicWorkStats`, vistas de popularidad y actividad | Proyección/eventos agregados; no atributos de identidad Work. |

## 4. Contrato Work: diferencias que deben cerrarse antes de congelar OpenAPI

La matriz SQL y el ejemplo de DTO de Storage V6 no están todavía alineados. El ejemplo actual de `Work` en `AI_osap-storage/docs/v6-openapi-contract.md` incluye `title`, `subtitle`, `catalogue`, `year`, `description`, `language`, `genres`, `tags`, `instruments`, `voices`, `ensembles`, `parts`, `composer_credits` y fechas; la matriz SQL añade o exige estudiar `song_name`, `attribution_type`, `attribution_note`, `opus`, `epoch_id`, `musical_key`, `duration`, `measure_count` y `complexity`.

No todos estos campos deben terminar necesariamente en Work. Pero cada uno necesita una resolución explícita: Work, Resource, relación normalizada, proyección derivada o eliminación. No se puede dar por cerrado el DTO mientras la matriz y el OpenAPI discrepen.

### Contrato de Work que debe cubrir la revisión

- Identidad: ID opaco estable.
- Denominación: título y, si se confirma su semántica, nombre cantable/alternativo y subtítulo.
- Autoría: atribución y créditos de compositor/coautores.
- Referencias catalográficas: opus y una o varias referencias de catálogo.
- Contexto temporal: año con semántica inequívoca y época normalizada.
- Clasificaciones de composición: géneros, etiquetas e idioma cuando correspondan a la obra.
- Rasgos musicales: tonalidad, compases, partes, complejidad, descripción, instrumentación/voicing solo cuando sean inherentes a la composición.
- Selección opcional de Resource de referencia, siempre hijo de la Work.
- Fechas técnicas de creación/actualización.

El contrato Work no incluye páginas de partitura, formato, licencia/dominio público del material, uploader, procedencia de proveedor, URL, ruta física, File ID ni hash usado como identidad.

## 5. Consumidores API que deben cambiar

1. `src/osap/api/platform/seo.py:osap_work_details()`: dejar de buscar Work OMR por título/compositor. Debe resolver una correspondencia persistente y tipada entre Work del índice y Work OMR; si no existe, devolver ausencia de enriquecimiento sin fingir identidad.
2. `src/osap/api/http/works.py:_merge_index_resources()`: eliminar la mezcla de materiales federados dentro de `resources` OMR y la extracción de File ID desde URLs. El detalle V6 expondrá colecciones distintas.
3. `src/osap/api/http/works.py:get_work()`: sustituir el detalle crudo heredado por el contrato Work→Resources→Files del Storage V6, o retirar la ruta administrativa si ya no tiene consumidor.
4. `src/osap/api/platform/seo.py:seo_work()` y `src/osap/api/seo/views.py:build_work_view()`: mantener la vista pública/SEO como proyección de Work federada; no presentarla como DTO canónico de Storage.
5. `web/src/api/types.ts`: separar los tipos actuales `WorkInfo`, `PublicWork`, `OsapWorkDetails` y `WorkDetailWork` de los futuros tipos canónicos `Work`, `Resource`, `File`, `ExternalMaterial` y `ProvisionalWorkGroup`. No renombrar `RepresentationInfo` mecánicamente.
6. `web/src/pages/WorkPage.tsx`: dejar de mezclar atributos de Work y de Resource. Páginas, licencia, formatos y demás datos de material deben mostrarse en la tarjeta/ficha del Resource/File correspondiente.
7. `web/src/components/WorkDetailTabs.tsx` y `web/src/state/searches.ts`: representar resultados federados con tipos de identidad explícitos; la cantidad de materiales externos no equivale al número de Resources OMR.
8. SEO SSR y JSON-LD: conservar metadatos públicos útiles, pero construirlos desde la Work canónica o desde un grupo provisional claramente identificado; no inferir que cada material externo es hijo persistido de Storage.

## 6. Riesgos de identidad detectados que afectan al DTO

- El enriquecimiento de detalle busca por título y compositor normalizados; no hay una tabla de correspondencias persistente. Una coincidencia textual no es una identidad Work.
- La ficha de Work pública procede del índice; el detalle enriquecido procede de Storage. Hoy pueden describir entidades distintas aunque coincidan en título/compositor.
- `_merge_index_resources()` mezcla resultados externos con Resources OMR y puede interpretar el último número de una URL externa como File ID.
- `RepresentationInfo` reúne candidatos de proveedores, páginas externas y materiales descargables. No equivale a Resource.
- La respuesta pública actual no ofrece una separación tipada entre Work OMR, registro externo y agrupación provisional.

Estos riesgos no se corrigen añadiendo campos al DTO: requieren resolver identidad y separar las colecciones.

## 7. Estado de cierre

| Elemento | Estado |
|---|---|
| Inventario de columnas `works` V5 | Existe en la matriz de Storage |
| Destino semántico preliminar | Existe, con varios campos pendientes de muestreo |
| Consumidores API/web verificados | Documentados aquí para el recorrido principal |
| Consumidores de importadores, SQL, informes y procesos externos | Pendientes de auditoría completa |
| Identidad persistente Work índice ↔ Work OMR | Pendiente de diseñar/validar |
| DTO Work Storage V6 alineado con matriz | Pendiente |
| Contrato federado de búsqueda/detalle API V6 | Pendiente de cerrar |
| OpenAPI 3.1 generado y probado | No ejecutado; fase documental |
| Código, esquema y producción | Sin cambios |

**Criterio de cierre:** cada columna conservada tiene semántica, destino y consumidores cubiertos; cada consumidor retirado tiene sustituto probado; el DTO Work coincide con la matriz aprobada; y el contrato federado separa Work OMR, Resources OMR, Files, materiales externos y grupos provisionales.
