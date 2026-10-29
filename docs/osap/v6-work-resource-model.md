# Planificación integral de OSAP V6

**Estado:** planificación abierta; no implementado.  
**Documento maestro:** se mantiene en `recursosformacion/AI_GAMEPC2` (OSAP API).  
**Alcance:** remodelación coordinada de varios repositorios. Este documento vive en API porque allí se coordina el contrato funcional y la experiencia de usuario; no significa que el modelo de datos vaya a implementarse dentro de API.

> V6 no es una migración incremental que deba conservar el esquema actual. La versión actual es la fuente de datos y el punto de partida para estudiar usos y migrar información. V6 debe arrancar con el modelo nuevo completo, los consumidores adaptados y las estructuras antiguas retiradas. Las decisiones de este documento son propuestas de trabajo, no un contrato definitivo: se pueden discutir y mejorar antes de empezar a implementar.

## 1. Objetivos y principios

1. Definir una única fuente de verdad para el catálogo musical y una identidad canónica de obra.
2. Eliminar duplicidades entre obras, ediciones/representaciones, recursos y ficheros.
3. Conservar los datos válidos, pero no conservar columnas o tablas solo porque existan o tengan consumidores actuales.
4. Cada consumidor heredado debe tener un reemplazo definido y probado antes de retirar su estructura.
5. Separar los metadatos intelectuales de la obra, los de una realización/edición concreta y los del objeto digital.
6. No confundir el estado editorial/publicación de una realización con la existencia o disponibilidad de sus bytes.
7. Permitir fuentes externas, recursos sin fichero descargado y ficheros compartidos por deduplicación.
8. Diseñar desde el principio las aportaciones de usuarios y el espacio privado de **Mi Actividad**.
9. Evitar que el índice de búsqueda, la API y Storage mantengan copias autoritativas del mismo catálogo.
10. No ejecutar migraciones ni escrituras de producción durante la fase de análisis.

## 2. Hipótesis central de modelo

La hipótesis preferida para investigar es **dos niveles musicales —Work y Resource— más File como objeto digital**, sin una tabla independiente de Representation.

```text
Work (obra musical)
  └── Resource (realización, edición, arreglo, transcripción o fuente)
        └── ResourceFile (relación)
              └── File (objeto digital, deduplicable)
                    └── StorageLocation (ubicación/copia física)
```

### 2.1 Work — obra musical

Identidad intelectual canónica de la obra, independiente de proveedor, formato de fichero, edición o índice. Contendrá únicamente atributos que describen la obra como tal y relaciones normalizadas que sean realmente comunes a ella.

Ejemplos candidatos: título canónico, subtítulo cuando proceda, personas creadoras y sus roles, catálogo/opus, época, géneros y descripción general.

No se trasladará automáticamente todo lo que hoy está en `works`: cada campo se clasificará por significado y uso demostrado.

### 2.2 Resource — realización musical concreta

Es la entidad que reúne lo que el modelo anterior repartía entre `representations` y `works_resources`. Puede describir una edición, arreglo, transcripción, partitura, versión o fuente musical, incluso cuando todavía no hay fichero disponible.

Puede tener cero, uno o varios ficheros. Un Work puede tener muchos Resources. Cada Resource pertenece a un Work canónico.

Candidatos: tipo de realización, proveedor y su identificador externo, licencia, situación de dominio público del contenido publicado, editor, fuente/nombre original, instrumentación/ensemble/voces/idioma propios de esa realización, tonalidad, duración, compases, páginas, partes, estado de publicación/disponibilidad y calidad/procedencia.

Estos campos son una propuesta; su semántica, cardinalidad y vocabulario deben fijarse en el inventario.

### 2.3 File — objeto digital

Identifica bytes concretos y sus propiedades técnicas: checksum, MIME, tamaño, nombre técnico/original si corresponde, estado de integridad y relaciones con ubicaciones de almacenamiento.

- File no es una edición ni una obra.
- El mismo File puede asociarse a más de un Resource cuando el contenido es idéntico y se deduplica.
- Un Resource puede disponer de varios Files (por ejemplo, MusicXML, PDF y MIDI).
- Las ubicaciones físicas pertenecen a File, no a Work ni a Resource.
- Una URL a la página de una edición no es lo mismo que una URL directa a un fichero. El modelo debe distinguir ambas.

Se estudiará una relación explícita `resource_files` en lugar de asumir que un único `file_id` dentro de Resource cubre todos los casos.

## 3. Criterios iniciales para los campos comentados

Estos criterios recogen las observaciones iniciales del usuario y deben validarse con los consumidores y los datos reales.

| Campo actual | Criterio inicial V6 | Trabajo pendiente |
|---|---|---|
| `works_key` | No conservarlo automáticamente en Work. Puede ser una clave técnica, un identificador de dataset o una clave natural heredada. | Rastrear escritores, lectores, unicidad, estabilidad y usos en URLs/importadores. Eliminarlo si no tiene semántica propia; si identifica un origen, moverlo al mapeo de procedencia. |
| `works_origin` | No parece un atributo intrínseco de Work: una obra puede proceder de varias fuentes. | Sustituir por una o varias correspondencias de origen; determinar si alguna fuente identifica Work o una realización concreta. |
| `works_origin_id` | No asumir que identifica globalmente una obra. | Mover al registro de correspondencia con el proveedor y asociarlo a Work o Resource según qué identifique realmente el ID externo. |
| `works_musical_key` | **Resource**, según criterio inicial del usuario. | Confirmar que representa la tonalidad de esa realización y cómo registrar la tonalidad original de la obra si hace falta. |
| `works_duration` | **Resource**, según criterio inicial del usuario. | Definir unidades, precisión y si se trata de duración interpretativa, audio o estimación musical. |
| `works_measures` | **Resource**, según criterio inicial del usuario. | Definir qué cuenta como compás y cómo tratar versiones/arreglos con diferente número de compases. |
| `works_license` | **Resource**, según criterio inicial del usuario. | Normalizar el vocabulario de licencias y guardar URL/texto de licencia y atribución cuando proceda. |
| `works_public_domain` | **Resource**, según criterio inicial del usuario. | Definir qué se evalúa (composición, edición, arreglo o fichero), país/jurisdicción y fuente de la evaluación. No inferir este valor solo por ausencia de licencia. |

Los cinco últimos campos pasan provisionalmente a Resource. No se consideran cerrados los detalles jurídicos o semánticos, pero sí son la base de trabajo solicitada para el siguiente análisis.

### 3.1 Correspondencias de origen

En lugar de repartir `origin` y `origin_id` entre varias tablas, estudiar una estructura explícita de correspondencias, por ejemplo:

- proveedor/fuente;
- tipo de entidad externa (`work` o `resource`);
- identificador externo exacto;
- ID canónico interno asociado;
- URL de origen opcional y metadatos de importación;
- fecha y estado de sincronización.

La clave única debe impedir duplicar la misma entidad externa al reimportar. Un identificador PDMX que identifica una obra podría mapear a Work; un ID de edición CPDL debe mapear a Resource. No se debe decidir por el nombre de la columna: hay que demostrar qué representa cada ID.

El `work_id` interno será estable y no dependerá de los IDs del índice, CPDL, PDMX u otro proveedor. La estrategia concreta (UUID u otro tipo) se resolverá junto con contratos, índices y URLs.

## 4. Distribución de los demás datos: borrador

| Grupo de datos actual | Destino candidato | Regla |
|---|---|---|
| Título canónico, subtítulo y descripción general | Work | Solo datos que describen la obra; conservar títulos crudos de fuentes aparte si son útiles. |
| Compositor, autor y demás roles intelectuales | Relaciones de Work con personas/roles | Reutilizar el catálogo canónico de personas; no duplicar personas como texto libre salvo para preservar la procedencia. |
| Editor de una edición | Relación de Resource con persona/rol | No atribuirlo al compositor ni a toda la obra. |
| Catálogo, opus y época | Work | Si el valor identifica la obra intelectual. |
| Géneros | Work y catálogo normalizado | Evitar copias de nombres de género en cada tabla o en JSON redundante. |
| Instrumentación, voces y ensemble | Resource cuando describan la plantilla concreta | Reutilizar catálogos y relaciones existentes; distinguir atributos explícitos de firmas derivadas. |
| Idioma | Resource cuando corresponda al texto de esa versión | Una obra puede tener versiones en varios idiomas. |
| Páginas y partes | Resource | Normalmente dependen de la edición o fichero de partitura, no de la obra abstracta. |
| Tipo/formato de fichero (PDF, MXL, MIDI…) | File | No dejar en Work una propiedad que cambia por fichero. |
| Nombre/path/estado del archivo | File o StorageLocation, según semántica | Eliminar rutas heredadas sin uso; no exponer claves físicas de almacenamiento. |
| Tamaño, MIME, checksum | File | Un único valor técnico por objeto digital. |
| Proveedor de almacenamiento y clave física | StorageLocation | Separar ubicación del objeto lógico y permitir múltiples copias. |
| Estado de revisión/publicación | Resource o flujo editorial | No mezclarlo con File disponible/no disponible. |
| Estadísticas | Agregados calculados o tablas de eventos apropiadas | No mantener múltiples contadores autoritativos sin una estrategia de actualización. |
| Thumbnails/imagenes | Revisar si son File relacionado o dato derivado | No conservar JSON/campos duplicados si se reconstruyen desde los recursos. |
| Campos vacíos, duplicados o sin consumidores | Eliminar tras verificar | La decisión se basa en evidencia, no solo en que hoy estén a NULL. |

