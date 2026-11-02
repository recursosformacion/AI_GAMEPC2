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
