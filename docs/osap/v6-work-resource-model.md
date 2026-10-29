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

### A. Discrepancia prioritaria: baseline frente al esquema que espera el código

Se comparó infrastructure/db/migrations/001_baseline_schema.sql con scripts/migrate_representations_resources.sql y los repositorios SQL.

| Elemento | Evidencia del repositorio | Consecuencia para V6 |
|---|---|---|
| works | El baseline declara las columnas listadas en la matriz B. | Evidencia de esquema versionado, no prueba del esquema de producción. |
| representations, representation_persons, works_resources | No aparecen como tablas en 001_baseline_schema.sql. Un script separado las crea. | El baseline no reconstruye por sí solo el esquema que espera la aplicación. |
| works_resources | El script de creación declara works_resources_representation_id como NOT NULL, pero no declara works_resources_work_id. | El código consulta y escribe works_resources_work_id. Discrepancia concreta entre DDL y consumidor. |
| representations | El DDL separado no declara representations_ensemble_code ni representations_voice_signature; la entidad y el repositorio los contemplan opcionalmente. | Confirmar si existen en otra migración, son campos abandonados o dependencias sin soporte de esquema versionado. |
| Orden/reproducibilidad | El baseline y el script de creación están separados; el baseline no contiene las tablas nuevas. | V6 necesita un baseline completo y una prueba de instalación en una base vacía. No corregir el esquema desplegado durante esta fase. |

**Resultado:** el SQL versionado no es una fuente única reproducible para el bloque Work/Representation/Resource. Es un requisito de diseño y pruebas de V6, no una razón para conservar el modelo anterior.

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
| works_obra_iden | FK autorreferente e indexada. | Alias/relación de equivalencia entre obras si sigue siendo válida; si no, eliminar. | Semántica pendiente. |
| works_music_digest | Declarada en DDL; productor/lector no rastreado en esta pasada. | Dato derivado/índice o hash musical separado del File.sha256. | No confundir con checksum binario; pendiente. |
| works_voicing, works_instrumentation | DDL conserva campos JSON/texto; SqlWorkRepository deriva instrumentación y voicing desde work_instruments/work_ensembles. | Retirar copias redundantes si se demuestra cobertura; asignar plantilla a Work o Resource según alcance. | Rastrear escritores y valores no migrados. |
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