## 5. Qué enseña el catálogo actual

Los documentos de Storage registran históricamente estos casos (las cifras son diagnósticos de septiembre de 2026, no una garantía de los valores actuales):

- **PDMX:** unos 254.035 recursos enlazados directamente a obras en el diagnóstico. El nivel de representación no aportaba una edición diferenciada en esa estructura.
- **CPDL:** unas 81.983 ediciones/representaciones, con unos 217.343 ficheros/referencias de recurso. Una obra puede tener varias ediciones y cada edición puede tener múltiples ficheros.
- Se registraron 11.242 ediciones sin recursos digitales asociados; algunas contienen licencia y editor y no deben descartarse solo por carecer de fichero.
- `archive_entries`, `cpdl_editions`, `cpdl_edition_files` y `cpdl_edition_persons` tienen o tuvieron consumidores. Su retirada requiere migrar la información y sustituir dichos consumidores; no implica conservar estas tablas en V6.
- El modelo actual admite recursos PDMX directos a Work y recursos CPDL bajo Representation. V6 debe expresar ambos casos con un único contrato coherente, sin conservar el nivel intermedio únicamente por la diferencia histórica de los proveedores.

Referencias de análisis existentes en Storage:
- `docsNew/diagnostico-representaciones-recursos.md`
- `docsNew/diseño-representaciones-recursos.md`
- `docsNew/cierre-representaciones-recursos.md`
- `docsNew/estudio-representations-vs-resources.md`

Estos documentos describen decisiones anteriores y datos históricos. Son evidencia para el inventario, no restricciones que impidan rediseñar V6.

## 6. Repositorios y límites de responsabilidad

La planificación se guarda en este repositorio (`AI_GAMEPC2` / OSAP API). La implementación afectará a más de un repositorio.

### OSAP API — coordinación y experiencia de usuario

- Contratos públicos, endpoints y modelos de respuesta.
- Búsqueda, índice/proyección, URLs, ficha de obra y descarga.
- Interfaz de catálogo y **Mi Actividad**.
- Orquestación del flujo de aportaciones, revisión y publicación.
- Cuotas y autorización desde la identidad autenticada.
- Pruebas de integración contra el contrato V6.

La API no debe convertirse en una segunda base autoritativa del catálogo.

### OSAP Storage — catálogo canónico y ficheros

- Esquema Work/Resource/File/StorageLocation y relaciones normalizadas.
- Repositorios, casos de uso, importadores y consultas del catálogo.
- Ingesta, deduplicación, checksum, almacenamiento, disponibilidad y publicación de ficheros.
- Migración de los datos históricos y reconciliación de IDs.
- Sustitución de las tablas heredadas y de sus consumidores.

### OSAP Auth

- Sigue siendo la fuente de identidad/autenticación.
- Los recursos privados deben asociarse a un identificador de propietario validado desde la identidad; no confiar en un propietario arbitrario enviado por el cliente.
- La autorización de lectura/escritura debe aplicarse en API y en cualquier acceso directo al contenido.

### Importadores y aplicaciones consumidoras

- Importadores PDMX/CPDL y otros deben escribir contra el contrato nuevo, con importación idempotente y procedencia trazable.
- Los importadores no deben crear entidades duplicadas por cada reejecución.
- Futuras integraciones (por ejemplo, AI_Guitarra/Virtuoso Tuner) deben consumir Work/Resource/File mediante contratos documentados, sin depender de tablas internas antiguas.

## 7. Mi Actividad y recursos de usuario

Mi Actividad debe diseñarse como parte del modelo V6, no añadirse después como excepción.

Requisitos funcionales iniciales:

- Solo usuarios autenticados pueden crear y gestionar sus aportaciones.
- El usuario puede seleccionar una obra existente de OSAP y asociar una realización propia, o iniciar una propuesta de obra nueva si el flujo lo permite.
- Puede subir/archivar ficheros como PDF, MusicXML y otros formatos permitidos.
- Cuota inicial objetivo: **1 GB por usuario**, con consumo calculado a partir de una regla explícita para ficheros compartidos/deduplicados.
- El contenido privado se almacena en el VPS/local privado configurado, no en R2 público por defecto.
- La clave física no se expone al cliente. Las descargas privadas se sirven a través de un endpoint autorizado o un mecanismo privado de corta duración.
- La existencia de File almacenado no implica que el Resource sea público.
- Separar propiedad, visibilidad, revisión editorial y disponibilidad del fichero.
- Una realización puede ser privada, no listada, compartida con un grupo o pública, si el modelo de permisos que se cierre contempla esos niveles.
- Al aprobar una aportación, se materializa el Resource canónico y sus relaciones; el proceso debe ser transaccional o recuperable y no dejar aceptaciones a medias.
- Los usuarios no deben poder modificar directamente la identidad de la obra, la propiedad de otros usuarios ni derechos ajenos.

Decisiones pendientes: ubicación exacta de propiedad y visibilidad en el modelo canónico; semántica de cuotas cuando un File deduplicado se comparte; retención y borrado; antivirus; límites de tamaño/MIME; flujo de revisión; qué pasa al retirar o privatizar un Resource ya publicado.

## 8. Índice, API e identidad pública

- Storage será la fuente de verdad propuesta para el catálogo canónico; debe confirmarse formalmente antes de implementar.
- El índice de búsqueda será una proyección reconstruible, no una segunda fuente autoritativa.
- Se eliminarán los IDs sintéticos de índice como identidad de negocio. Las URLs y respuestas usarán los IDs canónicos.
- El cambio de URLs debe incluir redirecciones o resolución de IDs antiguos cuando sea necesario para enlaces existentes y SEO.
- No persistir `download_url` absoluta dependiente del entorno; construir la URL a partir del contrato y la configuración de entrega.
- Definir claramente endpoints de Work, Resource, File y descarga, incluyendo qué metadatos son públicos.
- Los filtros de búsqueda se asignarán al nivel semántico adecuado: filtros de obra para Work y filtros de formato, licencia, instrumentación o disponibilidad para Resource/File según la definición final.

## 9. Inventario obligatorio antes de implementar

Se debe producir un inventario real de columnas SQL y consumidores, no solo de las clases Python.

Para cada tabla/columna se documentará:

1. Tipo, nulabilidad, valor por defecto, claves e índices.
2. Semántica real y ejemplos de valores.
3. Productores: importadores, API, procesos y administración.
4. Lectores: repositorios, consultas, endpoints, UI, buscador, descargas, informes y trabajos programados.
5. Volumen de datos, nulos, duplicados, cardinalidad y anomalías conocidas.
6. Destino V6: Work, Resource, relación, File, StorageLocation, catálogo, proyección o eliminación.
7. Transformación de datos, reglas de reconciliación y pérdidas aceptadas (idealmente ninguna para datos válidos).
8. Pruebas que demostrarán que el nuevo modelo cubre los usos antiguos.
9. Criterio para retirar la tabla/campo y todos sus consumidores.

Como mínimo se revisarán: `works`, `representations`, `representation_persons`, `works_resources`, `files`, `storage_locations`, `archives`, `archive_entries`, tablas CPDL, relaciones de personas/géneros/instrumentos/idiomas/ensembles, aportaciones, índices y migraciones.

**Atención al baseline:** los archivos de migración versionados deben reproducir el esquema objetivo de manera limpia. Se ha observado una posible discrepancia entre `001_baseline_schema.sql` y tablas que el código actual utiliza. Hay que resolverla mediante inspección de repositorio y pruebas locales; no consultar ni modificar la base de producción para inferir el esquema.

## 10. Plan de trabajo

### Fase A — Descubrimiento y diseño (ahora)

- Inventariar columnas SQL, entidades y consumidores en API, Storage, Auth e importadores.
- Clasificar campos con propuesta de destino y evidencias.
- Cerrar semántica Work/Resource/File y las correspondencias de origen.
- Definir contratos, permisos, almacenamiento privado y Mi Actividad.
- Acordar IDs, URLs, estrategia del índice y derechos/licencias.
- Documentar decisiones abiertas y criterios de aceptación.

**Salida:** esquema V6 propuesto, matriz de mapeo campo a campo, diagrama de relaciones, contratos API y plan de migración revisables antes de tocar código.

### Fase B — Punto de control y preparación de ramas

Solo cuando comience la implementación:

1. Comprobar estado real de todos los repositorios implicados y registrar los commits base.
2. Crear un tag/punto de control de la versión actual y una rama de mantenimiento para incidencias.
3. Crear la rama de desarrollo V6 en cada repositorio que deba cambiar.
4. Documentar cómo se sincronizan los contratos entre repositorios.
5. No mezclar cambios funcionales de V6 con correcciones urgentes de la versión mantenida.

No se han creado ramas ni tags en esta fase de planificación.

### Fase C — Implementación del modelo canónico

- Crear esquema nuevo y migraciones reproducibles.
- Implementar entidades, repositorios y casos de uso.
- Implementar correspondencias de proveedor e importación idempotente.
- Adaptar carga, deduplicación, almacenamiento privado y relaciones Resource–File.
- Implementar contratos API y proyección de búsqueda.

### Fase D — Migración y reconciliación

- Preparar copia de seguridad verificable y ensayo restaurable.
- Generar mapeos de Work y Resource sin fusionar obras por similitud débil.
- Migrar ediciones CPDL, recursos PDMX, personas editoras, licencias, procedencia y ficheros.
- Resolver colisiones y excepciones mediante informes revisables.
- Comparar conteos, relaciones, checksum y cobertura funcional antes/después.
- No borrar el origen hasta validar la migración en un entorno de ensayo y aprobar la liberación.

### Fase E — Consumidores y retirada del legado

- Adaptar búsqueda, ficha pública, descargas, administración, importadores y Mi Actividad.
- Eliminar adaptadores de transición si se hubieran creado.
- Retirar tablas y columnas heredadas dentro del lanzamiento V6, después de verificar que todos los consumidores han sido sustituidos.
- Actualizar documentación y contratos en todos los repositorios afectados.

### Fase F — Pruebas y liberación

- Pruebas unitarias y de integración en todos los repositorios.
- Pruebas de migración sobre copia, repetibilidad e idempotencia.
- Pruebas de autorización/privacidad, cuota, acceso a ficheros y deduplicación.
- Pruebas de búsqueda, SEO, URLs antiguas, descarga y disponibilidad.
- Plan de corte, validación, monitorización y recuperación.
- Criterios explícitos de aceptación y responsable de cada paso.

## 11. Decisiones abiertas que requieren propuesta y revisión

1. **Identidad de Work:** UUID u otro ID estable; política de alias y fusiones.
2. **Resource:** vocabulario de tipos y campos obligatorios mínimos; recurso sin fichero permitido.
3. **Procedencia:** esquema de correspondencias para IDs externos de Work y Resource.
4. **Tonalidad/duración/compases/licencia/dominio público:** se proponen en Resource siguiendo el criterio inicial del usuario; concretar semántica, validación y representación.
5. **Instrumentación, voces, idioma y ensemble:** decidir qué es atributo de Resource y qué puede heredarse/derivarse.
6. **Personas:** normalizar roles de creación de Work y roles editoriales de Resource.
7. **Archivos:** relación Resource–File múltiple y deduplicable; política para URLs externas y archivos sin descargar.
8. **Derechos:** separar licencia, atribución, estado de dominio público y autorización de redistribución.
9. **Privacidad:** propiedad, visibilidad, grupos y flujo editorial de aportaciones.
10. **Cuota:** atribución de bytes cuando un File se comparte por deduplicación.
11. **Índice y URLs:** proyección, reconstrucción, redirecciones y claves canónicas.
12. **Baseline y migraciones:** fuente reproducible del esquema completo.
13. **Retirada de legado:** orden de migración y pruebas para eliminar cada tabla/campo sin compatibilidad permanente.

## 12. Criterios de aceptación de V6

V6 no se considerará lista solo porque arranque la aplicación. Como mínimo:

- Existe una identidad canónica de Work y ninguna fuente externa o índice la sustituye.
- Un Work puede tener múltiples Resources; un Resource puede existir sin File y asociarse a varios Files.
- Los ficheros pueden deduplicarse sin perder sus relaciones de procedencia, propiedad y acceso.
- Metadatos de licencia, edición, instrumentación, tonalidad, duración y compases no se mezclan entre Work y Resource de forma ambigua.
- Todos los datos válidos de las tablas antiguas tienen destino documentado y reconciliado.
- Los importadores pueden ejecutarse repetidamente sin duplicar obras, recursos o correspondencias.
- Búsqueda, ficha pública, descargas y administración funcionan usando los contratos nuevos.
- Mi Actividad respeta identidad, propiedad, privacidad y cuota.
- No queda ningún consumidor operativo dependiendo de las tablas retiradas.
- Las migraciones pueden reproducirse desde el baseline versionado en un entorno limpio.
- Hay pruebas, informe de reconciliación, instrucciones de despliegue y procedimiento de recuperación.

---

## Referencias de trabajo

- Modelo V6 en API: este documento.
- Diseño previo de aportaciones: `docs/osap/contributions-resources-design.md`.
- Decisión de separación de DB API/Storage: `docs/osap-api-db-decision-v1.md`.
- Diagnóstico y modelo anterior de Storage: `AI_osap-storage/docsNew/diagnostico-representaciones-recursos.md`, `diseño-representaciones-recursos.md`, `cierre-representaciones-recursos.md` y `estudio-representations-vs-resources.md`.

Estas referencias sirven como historial y evidencia. La definición final se cerrará tras el inventario; V6 no queda obligada a conservar las decisiones arquitectónicas de la versión anterior.


## 9.1 Inventario inicial verificado en Storage (2026-10-29)

**Alcance:** lectura de los archivos versionados de AI_osap-storage; no se consultó la base de datos de producción. Esto describe el repositorio y el código, no certifica el esquema desplegado.

### A. Reconciliación de esquema versionado y documentación de la evolución

La primera lectura comparó infrastructure/db/migrations/001_baseline_schema.sql con scripts/migrate_representations_resources.sql. Esa comparación aislada parecía mostrar tablas ausentes y una columna que faltaba. Al ampliar la investigación a los documentos de evolución y al diagnóstico op2 del propio repositorio, **no hay base suficiente para calificarlo como error actual**: el baseline refleja una etapa del esquema, mientras que las tablas de representación/recurso se incorporaron mediante un script posterior y la aplicación evolucionó después. La documentación de diagnóstico más reciente describe works_resources_work_id como columna existente y parte del modelo op2. Por tanto, la discrepancia inicial debe tratarse como documentación/versionado histórico no actualizado, salvo que una prueba actual demuestre lo contrario.

| Observación inicial | Lectura corregida | Acción V6 |
|---|---|---|
| representations, representation_persons y works_resources no aparecen en 001_baseline_schema.sql. | El baseline no es por sí solo el historial completo de creación del bloque; existe un script posterior y documentación de migración ejecutada. | Reconstruir la secuencia real de evolución desde archivos versionados; no diagnosticar un fallo desplegado solo por omisión en el baseline. |
| works_resources_work_id no aparece en scripts/migrate_representations_resources.sql. | El diagnóstico op2 documenta recursos PDMX directos a Work y CPDL asociados a Representation; el código actual consulta work_id. El script inspeccionado corresponde a una fase anterior del modelo. | Documentar la evolución op2 y diseñar V6 desde la estructura actual confirmada por evidencia cruzada. |
| representations_ensemble_code y representations_voice_signature no aparecen en el DDL anterior. | La entidad/repositorio y la documentación evolucionaron; no se ha demostrado que sean columnas necesarias del esquema actual. | Clasificar cada campo por uso real y no añadirlo al modelo nuevo solo porque aparezca en una entidad histórica. |

No se consultó la base de datos de producción. El estado actual se determina aquí por coherencia entre documentación de migración, código y pruebas versionadas; cualquier afirmación sobre datos desplegados requerirá una consulta de solo lectura autorizada o una exportación reciente facilitada para análisis.

### B. Matriz inicial de works

Estas son las columnas declaradas por 001_baseline_schema.sql. El destino V6 es provisional y debe contrastarse con productores, lectores y datos.

| Columna actual | Evidencia/uso observado | Destino V6 propuesto | Estado |
|---|---|---|---|
| id | PK referenciada por relaciones y repositorios. | Work.id canónico; estrategia/tipo por decidir. | Conservar semántica; revisar contratos e IDs. |
| works_song_name, works_title, works_subtitle | SqlWorkRepository y consultas de obra los leen/escriben; título se usa en búsqueda/resolución. | Título canónico y subtítulo en Work; nombre crudo de proveedor en Resource/procedencia si difiere. | Separar canónico y original. |
| works_attr_type, works_attribution_note | La atribución se usa en administración y flujos de atribución. | Work y estado de atribución explícito. | Revisar junto al modelo de atribuciones V6. |
| works_opus, works_catalogue, works_year, works_epoch_id | Metadatos de catálogo/cronología. | Opus, catálogos y época en Work; definir si year significa composición, publicación u otra fecha. | Año requiere semántica. |
| works_musical_key, works_duration, works_measures | Están en DDL/entidad; SqlResolutionSource lee tonalidad desde Work. | Resource según el criterio inicial del usuario. | Adaptar resolución y contratos que hoy los leen desde Work. |
| works_pages, works_parts, works_complexity | Están en DDL/entidad; consumidores y semántica no se han completado en esta pasada. | Pages/parts provisionalmente en Resource; complexity según describa obra o realización. | Pendiente de rastreo. |
| works_description | Campo de texto general. | Work si describe la obra; notas específicas de edición a Resource. | Distinguir significado por fuente. |
| works_license, works_public_domain | DDL/entidad; SqlResolutionSource usa licencia de Work como fallback cuando falta licencia de Representation. | Resource; separar licencia de composición, edición, fichero y permiso de redistribución. | Migrar fallback y aclarar semántica legal. |
| works_origin, works_origin_id | SqlWorkRepository los persiste; administración requiere origen; resolución los usa como fallback. | Correspondencias externas Work/Resource según qué identifique cada ID. | No conservar como atributos escalares sin justificar. |
| works_key | Único en DDL; asociado históricamente a work_key; resolución usa COALESCE(representations_origin_id, works_key). | Eliminar si es clave de agrupación heredada; si es ID de fuente, mover a correspondencia externa. | Trazar todos los escritores/lectores. |
| works_type_file | El DDL lo define como formato de fichero; el diseño anterior ya proponía retirarlo de Work. | Formato de File o de relación Resource–File. | No pertenece a Work. |
| works_relative_path | DDL y entidad Work lo exponen; documento previo lo describía vacío en el conjunto PDMX analizado, dato histórico. | StorageLocation o retirar si no hay uso válido; nunca ruta autoritativa en Work. | Validar usos/datos actuales. |
| works_obra_iden | El cierre del 2026-09-19 registra 0 valores no nulos y 0 referencias funcionales en código/API/scripts. | Candidato a eliminar del esquema V6; no trasladar como relación sin necesidad nueva demostrada. | Evidencia histórica fuerte; confirmar solo si aparece una necesidad nueva. |
| works_music_digest | Declarada en DDL; productor/lector no rastreado en esta pasada. | Dato derivado/índice o hash musical separado del File.sha256. | No confundir con checksum binario; pendiente. |
| works_voicing, works_instrumentation | El código deriva instrumentación y ensembles desde relaciones normalizadas; la documentación de migración describe el reemplazo de works_voicing por relaciones. | No duplicar campos textuales heredados; conservar relaciones normalizadas y decidir Work/Resource según semántica. | Candidatos a eliminación; rastrear escritores y verificar cobertura. |
| works_created_at, works_updated_at | Auditoría técnica de fila. | Timestamps de Work. | Conservar si el modelo nuevo mantiene auditoría equivalente. |

### C. Matriz inicial de representations y representation_persons

DDL inspeccionado en scripts/migrate_representations_resources.sql:

| Columna actual | Uso/evidencia | Destino V6 propuesto | Estado |
|---|---|---|---|
| representations.id | PK usada por repositorios y CRUD. | Nueva identidad Resource o ID de transición de migración. | No conservar la identidad antigua como contrato público por inercia. |
| representations_works_id | FK obligatoria a Work; el repositorio lista por obra. | Resource.work_id obligatorio. | Conservar relación, aplanando el nivel. |
| representations_origin, representations_origin_id | Identifican entidad de origen; índice único compuesto. | Correspondencia externa de Resource cuando el origen identifica edición/realización. | No duplicar con procedencia de Work. |
| representations_origin_cpdlno | Dato auxiliar CPDL; el diseño anterior indica que no es único. | Metadato de procedencia de Resource. | No usar como identificador externo único. |
| representations_type | Tipo de edición/score/etc. | Resource.kind, separado del formato de fichero. | Normalizar vocabulario. |
| representations_source_name | Nombre crudo del origen; usado por búsqueda CRUD. | Nombre/título original de Resource o dato de procedencia. | Mantener si sirve para trazabilidad. |
| representations_license | Licencia por edición; fallback en resolución. | Licencia/atribución de Resource, separada de permisos del File. | Normalizar sin perder texto original. |
| representations_created_at, representations_updated_at | Auditoría técnica. | Auditoría de Resource si es útil. | No duplicar timestamps sin necesidad. |
| representations_ensemble_code, representations_voice_signature | La entidad/repositorio los contemplan opcionalmente, pero no aparecen en el DDL inspeccionado. | Plantilla musical normalizada o firma derivada; no guardar firma derivada como fuente de verdad. | Discrepancia de esquema por resolver. |

representation_persons contiene id, representation_persons_representation_id, representation_persons_person_id, representation_persons_role_id, representation_persons_name y representation_persons_created_at. Administración y resolución leen estas relaciones como editores de la representación. En V6 se convertirán en relaciones de Resource con personas/roles cuando corresponda; el nombre libre solo debe sobrevivir como evidencia de origen, no como sustituto permanente de la persona canónica.

### D. Matriz inicial de works_resources

DDL de scripts/migrate_representations_resources.sql frente al código consumidor:

| Columna actual | Uso/evidencia | Destino V6 propuesto | Estado |
|---|---|---|---|
| id | PK de fila de recurso y CRUD. | Resource.id será identidad musical; los ficheros se relacionan mediante tabla Resource–File. | Reconciliar identidad de fila actual durante migración. |
| works_resources_representation_id | FK obligatoria en DDL separado. | Eliminar nivel intermedio; Resource tendrá work_id. | Aplanar y reconciliar. |
| works_resources_work_id | Lo esperan SqlRepresentationRepository, SqlResourceAdminRepository y consultas de resolución; no aparece en el DDL de creación separado. | FK obligatoria Resource.work_id. | Inconsistencia prioritaria. |
| works_resources_type | Consumidores lo tratan como formato (MXL, PDF, MIDI, etc.). | Formato de File o relación Resource–File, distinto de Resource.kind. | Definir vocabulario. |
| works_resources_name | Nombre de fichero/origen; CRUD filtra por él. | Nombre original de fichero o etiqueta de Resource–File. | Separar nombre editorial y nombre técnico. |
| works_resources_relative_path | Expuesto por API antigua para descarga y leído por CRUD. | StorageLocation o retirar si es ruta heredada; no guardar ruta física en Resource. | Trazar descarga/URL antigua. |
| works_resources_status | CRUD/resolución lo leen; diagnóstico previo advertía status missing con file_id presente en archive_entries. | Estado editorial de Resource separado del estado técnico de File/StorageLocation. | Definir estados y reglas. |
| works_resources_file_id | FK opcional a File, ON DELETE SET NULL. | Relación Resource–File; permitir varios ficheros y deduplicación. | Migrar a tabla asociativa. |
| works_resources_url | URL externa; cierre previo documenta derivación de URLs CPDL. | URL externa tipada, distinguida de página de edición y descarga interna. | Conservar y clasificar. |
| works_resources_archive_id | FK opcional a Archives. | Procedencia de ingestión/importación, no ubicación final del File. | Conservar si es útil; separar de StorageLocation. |
| works_resources_created_at, works_resources_updated_at | Auditoría técnica. | Auditoría de Resource o relación Resource–File según el significado de cada fila. | Decidir al separar entidades. |

La tabla actual mezcla dos conceptos: recursos PDMX directos a Work y ficheros/referencias de ediciones CPDL. En V6 ambos deben mapear a Resource asociado a Work; bytes y URLs de descarga deben quedar en Resource–File o en una referencia externa tipada.

### E. files y storage_locations

| Tabla/columnas | Esquema versionado y código | Destino V6 propuesto | Estado |
|---|---|---|---|
| files.id | PK usada por repositorios y ubicaciones. | Identidad canónica del objeto digital. | Conservar semántica; revisar tipo de ID. |
| files.sha256 | CHAR(64), nullable, UNIQUE. La entidad exige hash para derivar la clave de almacenamiento, pero acepta None. | Hash de bytes calculado y validado en ingesta. | Decidir si File sin bytes es posible; no confundir con hash musical. |
| files.name | VARCHAR(512) NOT NULL. | Nombre técnico/original o nombre en Resource–File si un mismo File tiene nombres de origen diferentes. | Evitar que un nombre global borre procedencia. |
| files.mime_type, files.size_bytes | MIME/tamaño opcionales. | Metadatos técnicos derivados/verificados de bytes. | Conservar y validar. |
| files.status | La entidad usa registered, downloading, available, failed. | Estado de integridad/procesamiento de File. | Separar de publicación/visibilidad de Resource. |
| files.created_at, files.updated_at | Auditoría técnica. | Timestamps de File. | Conservar si son necesarios. |
| storage_locations.file_id, provider_id, object_key | DDL enlaza File y proveedor; UNIQUE(file_id, provider_id). | Copias físicas de File, fuera de Resource. | Conservar separación. |
| storage_locations.status | La entidad usa stored, failed, removed. | Estado de esa copia concreta. | No inferir disponibilidad solo del estado global de File. |

**Consumidores identificados en esta pasada:**
- infrastructure/repositories/sql_file_repository.py crea, consulta, actualiza y borra files; domain/entities/file.py define estado y clave derivada de SHA-256.
- api/routes/files.py expone registro, subida service-to-service, listado, detalle, descarga y URL. Su contrato declara que subir un File no crea Resource ni lo hace público.
- domain/entities/storage_location.py y storage_locations modelan copias físicas por proveedor.
- infrastructure/repositories/sql_representation_repository.py y application/use_cases/resource_admin.py consultan los campos actuales de Resource, incluidas las dos relaciones a Work/Representation.
- infrastructure/repositories/sql_resolution_source.py une Work, Representation y Resource, y usa licencia/ID de Work como fallback; debe adaptarse al nivel Resource.
- api/routes/works.py presenta una respuesta antigua de obra y recursos con relative_path, formato y file_id.
- application/use_cases/representation_admin.py, application/use_cases/resource_admin.py y las rutas api/routes/admin_representations.py / api/routes/admin_resources.py exponen CRUD de ambas tablas y deben sustituirse por administración de Work/Resource/File y relaciones.
- infrastructure/repositories/sql_work_repository.py lee/escribe metadatos de Work y deriva compositor, intérprete, género, instrumentación, tags, idioma y ensemble desde relaciones, aunque el DDL también declara works_voicing y works_instrumentation.

### F. Orientación de diseño derivada de la evidencia

1. Work conserva identidad intelectual y relaciones canónicas; no almacena formato ni ruta de fichero.
2. Resource representa una realización musical concreta, con work_id obligatorio; absorbe lo válido de Representation y la parte editorial de la fila antigua works_resources.
3. Resource–File debe ser una relación separada, con cardinalidad múltiple y deduplicación; una referencia externa no debe fingir que sus bytes están en Storage.
4. File representa bytes y metadatos técnicos; puede compartirse y tener varias ubicaciones.
5. Procedencia debe separar ID externo de Work del ID externo de Resource.
6. Separar revisión/publicación/visibilidad de Resource, disponibilidad técnica de File y estado de StorageLocation.
7. PDF/MXL/MIDI es el eje de formato; edition/score/arrangement/transcription es el eje de tipo musical.
8. Los campos de Work derivados desde relaciones normalizadas son candidatos a retirada, pero solo tras rastrear escrituras y comparar valores históricos.
9. V6 debe tener migraciones versionadas que creen todas las tablas y restricciones desde cero; no corregir esta discrepancia mediante cambios improvisados en la base desplegada.

### G. Siguiente bloque del inventario

Rastrear en todos los repositorios escritores y lectores de works_key, works_origin, works_origin_id, works_music_digest, works_obra_iden, works_voicing y works_instrumentation; completar archive_entries y tablas CPDL; revisar relaciones de personas/género/instrumentos/idioma/ensembles, contratos API e índice. Cada columna deberá clasificarse como **conservar**, **trasladar**, **derivar** o **eliminar**, con evidencia de productor y consumidor.


## 9.2 Corrección de interpretación y hallazgos adicionales (2026-10-29)

Esta sección corrige la lectura inicial de §9.1.A. La regla de trabajo es partir de la **situación actual del sistema**, no reconstruirla suponiendo que un archivo antiguo es el esquema entero. Las diferencias entre documentos fechados y código posterior se registran como documentación histórica desactualizada hasta que exista evidencia de un fallo vigente.

### Hallazgos con evidencia documental/código cruzada

1. **Modelo op2 actual, no jerarquía uniforme de tres niveles.** El diagnóstico de Storage de 2026-09-19 declara expresamente: PDMX usa Work → Resource y CPDL usa Work → Representation (edición) → N Resources. works_resources_work_id es parte de esa estructura; works_resources_representation_id es opcional en el modelo descrito. V6 puede decidir un modelo más uniforme, pero deberá migrar ambos casos sin perder la diferencia entre obra/recurso PDMX y edición CPDL.
2. **Tablas cpdl_editions* obsoletas como arquitectura activa.** scripts/import_cpdl_editions.py se marca [OBSOLETO] y dice que cpdl_editions, cpdl_edition_files y cpdl_edition_persons se eliminaron tras migrar a representations, works_resources y representation_persons. Algunos documentos generales aún las llaman staging/legado; se consideran documentación histórica, no prueba de que las tablas sigan activas.
3. **works_obra_iden: legado sin uso demostrado.** docsNew/works-obra-iden-cierre.md documenta 0 valores no nulos en 310.455 obras y ninguna referencia funcional en código, API o scripts. En V6 es candidato a eliminar, salvo que el diseño nuevo identifique una función de equivalencia de obras que realmente necesite esa relación.
4. **works_voicing: normalización previa realizada.** Las migraciones 007 y 008 y la documentación de fork describen el traslado de voicing a relaciones normalizadas de voices/ensembles. El código actual de SqlWorkRepository deriva el dato desde work_ensembles; no debemos reintroducir works_voicing como campo autoritativo. works_instrumentation también aparece como campo legado, mientras que la API deriva instrumentación desde work_instruments; verificar escritores antes de concluir su retirada.
5. **works_music_digest y works_key no son equivalentes.** La migración 034 explica que works_music_digest es un MD5 de notas musicales normalizadas (step/octave/duration/voice) extraídas de MusicXML, calculado por scripts/analyze_works_content.py para agrupar obras musicalmente equivalentes entre ediciones. works_key está descrito en el baseline como hash de agrupación heredado y se usó en la migración PDMX como identificador de origen. V6 debe distinguir huella musical, identidad/agrupación canónica y clave externa de proveedor. El digest es candidato a conservar como índice derivado si se confirma que siguen siendo necesarios el proceso y su uso; no es un hash de seguridad ni sustituye File.sha256.
6. **Procedencia Work vs Resource.** En la migración PDMX, representations_origin_id se rellena con works_key; para CPDL se construye como page_id:cpdlno, porque un Work puede tener múltiples ediciones. V6 necesita correspondencias externas tipadas por entidad, no una única columna genérica copiada sin criterio.
7. **archive_entries es un legado que hay que migrar con cobertura comprobada.** La documentación de la transición indica que se mantuvo intacto mientras se migraban recursos y que GetWork, la descarga e import_pdmx tenían dependencias/fallback. La situación exacta de cada fallback debe verificarse en el código vigente; en V6 no se retirará hasta sustituirlo y validar cobertura.

### Clasificación de trabajo actualizada

| Elemento | Clasificación preliminar V6 | Evidencia / siguiente comprobación |
|---|---|---|
| works_obra_iden | **Eliminar** | Cierre documentado: cero valores/consumidores; confirmar que V6 no necesita equivalencias múltiples. |
| works_voicing | **Eliminar como campo autoritativo** | Migraciones y repositorios usan relaciones normalizadas. |
| works_instrumentation | **Eliminar como copia redundante**, sujeto a validación | Lectura normalizada en work_instruments; rastrear escritores y diferencias no migradas. |
| works_key | **Trasladar o redefinir**, no eliminar a ciegas | Se usa como clave heredada de agrupación y como identificador PDMX en migración; separar semánticas. |
| works_music_digest | **Conservar como concepto solo si sigue teniendo consumidor** | Revisar migración 034 y productores/lectores; no confundir con SHA-256 de File. |
| works_origin / works_origin_id | **Trasladar a correspondencias externas**, separando Work y Resource | Los imports muestran identificadores de distinto ámbito; definir cardinalidad/unicidad por proveedor. |
| works_resources_work_id | **Conservar como relación conceptual obligatoria en Resource V6** | Modelo op2 documenta recursos PDMX directos a Work; en V6 todos los Resource tendrán Work padre. |
| works_resources_representation_id | **Eliminar como FK separada si V6 elimina Representation** | Migrar las ediciones CPDL a Resource y transferir licencia, editoría, identificador CPDL y ficheros sin pérdida. |
| representations | **Candidata a absorberse en Resource**, no eliminación mecánica | Mantiene semántica real de edición CPDL y 11.242 registros sin fichero según diagnóstico histórico; esos datos deben sobrevivir como Resources aunque no haya File. |
| archive_entries | **Retirar solo después de migrar y reemplazar consumidores** | Auditar SqlArchiveEntryRepository, import_pdmx, GetWork, descarga y cualquier fallback restante. |

### Siguiente tramo de investigación

Antes de proponer el DDL final, rastrear:
- migración 034 y referencias a works_music_digest;
- escritores/lectores de works_key, works_origin, works_origin_id, works_type_file y works_relative_path;
- relaciones de personas/roles, géneros, instrumentos, idiomas y ensembles, distinguiendo dato canónico de proyección/índice;
- endpoints y frontend que exponen recursos, URLs de descarga, edición CPDL y metadatos de licencia;
- fallback y cobertura de archive_entries.

No se ha cambiado código ni base de datos. Esta planificación se mantiene en el repositorio API como documento maestro.


### Nota de rigor sobre la evidencia

La migración 034 describe works_music_digest con una semántica concreta (MD5 de notas normalizadas, no hash de fichero). La documentación de works_obra_iden es un cierre histórico basado en una consulta de septiembre de 2026, no una consulta actual. Se usa como evidencia fuerte para el diseño, pero no como prueba de datos actuales. Del mismo modo, el diagnóstico op2 es evidencia de la estructura que se documentó tras la migración, no una lectura de producción hecha en esta revisión.



## 10. Arquitectura objetivo propuesta para cerrar el modelo V6

Esta sección convierte los hallazgos en una propuesta coherente de destino. No describe cambios ya implementados. Se parte del modelo op2 documentado en Storage y se normaliza para V6, sin exigir que el esquema nuevo reproduzca sus dos caminos heredados.

### 10.1 Modelo lógico recomendado

**Recomendación:** eliminar la entidad persistente separada `Representation` y usar un único `Resource` musical dependiente de una `Work`. Mantener `File` como identidad de bytes y una relación explícita entre Resource y File.

```text
Work
 ├── WorkPersonRole ── Person
 ├── WorkGenre ─────── Genre
 ├── WorkInstrument ── Instrument (+ cantidad/función si aplica)
 ├── WorkEnsemble ──── Ensemble ── EnsembleVoice
 ├── WorkLanguage ──── Language                 [idioma de la obra/original, si se conoce]
 ├── WorkExternalIdentifier
 └── Resource (0..N; cada Resource tiene exactamente un Work)
      ├── ResourcePersonRole ── Person          [editor, arreglista, transcriptor, etc.]
      ├── ResourceExternalIdentifier
      ├── ResourceFile ── File (0..N)
      │                  └── StorageLocation (0..N copias)
      ├── ResourceLanguage ── Language          [idioma de esta realización]
      └── ResourceEnsemble / ResourceInstrument [solo si difiere de la obra]
```

Reglas:
- `Work` identifica la obra intelectual; no es un fichero, una edición ni un formato.
- `Resource` es una realización/fuente musical concreta: edición, partitura, arreglo, transcripción, versión, interpretación publicada o fuente catalográfica. Puede existir sin ficheros, por ejemplo una edición CPDL catalogada pero no materializada.
- `ResourceFile` relaciona una realización con los ficheros que la representan. Un Resource puede tener PDF, MusicXML y MIDI; un mismo File puede compartirse si el contenido binario es idéntico.
- `File` identifica bytes por SHA-256; `StorageLocation` representa cada copia física. No guarda licencia editorial, autoría musical, publicación ni visibilidad.
- Una URL de página fuente y una URL de descarga directa son conceptos diferentes. Deben tiparse y no confundirse con un fichero almacenado.
- No introducir una entidad `Representation` adicional solo para conservar la jerarquía CPDL. Su semántica editorial se absorbe en Resource; las filas hijas actuales de `works_resources` se reinterpretan como relaciones de fichero/referencia tras auditar sus campos.
- Las relaciones opcionales de Resource a instrumento/ensemble solo se crean si la realización puede diferir de la Work; no duplicar relaciones idénticas sin razón de consulta.

### 10.2 Cómo se convierten los dos patrones actuales

| Patrón actual | Conversión propuesta |
|---|---|
| PDMX: Work → Resource directo, habitualmente un fichero MXL | Crear Resource para la realización PDMX y asociar el File mediante ResourceFile. No exigir un nivel Representation. |
| CPDL: Work → Representation (edición) → varios works_resources | Crear un Resource por edición CPDL, trasladando origen, ID de página/CPDLno, licencia, nombre fuente y roles de editor. Convertir los hijos works_resources en ResourceFile/referencias de formato, no en nuevos Resources si solo representan ficheros de esa misma edición. |
| CPDL Representation sin hijos (11.242 según diagnóstico histórico) | Crear Resource de edición sin ResourceFile. No descartarlo por no tener bytes. |
| Recurso externo que no se ha descargado | Mantener Resource y su referencia externa tipada; no crear un File ficticio. Si el registro solo expresa un formato esperado pero no una referencia real, conservarlo temporalmente como placeholder identificable y resolverlo en auditoría antes de migrar. |
| Aportación de usuario | Crear Resource ligado a Work; relacionar File(s) privados a través de ResourceFile; guardar propietario, visibilidad y estado editorial separados. |

La cardinalidad del modelo nuevo es intencionalmente más expresiva que la cardinalidad actual: Work 1:N Resource, Resource 0:N ResourceFile, File 0:N ResourceFile y File 0:N StorageLocation. No se codifica como regla universal que PDMX sea 1:1 ni que una edición tenga siempre un número concreto de ficheros.

### 10.3 Destino propuesto de los campos discutidos

| Dato heredado | Destino V6 recomendado | Justificación / condición |
|---|---|---|
| `works_musical_key` | Resource.musical_key | La tonalidad puede cambiar entre arreglos/transposiciones. Si la fuente solo conoce una tonalidad global de la obra, migrarla como valor de origen con procedencia y no fingir que aplica a todas las realizaciones. |
| `works_duration`, `works_measures`, `works_pages`, `works_parts`, `works_complexity` | Resource, con valores tipados cuando se pueda | Duración, compases, páginas, partes y dificultad pueden variar por arreglo/edición. No convertir datos ambiguos a números sin preservar el valor original. |
| `works_license` | Resource.licence assertion; si la condición solo se aplica a un fichero, a ResourceFile | La licencia debe acompañar al objeto que realmente licencia; conservar texto original, fuente y evidencia cuando no sea posible normalizar. No heredar automáticamente una licencia de Work a todos sus Resources. |
| `works_public_domain` | No trasladar ciegamente como booleano autoritativo. Convertir a una afirmación de estado legal con sujeto, jurisdicción, fecha/fuente y confianza, asociada a Work si se refiere a la composición o a Resource/ResourceFile si se refiere a edición/fichero | Dominio público de una composición y licencia de una edición/escaneo no son equivalentes. Conservar el dato legado y su procedencia mientras se determina qué significaba cada valor. |
| `works_origin`, `works_origin_id` | WorkExternalIdentifier | Solo cuando identifiquen la obra intelectual del proveedor. |
| `representations_origin`, `representations_origin_id`, `representations_origin_cpdlno` | ResourceExternalIdentifier / metadatos de procedencia | CPDL page ID y CPDLno son identificadores de ámbitos distintos; CPDLno no debe suponerse único. |
| `works_key` | Campo de migración/clave de agrupación solo si se documenta su semántica; IDs externos se trasladan a WorkExternalIdentifier | No reutilizar una clave de agrupación como identidad canónica, ni asumir que equivale a un ID de proveedor. Mantener tabla de correspondencia durante la migración. |
| `works_music_digest` | Huella musical derivada, opcional e indexable, separada de Work.id y File.sha256 | Es MD5 de notas normalizadas de MusicXML, no hash de bytes. Conservar solo si la agrupación/reconciliación musical V6 tiene un consumidor demostrado. |
| `works_type_file`, `works_resources_type` | Formato de ResourceFile mediante catálogo/valor normalizado | PDF/MXL/MIDI describe el artefacto, no el tipo musical de Resource. |
| `works_relative_path`, `works_resources_relative_path` | Eliminar como dato autoritativo; usar StorageLocation.object_key internamente y resolver URL a través del servicio | No exponer rutas físicas ni mantener rutas replicadas en Work/Resource. Antes, migrar todos los enlaces/descargas que aún dependan de ellas. |
| `works_voicing`, `works_instrumentation` | Retirar copias textuales tras validar cobertura de relaciones normalizadas | La instrumentación/ensemble canónicos están en relaciones. Una realización que difiera de la Work debe poder expresar su propia instrumentación sin duplicar el dato de Work. |
| `works_obra_iden` | Eliminar | Sin valores/consumidores según cierre histórico; no representa un mecanismo suficiente para resolver identidad/duplicados. |
| `works_song_name`, `works_title`, `works_subtitle` | Título canónico y variantes/títulos de fuente en Work, con reglas explícitas de preferencia | No fusionar automáticamente columnas solo por parecido; preservar variantes y valores crudos cuando sean evidencia de procedencia. |
| `works_year` | Work date/period con tipo de fecha y precisión | Aclarar si significa composición, publicación, edición o fecha estimada; un único entero genérico puede no bastar. |
| `works_description` | Work.description si describe la obra; Resource.description si describe edición/fuente | Clasificar por significado y origen, no por el nombre de columna. |

### 10.4 Catálogos y relaciones normalizadas

Mantener el principio de que la identidad canónica de una persona, instrumento, género, idioma o ensemble se guarda una sola vez y se conecta mediante relaciones:
- Personas y roles: reutilizar `persons`, identidades/alias e IDs externos de persona; mantener `WorkPersonRole` y `ResourcePersonRole` diferenciados para que un editor de edición no se convierta en compositor de la obra.
- Géneros y época: género principal/relaciones en Work cuando describen la obra; no duplicarlos en Resource sin evidencia de que una edición cambia la clasificación.
- Instrumentos y ensembles: Work expresa la instrumentación/plantilla conocida de la obra; Resource puede sobrescribirla o añadir una variante si el arreglo cambia la formación. Las voces se derivan del ensemble canónico y su relación de voces, no de una firma textual duplicada.
- Idioma: distinguir idioma original/de la obra y lengua de la realización, por ejemplo una traducción. La relación actual `work_language` no basta para representar ambos significados si las ediciones varían.
- Tags: conservar tags editoriales como clasificación de Work o Resource según el origen y el significado; no copiar tags de una fuente a todas las realizaciones automáticamente.
- Catálogos/opus: conservar identificadores de catálogo tipados en Work; no convertirlos en claves externas genéricas.
- Índice de búsqueda: proyección reconstruible del modelo canónico, sin propiedad exclusiva de ningún metadato.

### 10.5 Licencia, publicación, privacidad y aportaciones

Son ejes separados, no un único campo `status`:
- **Estado técnico de File:** registrado, procesando, disponible, fallido; ubicación concreta: almacenada, retirada o fallida.
- **Estado editorial de Resource:** borrador, pendiente de revisión, aceptado/publicado, rechazado, archivado, según el flujo de catálogo.
- **Visibilidad:** público, no listado, grupo, privado.
- **Propiedad:** usuario propietario mediante el ID estable de osap-auth; Storage guarda la referencia de propiedad, pero no replica credenciales ni gestiona contraseñas.
- **Licencia/atribución:** afirmación legal asociada al objeto correcto (Work, Resource o ResourceFile), con fuente; no se deduce de que sea público.
- **Acceso a bytes:** toda descarga pasa por autorización. Los objetos privados no pueden servirse desde un bucket público o URL sin control. La URL pública de un recurso no convierte en públicos todos sus ficheros.

El flujo de aportaciones de osap-api es estado operativo/orquestación; el catálogo publicado y la relación Resource–File viven en Storage. Aceptar una aportación debe materializar una operación idempotente en Storage y dejar trazabilidad. El código actual todavía documenta una limitación: el flujo de aportaciones está centrado en `target_kind=representation` y el comentario de servicio indica que la aceptación no materializa aún el catálogo. V6 deberá sustituir ese contrato por Work/Resource, no perpetuar Representation como API pública.

### 10.6 Fronteras entre repositorios

| Repositorio | Responsabilidad V6 | No debe convertirse en |
|---|---|---|
| `AI_GAMEPC2` / osap-api | API pública, orquestación, contratos de proveedores, búsqueda/UX, aportaciones como workflow, administración y proyección de catálogo | Copia autoritativa de obras, recursos o ficheros; gestor de identidad; ubicación de los bytes |
| `AI_osap-storage` | Catálogo canónico Work/Resource, relaciones, procedencia, metadatos de File, ResourceFile, ubicaciones físicas y autorización/streaming de contenido según contrato | Propietario de contraseñas/identidad ni configuración de proveedores externos que pertenece a API |
| `AI_osap-auth` | Identidad, autenticación, tokens y claves públicas/verificación | Catálogo musical o ACL duplicada con su propio modelo de recursos |
| `ai-importacion`, importadores de Storage y otros conectores | Ingesta, mapeo de origen, validación, propuesta de metadatos y ejecución de contratos versionados | Escritura directa en tablas internas ni mantenimiento de un esquema paralelo autoritativo |
| `ai_recogeYouTube` y futuros consumidores | Asociar vídeos/observaciones con Work/Resource por API estable, sin suponer Representation | Dependencia directa de tablas o IDs internos no documentados |

**Decisión de propiedad de datos:** los campos canónicos de propiedad/visibilidad/publicación de un Resource deben pertenecer a Storage porque describen el recurso del catálogo; Auth solo acredita quién es el usuario y API coordina el flujo. La base de datos de API conserva el estado operativo de aportaciones, pero no se convierte en una segunda fuente del catálogo.

### 10.7 Mi Actividad — alcance funcional inicial

1. Acceso solo a usuarios autenticados.
2. Buscar y seleccionar una Work canónica existente; crear Resource propio ligado a ella.
3. Subir uno o varios artefactos (PDF, MusicXML, MIDI y formatos admitidos), con límites configurables, validación MIME real, tamaño, hash y análisis antimalware.
4. Cuota inicial propuesta: 1 GB por usuario, calculada sobre bytes únicos o cuota lógica según una decisión explícita; la primera versión debe escoger una regla visible y no contar deduplicación de manera sorpresiva.
5. Privado por defecto. Publicación o compartición requiere acción explícita y flujo de revisión/licencia.
6. Almacenamiento privado en VPS, fuera de directorios de despliegue y fuera de buckets públicos. La capa de almacenamiento debe permitir migrar a otro proveedor sin cambiar Resource.
7. Ver, descargar, renombrar metadatos, archivar y retirar aportaciones propias con auditoría. No permitir que archivar borre un File compartido por otros Resources.
8. No duplicar catálogos de personas, géneros, instrumentos, idiomas o ensembles; enlazar los existentes.
9. Diseñar el contrato de modo que AI_Guitarra pueda consumir Resources autorizados sin acceder a tablas internas.
10. No confundir “archivar para mí” con borrar del catálogo público; la operación debe actuar sobre la aportación/visibilidad del usuario sin borrar una Work compartida.

## 11. Secuencia de migración y liberación

La migración se diseña para un esquema nuevo completo y una sustitución controlada, no para mantener indefinidamente el modelo viejo.

### Fase A — inventario congelado y punto de control (antes de escribir código)
- Congelar el estado de los repositorios implicados y registrar commits, tags y estado de despliegue.
- Crear un tag de referencia y una rama de mantenimiento de la versión actual antes de iniciar implementación; no hacerlo durante esta fase documental.
- Completar inventario de productores, consumidores, contratos HTTP, tablas, jobs, scripts, índices y rutas de descarga.
- Obtener un snapshot/export de datos autorizado y reciente para el análisis de migración; no consultar ni escribir producción desde esta planificación.
- Entregable: matriz de columna/tabla con clasificación, prueba de cobertura, responsable y plan de retirada.

### Fase B — contrato V6 y esquema canónico
- Aprobar el glosario Work, Resource, ResourceFile, File, StorageLocation, procedencia externa, estado editorial, visibilidad y licencia.
- Definir DDL íntegro y versionado desde una base vacía, constraints, índices, unicidad, soft delete/archivado y auditoría.
- Definir contratos de API versionados y errores; ningún consumidor dependerá de SQL directo.
- Definir claves estables y mapping de IDs. Preservar IDs existentes cuando no haya fusión y no rompa semántica; si hay deduplicación/fusión de Works, usar mapping explícito old_id → new_id y redirecciones de URL.
- Entregable: modelo lógico, DDL, OpenAPI/contratos, reglas de identidad y plan de compatibilidad transitoria.

### Fase C — importador y reconciliación en entorno aislado
- Crear importadores repetibles e idempotentes para Work, personas/roles, catálogos, Resources, ResourceFiles, Files, ubicaciones y procedencia.
- Importar CPDL conservando una Resource por edición, editores, licencia, IDs de origen y ediciones sin fichero.
- Importar PDMX conservando la relación Work–Resource y cada File descargable.
- Resolver `archive_entries` como fuente/fallback histórico: comparar cobertura y conflictos con Resources/File antes de retirarlo; no copiar sus metadatos de obra si ya existen en Work sin una regla de precedencia.
- Conservar valores crudos en una tabla de staging/auditoría cuando la normalización no sea segura. No descartar registros ambiguos silenciosamente.
- Entregable: informe de reconciliación, errores exportables, filas no migradas justificadas y repetición idempotente demostrada.

### Fase D — adaptación de consumidores en paralelo
- Adaptar primero Storage: entidades, repositorios, casos de uso, administración, descarga/streaming e importadores.
- Adaptar API: contratos de Work/Resource, búsqueda, detalle, enlaces, resolución, aportaciones y Mi Actividad.
- Adaptar Auth solo donde el contrato de identidad/token lo requiera; no trasladar identidad a Storage.
- Adaptar importadores y consumidores externos, incluyendo cualquier app que hoy espere `representation_id`, `works_resources_relative_path` o rutas de descarga antiguas.
- Actualizar índice y cachés como proyecciones reconstruibles.
- Entregable: matriz de consumidores con pruebas pasando contra V6 sin leer tablas legacy.

### Fase E — validación y corte
- Ejecutar migración completa sobre snapshot de ensayo; repetir desde cero y comprobar idempotencia.
- Comparar cantidades, relaciones, checksums, recuentos por origen/formato, IDs externos, recursos sin fichero, licencias, editores y descargas.
- Probar búsquedas, detalle de obra, resolución de recursos, importación, administración, autorización, cuota, subida, descarga privada/pública, archivado y restauración.
- Probar una base nueva desde cero solo con migraciones versionadas; prohibido depender de alteraciones manuales no reproducibles.
- Plan de corte con ventana, backup verificable, criterio de abortar, rollback al tag/DB actual y verificación posterior.
- Entregable: acta de validación y checklist de liberación.

### Fase F — retirada del modelo anterior
- Solo después del corte estable: eliminar tablas/campos/endpoints internos legacy, fallbacks de `archive_entries`, contratos de Representation y adaptadores temporales.
- Mantener redirecciones HTTP/IDs históricos donde sean necesarios para URLs públicas y enlaces externos, no una capa de compatibilidad de datos indefinida.
- Confirmar que ningún repositorio, script, tarea programada o frontend sigue usando el modelo antiguo.
- Entregable: prueba de ausencia de referencias, backup de archivo histórico y documentación de retirada.

## 12. Invariantes de datos y criterios de aceptación V6

1. Toda Resource pertenece a exactamente una Work.
2. Una Resource puede no tener File; no se inventa un File para una URL o un placeholder.
3. Un File almacenado tiene SHA-256 verificado, tamaño y MIME comprobados; la disponibilidad requiere al menos una StorageLocation válida.
4. Una StorageLocation no determina por sí sola la visibilidad de Resource.
5. La misma huella de fichero no implica que dos Resources sean la misma realización.
6. El mismo identificador externo puede existir en distintos proveedores; unicidad se define por proveedor + tipo de entidad + ID externo, con excepciones documentadas para IDs no únicos como CPDLno.
7. La identidad de Work no se determina exclusivamente por título, compositor, `works_key` ni digest musical.
8. Los roles de Work no se copian automáticamente a Resource ni viceversa.
9. Una licencia o afirmación de dominio público siempre tiene sujeto y procedencia; “público” como visibilidad no equivale a “dominio público” legal.
10. Los objetos privados nunca se sirven sin autorización ni desde almacenamiento público.
11. Archivar/eliminar una Resource no borra un File mientras esté referenciado por otras Resources.
12. La importación repetida no duplica Work, Resource, relaciones externas ni asociaciones ResourceFile.
13. Las proyecciones de búsqueda se pueden reconstruir desde el catálogo canónico.
14. Todas las migraciones se ejecutan desde una base vacía con artefactos versionados; las cifras finales se comparan con un snapshot actual, no con conteos de septiembre de 2026.
15. No queda consumidor en producción que requiera las tablas o contratos retirados al finalizar V6.

## 13. Registro de decisiones: propuesta por defecto

| Decisión | Propuesta por defecto | Motivo | Cuándo se considerará cerrada |
|---|---|---|---|
| Representation como entidad | Eliminar como tabla/contrato independiente y absorber en Resource | Unifica PDMX y CPDL sin perder edición como concepto | Tras probar la conversión CPDL, incluyendo recursos sin fichero y roles de editor |
| Resource vs fichero | Separar Resource y ResourceFile; File separado | La edición puede tener varios formatos y un File puede compartirse | Tras validar cardinalidades y casos de uso de importación/descarga |
| `works_key` | No llevar como identidad canónica; conservar en staging/mapping y derivar identificadores externos cuando proceda | Actualmente mezcla agrupación e identificación de origen | Tras rastrear todos sus consumidores y probar reconciliación |
| `works_music_digest` | Huella derivada opcional, no sustituto de SHA-256 | Huella musical y hash binario miden cosas distintas | Tras demostrar consumidor de agrupación musical en V6 |
| Licencia/dominio público | Afirmaciones tipadas por sujeto y procedencia; no booleano ambiguo global | Obra, edición y fichero tienen derechos distintos | Tras inventariar semántica y valores actuales |
| Instrumentación/voicing | Relaciones canónicas; override de Resource solo cuando difiere | Evita duplicidad de texto/catálogos | Tras reconciliar valores no normalizados |
| Propiedad/visibilidad | Metadatos canónicos de Resource en Storage; Auth aporta identidad; API orquesta workflow | Una sola fuente autoritativa del recurso | En contrato V6 y pruebas ACL |
| Estado de aportación | Workflow operativo en API; aceptación materializa Resource idempotente en Storage | Separa revisión del catálogo publicado | Tras pruebas de repetición y fallos parciales |
| IDs públicos | Mantener cuando no haya fusiones; tabla de mapeo/redirect para los que cambien | Reduce roturas sin conservar el esquema antiguo | Tras análisis de duplicados y URLs |
| `archive_entries` | Retirar al final, tras migrar todos los consumidores y validar cobertura | Sigue siendo legado/fallback documentado | Solo cuando pruebas y rastreo demuestren cero dependencias |

## 14. Discrepancias documentales que deben quedar resueltas

### 14.1 Fechas y cifras de CPDL
El diagnóstico de 2026-09-19 dice que los 217.343 recursos CPDL no tenían `file_id` ni `url`. El informe de migración de 2026-09-20 dice que tenían URL externa derivada. Es una diferencia temporal/documental que no puede resolverse con los documentos solos. Para V6, no afirmar que esas URLs siguen vigentes: el inventario de migración deberá verificar su forma, estado HTTP, tipo (página vs descarga directa), licencia y cobertura desde un snapshot/export reciente. Las 11.242 ediciones sin recursos son un recuento histórico, no un número garantizado hoy.
### 14.2 `works_music_digest` frente a `files.sha256`
El informe de migración propone calcular `files.sha256` y “cuando exista, eliminar `works_music_digest`”. Esa sustitución no es semánticamente válida: SHA-256 identifica bytes de un fichero; `works_music_digest` es MD5 de notas musicales normalizadas para detectar similitud musical. Solo se podrá retirar la huella musical si se demuestra que ningún proceso de reconciliación/agrupación la necesita; nunca porque se haya calculado SHA-256. La documentación de V6 debe tratar esa recomendación anterior como obsoleta o incompleta.
### 14.3 Representations vs esquema V6
El informe de migración del 2026-09-20 considera cerrado el modelo actual Work → Representation → Resource, pero el propio diagnóstico op2 documenta dos patrones distintos: PDMX directo a Work y CPDL a través de Representation. No es un error de funcionamiento por sí mismo; describe la evolución del sistema actual. La decisión V6 de absorber Representation en Resource es una propuesta de rediseño y exige la conversión explícita descrita en §10.2.
### 14.4 Tablas CPDL de staging
La documentación aún enumera `cpdl_editions*` entre las tablas heredadas, mientras que el script de importación se marca obsoleto y declara que se retiraron como arquitectura activa. Hasta revisar el esquema/uso vigente, tratarlas como artefactos históricos/staging candidatos a retirada, no como fuente canónica. La migración debe detectar si existen y si contienen datos exclusivos antes de descartarlas.

## 15. Trabajo documental pendiente antes de declarar el plan cerrado

El modelo conceptual y las fronteras de repositorio ya tienen una propuesta coherente. Para declarar la planificación **lista para implementación**, queda completar una última matriz de evidencia:
- Todos los consumidores actuales de `works_key`, `works_origin`, `works_origin_id`, `works_type_file`, `works_relative_path` y `works_music_digest`.
- Productores y lectores de `archive_entries` y rutas de descarga/URL.
- Relaciones de Work/Resource con personas, roles, idiomas, instrumentos, ensembles, géneros y tags.
- Endpoints, schemas, frontend, importadores y aplicaciones consumidoras que exponen `representation_id` o campos de ruta antiguos.
- Contrato actual de upload/streaming de Storage y configuración efectiva de almacenamiento privado, documentado sin asumir que los ejemplos de configuración son producción.
- Inventario de IDs/URLs públicos y reglas de redirects.
- Reconciliación de cifras históricas contra un snapshot autorizado y reciente, sin consultar ni modificar producción desde esta fase.

La planificación se considerará coherente cuando cada elemento de esa matriz tenga: fuente actual, productor, consumidores, decisión V6, mapeo de migración, prueba de aceptación y condición para retirar el legado. Hasta entonces el modelo propuesto es una arquitectura de destino fundamentada, pero el plan no se etiqueta todavía como “listo para implementar”.

