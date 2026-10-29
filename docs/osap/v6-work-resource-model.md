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
7. Permitir referencias externas y Resources sin File descargado; cada File representa un artefacto concreto y pertenece a un único Resource. No se propone Blob ni compartir Files entre Resources.
8. Diseñar desde el principio las aportaciones de usuarios y el espacio privado de **Mi Actividad**.
9. Evitar que el índice de búsqueda, la API y Storage mantengan copias autoritativas del mismo catálogo.
10. No ejecutar migraciones ni escrituras de producción durante la fase de análisis.

## 2. Hipótesis central de modelo

La hipótesis preferida para investigar es **dos niveles musicales —Work y Resource— más File como objeto digital**, sin una tabla independiente de Representation.

```text
Work (obra musical)
  └── Resource (realización, edición, arreglo, transcripción o fuente)
        └── File (artefacto digital lógico, pertenece a un Resource)
              └── almacenamiento propio del File (ruta o clave física)

```

### 2.1 Work — obra musical

Identidad intelectual canónica de la obra, independiente de proveedor, formato de fichero, edición o índice. Contendrá únicamente atributos que describen la obra como tal y relaciones normalizadas que sean realmente comunes a ella.

Ejemplos candidatos: título canónico, subtítulo cuando proceda, personas creadoras y sus roles, catálogo/opus, época, géneros y descripción general.

No se trasladará automáticamente todo lo que hoy está en `works`: cada campo se clasificará por significado y uso demostrado.

### 2.2 Resource — realización musical concreta

Es la entidad que reúne lo que el modelo anterior repartía entre `representations` y `works_resources`. Puede describir una edición, arreglo, transcripción, partitura, versión o fuente musical, incluso cuando todavía no hay fichero disponible.

Un Resource puede no tener ficheros o tener varios artefactos digitales de la misma realización (formatos alternativos, partes o derivados). Cada File pertenece a un único Resource. Una obra (Work) puede tener muchos Resources y cada Resource pertenece a una única obra (Work) canónica.

Candidatos: tipo de realización, proveedor y su identificador externo, licencia, situación de dominio público del contenido publicado, editor, fuente/nombre original, instrumentación/ensemble/voces/idioma propios de esa realización, tonalidad, duración, compases, páginas, partes, estado de publicación/disponibilidad y calidad/procedencia.

Estos campos son una propuesta; su semántica, cardinalidad y vocabulario deben fijarse en el inventario.

### 2.3 File — objeto digital

Identifica bytes concretos y sus propiedades técnicas: checksum, MIME, tamaño, nombre técnico/original si corresponde, estado de integridad y relaciones con ubicaciones de almacenamiento.

- File no es una edición ni una obra.
- Un File lógico pertenece a un único Resource; no se comparte entre Resources.
- Un Resource puede tener varios Files cuando representan artefactos de esa misma realización.
 - El hash, si se guarda, verifica integridad; no deduplica ni fusiona Files.
 - La referencia de almacenamiento corresponde al File; las réplicas técnicas son responsabilidad interna del servicio de almacenamiento.
- Una URL a la página de una edición no es lo mismo que una URL directa a un fichero. El modelo debe distinguir ambas.

 - No se propone una tabla de unión Resource–File ni una entidad Blob. La pertenencia se expresa mediante `files.resource_id`; cada File identifica un único artefacto y un único objeto físico.

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

La clave externa debe impedir duplicar la misma entidad de origen al reimportar, sin condicionar el modelo interno a la jerarquía del proveedor. Un identificador externo puede referirse a Work, Resource, File o a una ficha/fuente que no sea una entidad canónica; cada correspondencia se tipa tras verificar su significado.

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
- **CPDL:** el inventario histórico contiene registros de procedencia y referencias a ficheros; esas agrupaciones reflejan cómo se importó la fuente, no una estructura que V6 deba reproducir.
- Se registraron 11.242 ediciones sin recursos digitales asociados; algunas contienen licencia y editor y no deben descartarse solo por carecer de fichero.
- `archive_entries`, `cpdl_editions`, `cpdl_edition_files` y `cpdl_edition_persons` tienen o tuvieron consumidores. Su retirada requiere migrar la información y sustituir dichos consumidores; no implica conservar estas tablas en V6.
- El modelo actual agrupa datos de proveedores de formas distintas. V6 debe expresar el dominio musical con un único contrato independiente de esas estructuras; solo se conservarán las referencias externas mínimas necesarias para identificar la fuente y volver a consultar sus datos, no copias completas de sus registros.

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
- Ingesta, verificación de integridad, almacenamiento, disponibilidad y publicación de ficheros.
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
- Adaptar carga y almacenamiento privado y relaciones Resource–File.
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
- Pruebas de autorización/privacidad, cuota, acceso a ficheros y asociación exclusiva de cada objeto físico a un File.
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
7. **Archivos:** relación Resource–File 1:N; un File y un objeto físico no se comparten entre Resources; política para URLs externas y archivos sin descargar.
8. **Derechos:** separar licencia, atribución, estado de dominio público y autorización de redistribución.
9. **Privacidad:** propiedad, visibilidad, grupos y flujo editorial de aportaciones.
10. **Cuota:** atribución directa de los bytes de cada File a su propietario o Resource, sin deduplicación compartida.
11. **Índice y URLs:** proyección, reconstrucción, redirecciones y claves canónicas.
12. **Baseline y migraciones:** fuente reproducible del esquema completo.
13. **Retirada de legado:** orden de migración y pruebas para eliminar cada tabla/campo sin compatibilidad permanente.

## 12. Criterios de aceptación de V6

V6 no se considerará lista solo porque arranque la aplicación. Como mínimo:

- Existe una identidad canónica de Work y ninguna fuente externa o índice la sustituye.
 - Una obra (Work) puede tener múltiples Resources; un Resource puede existir sin Files o tener varios (PDF, MusicXML, MIDI, partes). Cada File pertenece a un único Resource y representa un único artefacto almacenado.
 - No se comparte un objeto físico entre Files. Si un artefacto aparece asociado a dos Resources, se revisa la clasificación: si es la misma realización, debe ser un único Resource; si son realizaciones distintas, cada File debe ser independiente.
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
| works_resources_file_id | FK opcional a File, ON DELETE SET NULL. | Relación Resource–File; permitir varios ficheros por Resource, sin compartir Files entre Resources. | Migrar a tabla asociativa. |
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
 - Resource–File debe tener cardinalidad 1:N, sin compartir Files ni objetos físicos entre Resources; una referencia externa no debe fingir que sus bytes están almacenados por OSAP.
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
      ├── File (0..N, cada uno pertenece a un solo Resource)
              └── almacenamiento propio del File (ruta o clave física)
      │                  └── StorageLocation (0..N copias)
      ├── ResourceLanguage ── Language          [idioma de esta realización]
      └── ResourceEnsemble / ResourceInstrument [solo si difiere de la obra]
```

Reglas:
- `Work` identifica la obra intelectual; no es un fichero, una edición ni un formato.
- `Resource` es una realización/fuente musical concreta: edición, partitura, arreglo, transcripción, versión, interpretación publicada o fuente catalográfica. Puede existir sin ficheros, por ejemplo una edición CPDL catalogada pero no materializada.
 - `File` representa un artefacto de un Resource. Un Resource puede tener PDF, MusicXML y MIDI si pertenecen a la misma realización; cada formato es un File independiente, con su propio identificador, hash de integridad opcional y ubicación.
- `File` identifica bytes por SHA-256; `StorageLocation` representa cada copia física. No guarda licencia editorial, autoría musical, publicación ni visibilidad.
- Una URL de página fuente y una URL de descarga directa son conceptos diferentes. Deben tiparse y no confundirse con un fichero almacenado.
- No introducir entidades de dominio para replicar jerarquías de proveedores. Resource describe la realización musical; solo se conservan los IDs externos y enlaces mínimos necesarios para volver a consultar la fuente. Cada registro heredado se clasifica por su significado real.
- Las relaciones opcionales de Resource a instrumento/ensemble solo se crean si la realización puede diferir de la Work; no duplicar relaciones idénticas sin razón de consulta.

### 10.2 Cómo se convierten los dos patrones actuales

| Patrón actual | Conversión propuesta |
|---|---|
| PDMX: Work → Resource directo, habitualmente un fichero MXL | Crear Resource para la realización PDMX y asociar el artefacto mediante `files.resource_id`. No exigir un nivel Representation. |
| Fuente externa con ficha que contiene varios artefactos | No copiar la jerarquía de la fuente al dominio. Clasificar cada dato como Work, Resource, File, enlace de fuente o registro de procedencia; identificar realizaciones por evidencia y marcar ambigüedades para revisión. |
| Registro externo sin fichero asociado | Crear Resource sin Files solo si la información describe una realización musical con identidad suficiente; en caso contrario conservarlo como registro de fuente/procedencia, sin inventar Resource. |
| Recurso externo que no se ha descargado | Mantener Resource y su referencia externa tipada; no crear un File ficticio. Si el registro solo expresa un formato esperado pero no una referencia real, conservarlo temporalmente como placeholder identificable y resolverlo en auditoría antes de migrar. |
| Aportación de usuario | Crear Resource ligado a Work; cada File privado pertenece a ese Resource y tiene almacenamiento propio; guardar propietario, visibilidad y estado editorial separados. |

La cardinalidad propuesta es: Work 1:N Resource; Resource 0:N File; cada File pertenece a un único Resource y representa un único artefacto almacenado. No se asume que una ficha CPDL equivalga a un único Resource.

### 10.3 Destino propuesto de los campos discutidos

| Dato heredado | Destino V6 recomendado | Justificación / condición |
|---|---|---|
| `works_musical_key` | Resource.musical_key | La tonalidad puede cambiar entre arreglos/transposiciones. Si la fuente solo conoce una tonalidad global de la obra, migrarla como valor de origen con procedencia y no fingir que aplica a todas las realizaciones. |
| `works_duration`, `works_measures`, `works_pages`, `works_parts`, `works_complexity` | Resource, con valores tipados cuando se pueda | Duración, compases, páginas, partes y dificultad pueden variar por arreglo/edición. No convertir datos ambiguos a números sin preservar el valor original. |
| `works_license` | Resource.licence assertion; si la condición solo se aplica a un artefacto, a File | La licencia debe acompañar al objeto que realmente licencia; conservar texto original, fuente y evidencia cuando no sea posible normalizar. No heredar automáticamente una licencia de Work a todos sus Resources. |
| `works_public_domain` | No trasladar ciegamente como booleano autoritativo. Convertir a una afirmación de estado legal con sujeto, jurisdicción, fecha/fuente y confianza, asociada a Work si se refiere a la composición o a Resource/File si se refiere a edición/artefacto | Dominio público de una composición y licencia de una edición/escaneo no son equivalentes. Conservar el dato legado y su procedencia mientras se determina qué significaba cada valor. |
| `works_origin`, `works_origin_id` | WorkExternalIdentifier | Solo cuando identifiquen la obra intelectual del proveedor. Ejemplo confirmado: el importador IMSLP guarda el pageid estable en Work. Para CPDL, la página identifica Work, mientras pageid:cpdlno identifica una edición/Resource. |
| `representations_origin`, `representations_origin_id`, `representations_origin_cpdlno` | Correspondencias externas tipadas y datos de procedencia | Los componentes heredados pueden identificar proveedor, ficha, agrupación o realización; determinar semántica antes de mapear. |
| `works_key` | Campo de migración/clave de agrupación solo si se documenta su semántica; IDs externos se trasladan a WorkExternalIdentifier | Se usa en SqlWorkRepository y herramientas de revisión/importación, y el migrador PDMX lo usó como ID de origen de una Representation. No reutilizarlo como identidad canónica ni asumir que equivale a un ID de proveedor. Mantener tabla de correspondencia durante la migración. |
| `works_music_digest` | Huella musical derivada, opcional e indexable, separada de Work.id y File.sha256 | Es MD5 de notas normalizadas de MusicXML, no hash de bytes. Conservar solo si la agrupación/reconciliación musical V6 tiene un consumidor demostrado. |
| `works_type_file`, `works_resources_type` | Formato de File mediante catálogo/valor normalizado | PDF/MXL/MIDI describe el artefacto, no el tipo musical de Resource. |
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
- **Licencia/atribución:** afirmación legal asociada al objeto correcto (Work, Resource o File), con fuente; no se deduce de que sea público.
- **Acceso a bytes:** toda descarga pasa por autorización. Los objetos privados no pueden servirse desde un bucket público o URL sin control. La URL pública de un recurso no convierte en públicos todos sus ficheros.

El flujo de aportaciones de osap-api es estado operativo/orquestación; el catálogo publicado y la relación Resource–File viven en Storage. El código de plataforma actual sí llama a _materialize antes de marcar una aportación como accepted y documenta idempotencia por evento. En cambio, el docstring de src/osap/application/contributions.py afirma que aceptar solo cambia el estado y que la materialización queda para un bloque posterior: ese comentario no describe el flujo de plataforma actual y debe tratarse como documentación desactualizada, no como prueba de ausencia de materialización. La limitación funcional que sí se observa es que add_resource requiere target_kind=representation y el cliente Storage consulta la representación para recuperar el Work. V6 deberá sustituir ese contrato por Work/Resource y conservar la garantía de que un fallo de Storage impide marcar accepted.

### 10.6 Fronteras entre repositorios

| Repositorio | Responsabilidad V6 | No debe convertirse en |
|---|---|---|
| `AI_GAMEPC2` / osap-api | API pública, orquestación, contratos de proveedores, búsqueda/UX, aportaciones como workflow, administración y proyección de catálogo | Copia autoritativa de obras, recursos o ficheros; gestor de identidad; ubicación de los bytes |
| `AI_osap-storage` | Catálogo canónico Work/Resource, relaciones, procedencia, metadatos de File y almacenamiento y autorización/streaming de contenido según contrato | Propietario de contraseñas/identidad ni configuración de proveedores externos que pertenece a API |
| `AI_osap-auth` | Identidad, autenticación, tokens y claves públicas/verificación | Catálogo musical o ACL duplicada con su propio modelo de recursos |
| `ai-importacion`, importadores de Storage y otros conectores | Ingesta, mapeo de origen, validación, propuesta de metadatos y ejecución de contratos versionados | Escritura directa en tablas internas ni mantenimiento de un esquema paralelo autoritativo |
| `ai_recogeYouTube` y futuros consumidores | Asociar vídeos/observaciones con Work/Resource por API estable, sin suponer Representation | Dependencia directa de tablas o IDs internos no documentados |

**Decisión de propiedad de datos:** los campos canónicos de propiedad/visibilidad/publicación de un Resource deben pertenecer a Storage porque describen el recurso del catálogo; Auth solo acredita quién es el usuario y API coordina el flujo. La base de datos de API conserva el estado operativo de aportaciones, pero no se convierte en una segunda fuente del catálogo.

### 10.7 Mi Actividad — alcance funcional inicial

1. Acceso solo a usuarios autenticados.
2. Buscar y seleccionar una obra (Work) canónica existente; crear Resource propio ligado a ella.
3. Subir uno o varios artefactos (PDF, MusicXML, MIDI y formatos admitidos), con límites configurables, validación MIME real, tamaño, hash y análisis antimalware.
4. Cuota inicial propuesta: 1 GB por usuario, calculada sumando los bytes de los Files privados del usuario, sin descuentos por deduplicación compartida.
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
- Aprobar el glosario Work, Resource, File, almacenamiento, procedencia externa, estado editorial, visibilidad y licencia.
- Definir DDL íntegro y versionado desde una base vacía, constraints, índices, unicidad, soft delete/archivado y auditoría.
- Definir contratos de API versionados y errores; ningún consumidor dependerá de SQL directo.
- Definir claves estables y mapping de IDs. Preservar IDs existentes cuando no haya fusión y no rompa semántica; si hay deduplicación/fusión de Works, usar mapping explícito old_id → new_id y redirecciones de URL.
- Entregable: modelo lógico, DDL, OpenAPI/contratos, reglas de identidad y plan de compatibilidad transitoria.

### Fase C — importador y reconciliación en entorno aislado
- Crear importadores repetibles e idempotentes para Work, personas/roles, catálogos, Resources, Files, Blobs, ubicaciones y procedencia.
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
12. La importación repetida no duplica Work, Resource, relaciones externas, Files lógicos ni Blobs.
13. Las proyecciones de búsqueda se pueden reconstruir desde el catálogo canónico.
14. Todas las migraciones se ejecutan desde una base vacía con artefactos versionados; las cifras finales se comparan con un snapshot actual, no con conteos de septiembre de 2026.
15. No queda consumidor en producción que requiera las tablas o contratos retirados al finalizar V6.

## 13. Registro de decisiones: propuesta por defecto

| Decisión | Propuesta por defecto | Motivo | Cuándo se considerará cerrada |
|---|---|---|---|
| Representation como entidad | Eliminar como tabla/contrato independiente y absorber en Resource | Unifica PDMX y CPDL sin perder edición como concepto | Tras probar la conversión CPDL, incluyendo recursos sin fichero y roles de editor |
| Resource vs fichero | Resource 1:N File mediante `files.resource_id`; cada File tiene almacenamiento propio, sin compartir objeto físico entre Files | Una realización puede tener varios artefactos; los bytes compartidos no comparten identidad/ACL lógica | Tras perfilar CPDL, formatos secundarios y referencias a hash |
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

## 16. Cierre de coherencia del diseño y matriz de consumidores (2026-10-29)

Esta sección completa el mapa entre las evidencias localizadas y las decisiones propuestas. No sustituye la validación de un snapshot reciente cuando se prepare la migración, pero sí fija una dirección arquitectónica consistente y evita que la implementación tenga que volver a decidir conceptos básicos en cada repositorio.

### 16.1 Fuentes de verdad en V6

| Concepto | Fuente de verdad | Proyecciones / datos que no deben ser autoritativos |
|---|---|---|
| Identidad y metadatos intelectuales de Work | Storage: Work + relaciones canónicas | Índice, cachés API, textos de proveedor, copias en tablas de archivo |
| Identidad externa de una Work | WorkExternalIdentifier, con proveedor y tipo de entidad | works_key como identidad global; títulos o nombres de archivo |
| Identidad de una realización | Resource + ExternalIdentifier tipado | No copiar jerarquías de proveedor ni asumir unicidad de IDs que identifican páginas o agrupaciones |
| Personas y roles de la obra | Person + WorkPersonRole | composer/artist duplicados en Work; texto de atribución como relación canónica |
| Personas y roles de la edición/recurso | Person + ResourcePersonRole | representation_persons sin migrar o nombre de editor libre como única identidad |
| Clasificación de Work | relaciones normalizadas de género, época, instrumento, ensemble, idioma y tags | works_instrumentation / works_voicing y columnas de texto duplicadas |
| Ficheros | File identificado por SHA-256 verificado cuando contiene bytes | rutas físicas en Work/Resource; nombre de fichero como identidad |
| Ubicación física | StorageLocation por File y proveedor | archive_id o relative_path como ubicación física autoritativa |
| Formato de artefacto | File + formato normalizado | works_type_file o tipo musical de Resource |
| Licencia/atribución | afirmación de licencia ligada al objeto que realmente cubre, con fuente | booleano global heredado o inferencia por visibilidad |
| Estado técnico | File / StorageLocation | estado editorial del Resource |
| Estado editorial, propiedad y visibilidad | Resource y sus metadatos de gestión en Storage | estados duplicados en API que aparenten publicar el catálogo |
| Identidad del usuario | osap-auth | copias de credenciales/usuarios en Storage |
| Workflow de aportación/revisión | estado operativo de aportación en API; la aceptación materializa Resource en Storage | contribución aceptada como sustituto permanente del registro canónico |
| Búsqueda | índice reconstruible desde Work/Resource y relaciones | una segunda copia editable del catálogo |

### 16.2 Matriz de consumidores heredados y destino V6

| Consumidor actual identificado | Dependencia actual | Adaptación V6 requerida | Criterio para retirar el legado |
|---|---|---|---|
| SqlWorkRepository y casos de uso de Work | columnas works_* y relaciones normalizadas; expone títulos, roles, géneros, instrumentos, idioma, tags y voicing | Repositorio Work V6; metadatos de edición pasan a Resource; respuestas de listas se generan desde relaciones | Tests de búsqueda/detalle y round-trip; cero lectura de columnas retiradas |
| SqlRepresentationRepository | Lee/escribe representations y works_resources, incluidos work_id y representation_id | Sustituir por repositorios Resource y File y ResourceExternalIdentifier | Ninguna entidad/puerto/SQL de Representation en los consumidores activos |
| SqlResolutionSource | Une Work, Representation y Resource; usa COALESCE de origen/ID/licencia y lee tonalidad desde Work | Resolución por Work + Resources candidatas; procedencia, licencia y tonalidad según ámbito correcto | Pruebas de resolución con PDMX, CPDL, transposición/arreglo y Resource sin fichero |
| SqlResourceAdminRepository / ResourceAdminCrud | CRUD de works_resources, rutas, estado, URL, file_id y archive_id | Administración de Resource y de sus artefactos, sin exponer rutas físicas | CRUD completo y permisos probados; rutas antiguas no requeridas |
| RepresentationAdminCrud y rutas admin de representations/resources | Exponen representation_id, licencia, origen y editoría | Sustituir por administración de Resource y roles de Resource; adaptar scopes y UI | Ningún endpoint activo requiere representation_id como identidad de negocio |
| api/routes/works.py y schemas WorkRead/WorkDetailRead/ResourceRead | Respuesta de obra con resources, relative_path, format, file_id y URL | Contrato versionado Work + Resource + artefactos; URLs emitidas por servicio de acceso, no construidas desde path | Clientes y frontend migrados; pruebas contractuales y redirects donde proceda |
| SqlArchiveEntryRepository, importador PDMX y fallback de obra/descarga | archive_entries como registro legado, ruta relativa, logical_id, file_id y metadatos de fuente | Importar todo dato exclusivo a Work/Resource/File y referencias externas mínimas; reemplazar cada fallback | Conteos y relaciones reconciliados, descarga equivalente, rastreo sin referencias activas |
| scripts/migrate_to_representations.py y herramientas de importación CPDL | Conversión actual de PDMX a Representation y CPDL a Representation + resources | Reescribir como importador V6 idempotente; CPDL debe clasificar arreglos como Resources y artefactos de cada realización como Files | Reimportación repetida sin duplicados; errores y exclusiones auditables |
| scripts/analyze_works_content.py y revisión por digest | Calcula digest musical desde MusicXML para reconciliación | Mantener como proceso derivado opcional y versionado solo si se aprueba consumidor; nunca usarlo como hash de bytes | Prueba de uso y calidad; si no hay consumidor, retirar proceso y campo tras preservar resultados necesarios |
| API de aportaciones (ContributionService, ContributionsMixin, router HTTP) | Operación add_resource dirigida a representation; estado draft/submitted/in_review/accepted/rejected; adjuntos File no públicos; review_contribution materializa primero en Storage al aceptar | Cambiar target a Work/Resource según operación; conservar materialización previa al estado accepted, idempotencia por evento y manejo de fallo parcial | Pruebas de reintento/fallo parcial, propiedad derivada de Auth y ACL de Storage |
| Cliente StorageContributionClient | Consulta admin de Representation para recuperar Work y sube File sin crear Resource | Resolver Work/Resource por contrato V6 y materializar File con operación autorizada | Ninguna llamada del cliente a rutas admin legacy |
| Frontend/API e índice | IDs y contratos actuales de obras, representaciones, URLs de recursos | Consumir API V6; reconstruir índice desde modelo canónico; mapear IDs públicos antiguos | Tests E2E, links antiguos redirigidos o con respuesta de retirada documentada |
| Importadores externos (PDMX, CPDL, IMSLP y futuros) | campos de origen en Work o Representation y formatos históricos | Adaptadores de origen a WorkExternalIdentifier/ResourceExternalIdentifier y contratos de ingesta | Ningún importador escribe directamente en tablas internas ni asume IDs de tablas |
| Aplicaciones consumidoras (incluida futura AI_Guitarra) | Posible dependencia de IDs, endpoints o estructura actual | Consumir contrato API documentado; permiso de descarga se verifica por Resource/File | Pruebas de integración sin acceso SQL directo |

### 16.3 Decisiones cerradas para el diseño de destino

Estas son decisiones de diseño propuestas por defecto para evitar bifurcaciones durante la implementación. No son afirmaciones de que el código ya las cumpla.

1. **Una sola entidad musical de realización:** Resource absorbe el significado editorial de Representation. No hay tabla/contrato permanente Representation en V6.
2. **Separación entre realización y artefacto:** Resource no es un PDF ni un MXL. File representa cada artefacto concreto y su papel/formato; File representa el artefacto digital y su almacenamiento propio.
3. **Un Work por Resource:** toda Resource tiene un Work padre obligatorio. No hay recursos musicales huérfanos.
4. **Cero o muchos artefactos:** Resource puede carecer de fichero, tener varios o compartir un File con otras Resources. La ausencia de bytes no elimina la edición catalogada.
5. **Identificadores externos tipados:** clave única por proveedor + entidad + identificador normalizado, con excepciones expresas por fuentes que no ofrezcan IDs únicos. Guardar ID crudo y URL de origen cuando ayude a auditoría.
6. **Hash binario frente a huella musical:** SHA-256 calculado sobre bytes identifica File; digest de notas normalizadas agrupa contenido musical aproximado. Ninguno sustituye la identidad canónica de Work.
7. **Metadatos con ámbito:** datos que pueden cambiar por arreglo/edición (tonalidad, duración, compases, páginas, partes, dificultad) van en Resource si su semántica corresponde a la realización. El dato heredado ambiguo se conserva con procedencia en staging hasta clasificarlo.
8. **Derechos explícitos:** licencia y dominio público se modelan con sujeto y evidencia. No inferir derechos a partir de visibilidad, origen o disponibilidad de descarga.
9. **Relaciones normalizadas como verdad:** compositor, editor, arreglista, intérprete, instrumentos, ensemble, voces, género, idioma y tags se representan mediante IDs y roles. No se guardan copias de los nombres crudos del proveedor; si no se pueden normalizar con suficiente confianza, se omiten o se dejan pendientes de revisión y se vuelven a consultar en el proveedor cuando sea necesario.
10. **Almacenamiento independiente del catálogo:** File identifica el artefacto y referencia su almacenamiento; ningún campo de Work/Resource contiene la ruta física autoritativa.
11. **Seguridad por defecto:** aportaciones privadas nacen privadas; la API no puede hacer público un objeto por el mero hecho de aceptar la aportación; Storage aplica ACL en descarga/streaming.
12. **Un solo catálogo autoritativo:** Storage conserva Work/Resource/relaciones/artefactos; API conserva workflow, configuración de proveedores y proyecciones operativas; Auth mantiene identidad.
13. **Importadores idempotentes:** proveedor + ID externo y reglas de reconciliación controlan reimportación; nunca deduplicar automáticamente dos obras solo por título o digest.
14. **Retirada de legado al final:** tablas y campos actuales solo se eliminan cuando la matriz de consumidores y las pruebas demuestren que ya no son necesarios.

### 16.4 Comprobaciones obligatorias al preparar la migración real

No son decisiones conceptuales pendientes; son verificaciones de datos que deben realizarse sobre una exportación/snapshot autorizado y reciente antes de ejecutar el importador:

- Reconciliar la diferencia documentada entre 0 URLs CPDL en el diagnóstico de 2026-09-19 y 217.343 URLs externas en el informe del 2026-09-20. Distinguir URL de página CPDL, URL de descarga y URL derivada; comprobar cobertura y respuesta sin descargar materiales protegidos indiscriminadamente.
- Verificar el estado actual de las tablas cpdl_editions*: si ya no existen, tratarlas como legado documental; si existen con datos exclusivos, migrarlos o justificar su archivo.
- Comprobar cuántas filas de works_music_digest tienen un digest válido y qué proceso/revisión lo consume hoy; no reemplazarlo con SHA-256.
- Contabilizar los valores actuales de tonalidad, duración, compases, páginas, partes, licencia y dominio público en Work y Resource. Los recuentos históricos no bastan para decidir pérdida/cobertura.
- Enumerar cada ruta HTTP pública y privada de detalle/descarga y su uso externo; definir mapeo de IDs y redirects.
- Validar la política efectiva de almacenamiento privado. Los ejemplos de configuración y los documentos de diseño no demuestran por sí solos la configuración desplegada.
- Verificar con pruebas el flujo activo de materialización de aportaciones y su idempotencia; el código de plataforma actual materializa antes de accepted, aunque el docstring de la capa de aplicación esté desactualizado. Diseñar el reemplazo V6 conservando esa garantía.
- Obtener snapshot y backup verificado; estas tareas pertenecen a la preparación de migración, no a la fase documental actual.

### 16.5 Criterio final de preparación

La arquitectura V6 ya tiene un modelo objetivo único y una dirección de migración coherente. Se podrá declarar **lista para implementación** cuando el documento de inventario tenga una fila por cada columna/tabla/contrato que se retirará, con productor, lectores, mapeo de destino y prueba; y cuando se hayan cerrado los contratos de API y el DDL reproducible desde una base vacía.

Las verificaciones de datos del §16.4 no bloquean la definición del modelo conceptual, pero sí bloquean la ejecución segura de una migración real. No se consultará ni escribirá producción desde este trabajo documental.

### 16.6 Reconciliación del flujo de aportaciones con el código vigente

La revisión directa de src/osap/api/platform/contributions.py confirma que review_contribution ejecuta _materialize antes de llamar al método review cuando la acción es accept. Si falla la materialización, no se cambia el estado a accepted. El helper declara idempotencia por evento y actualmente enruta add_resource a una representación existente; también contempla add_representation y create_work.

El docstring de src/osap/application/contributions.py, que dice que aceptar solo marca accepted y que la materialización será un bloque posterior, está desactualizado respecto de la capa de plataforma. No debe usarse para afirmar que la materialización no existe. La migración V6 debe preservar el orden de seguridad (materializar primero, aceptar después), probar reintentos y sustituir la dependencia de representation_id por contratos Work/Resource. La persistencia de las cuatro tablas de aportaciones y su estado de migración deben comprobarse mediante documentación de despliegue/snapshot antes de una liberación; el código por sí solo no demuestra que todas las tablas estén aplicadas en producción.

### 16.7 Identificadores y enlaces de origen: ejemplos comprobados

La investigación de los importadores confirma que no existe una regla única para trasladar todos los campos de origen:

- **IMSLP:** scripts/import_imslp_works.py materializa una Work con works_origin=IMSLP y works_origin_id igual al pageid estable de la obra. También conserva works_source_url como permalink a la página fuente y crea una fila de importación de compositor sin resolver. V6 debe trasladar el pageid a WorkExternalIdentifier, el permalink a un enlace de fuente de Work y la atribución sin resolver al flujo de evidencia/personas, sin inventar un Resource descargable: el importador declara que no descarga ni aloja ficheros IMSLP.
- **CPDL:** el page ID identifica la página/Work y el par page ID + cpdlno identifica una edición. cpdlno solo no es único. En V6, WorkExternalIdentifier y ResourceExternalIdentifier deben ser entidades/ámbitos distintos.
- **PDMX:** works_key se utilizó como clave de agrupación y en la migración como representations_origin_id. Antes de descartarlo, se debe guardar una correspondencia reversible que permita reimportación, reconciliación y auditoría; no asumir que representa una clave externa universal.
- **URL de origen vs URL de descarga:** works_source_url (IMSLP) enlaza la fuente catalográfica. Una URL de descarga apunta a un artefacto concreto. V6 debe distinguir SourceLink/URL de página, URL directa de descarga y File almacenado; no crear un File solo porque exista un permalink.
- **Idempotencia:** las claves de ingesta deben incluir proveedor, tipo de entidad e ID externo. La política de unicidad se define por fuente: no usar una única restricción global de origin_id ni deduplicar Work por título.

## 17. Matriz de columnas y contratos heredados: estado de cierre documental (2026-10-29)

### 17.1 Regla para interpretar esta matriz

La matriz distingue tres niveles: evidencia de código/documentación, destino propuesto y verificación pendiente. Se ha completado hasta el nivel necesario para orientar el diseño y preparar una auditoría automatizada; no se afirma que sea aún un inventario exhaustivo de cada referencia literal del monorepo o consumidor externo. El prompt de la sección 18 debe cerrar ese límite.

### 17.2 Columnas de Work (works)

| Campo actual / familia | Evidencia y uso conocido | Destino V6 | Regla de migración y retirada |
|---|---|---|---|
| id | PK de Work referenciada por roles, catálogos, índice, recursos y rutas | Work.id | Mantener si no hay fusión; mapping y redirects si cambia; nunca reutilizar ID |
| works_title, works_song_name, works_subtitle | SqlWorkRepository inserta/proyecta estos campos; importadores alimentan títulos con reglas distintas | Work.title + variantes/títulos de fuente | Definir precedencia; preservar originales y fuente; no fusionar solo por nombre |
| works_key | Usado por SqlWorkRepository y herramientas de agrupación; la documentación de migración lo describe como clave de agrupación/deduplicación; un migrador antiguo lo reutilizó como ID de origen | No es ID canónico; mapping y, si procede, ExternalIdentifier PDMX | Rastrear todos los lectores/escritores y preservar mapping reversible |
| works_origin, works_origin_id | IMSLP guarda proveedor + pageid estable en Work; CPDL usa IDs de página en un camino; PDMX tiene semántica histórica variable | WorkExternalIdentifier si identifica obra; ResourceExternalIdentifier si identifica edición | Proveedor + entidad + ID; preservar crudo, URL y colisiones; no unicidad global de origin_id |
| works_source_url | IMSLP lo define como permalink a página fuente, no como fichero alojado | Enlace de fuente asociado a Work o Resource | Distinguir URL de página, descarga directa y File almacenado |
| works_catalogue, works_opus | Proyección de catálogo/opus en repositorio y scripts de enriquecimiento | Identificadores de catálogo tipados en Work | Conservar autoridad, catálogo, valor y texto original |
| works_attr_type, works_attribution_note | Repositorio y scripts de atribución; atribución anónima/tradicional separada de identidades | Atribución explícita de Work + WorkPersonRole + auditoría | No crear Persona para anónimo/tradicional; evitar dobles verdades |
| works_musical_key | Se expone desde Work; puede variar por arreglo/transposición | Resource.musical_key por defecto | Migrar con procedencia; no copiar a todos los Resources sin evidencia |
| works_year | Campo genérico de fecha | Fecha/periodo de Work con tipo y precisión | Distinguir composición, publicación y estimación; conservar original |
| works_duration, works_measures, works_pages, works_parts, works_complexity | Campos heredados; pueden variar por edición/arreglo | Resource si describen realización; Work solo si son globales | Revisar unidad/tipo; no confundir páginas, compases y partes vocales |
| works_license, works_public_domain | Semántica insuficiente para afirmar derechos de toda realización | Afirmación de derechos con sujeto, jurisdicción, fuente, fecha y confianza | No convertir booleano en certeza legal; preservar valor crudo |
| works_relative_path | Insertado por repositorio Work; rutas/fallback legacy pueden usarlo | Eliminar de Work; ubicación en StorageLocation y relación con File | Encontrar y migrar todo lector y constructor de URL |
| works_type_file | Campo histórico de formato, pendiente de rastreo completo de consumidores | Formato normalizado del artefacto asociado a Resource | No confundir formato con tipo de realización |
| works_music_digest | MD5 de notas normalizadas MusicXML para similitud musical, no hash binario | Huella derivada opcional de reconciliación | Conservar mientras exista consumidor probado; no sustituir por SHA-256 |
| works_voicing, works_instrumentation | Textos históricos; las relaciones de ensemble/instrumento ya se usan en repositorio Work | Relaciones canónicas; override de Resource si difiere | Resolver contra catálogos; staging de texto crudo y prueba de cobertura |
| works_description y otros descriptivos | La semántica depende del origen y del sujeto descrito | Work.description o Resource.description según significado | Clasificar por contenido y procedencia |
| cachés, contadores, ranking y digests | Algunos pueden ser calculados por procesos auxiliares o índice | Proyección reconstruible o estadísticas separadas si hay requisito | Identificar productor/lector y reconstrucción antes de retirar |

### 17.3 Columnas de Representation (representations)

| Campo actual | Evidencia/uso conocido | Destino V6 | Regla de migración |
|---|---|---|---|
| id | Identificador de edición consumido por admin, resolución y aportaciones | Resource.id cuando la fila representa edición/fuente | Mapping legacy → Resource; no exponer representation_id en V6 |
| representations_works_id | FK a Work | Resource.work_id NOT NULL | Cada Resource debe tener Work; excepciones a staging, no huérfanos |
| representations_origin, representations_origin_id | PDMX usa work_key en vía histórica; CPDL usa página + cpdlno | ResourceExternalIdentifier + procedencia | Proveedor + entidad + ID; preservar componentes separados |
| representations_origin_cpdlno | Número de edición CPDL que no es único por sí solo | Identificador de Resource compuesto por página + cpdlno | Unicidad compuesta según fuente |
| representations_type | Tipo de representación/fuente | Resource.kind normalizado | No reutilizar códigos de formato PDF/MXL |
| representations_source_name | Nombre textual de edición/fuente | Resource.source_title o nombre de fuente | Conservar literal original |
| representations_license | Usado por repositorio/admin; probablemente describe edición | Afirmación de derechos de Resource/artefacto | Migrar literal y procedencia; revisar ambigüedad |
| representations_ensemble_code, representations_voice_signature | Ensemble canónico y voces tienen modelo normalizado; voice_signature es derivado | Relaciones de instrumentación de Resource solo si difiere de Work | Resolver alias; no persistir firma derivada como segunda verdad |
| created_at, updated_at | Auditoría técnica | Auditoría de Resource | Conservar timestamps si son confiables y distinguir importación/publicación |

### 17.4 Columnas de works_resources

El nombre actual es ambiguo: muchas filas representan fichero o referencia de formato, no una realización musical completa. No se conserva el nombre de tabla por inercia.

| Campo actual | Evidencia/uso conocido | Destino V6 | Regla de migración |
|---|---|---|---|
| id | PK de fila que hoy puede ser fichero/referencia | ID de asociación Resource–File o Resource solo si lo justifica la semántica | No mapear automáticamente a Resource.id |
| works_resources_work_id | Camino directo de PDMX y filas sin Representation | Resource.work_id para filas que sean realizaciones; si son artefactos, Work se deriva de Resource | Clasificar semántica por fila; no conservar doble vía |
| works_resources_representation_id | Une artefactos CPDL con edición; nulo en PDMX directo | Resource padre V6 | Eliminar jerarquía doble; asociación de artefacto apunta a Resource |
| works_resources_type | PDF, MXL, MIDI, MP3, CAPX, MUS, SIB, MSCZ y otros formatos | Formato de asociación Resource–File | Normalizar sin perder códigos desconocidos; no es tipo musical de Resource |
| works_resources_name | Nombre de artefacto/recurso | Nombre original del artefacto; título editorial vive en Resource | No usar como título canónico de Work ni identidad de File |
| works_resources_relative_path | Consumido por repositorios y posiblemente descarga/fallback | No guardar ruta física en Work/Resource; ubicación en StorageLocation | Migrar enlaces y constructores de URL antes de retirar |
| works_resources_status | Estado técnico/editorial ambiguo | Separar estado técnico de File/StorageLocation y estado editorial de Resource | Tabla explícita de correspondencia; no copiar un estado a ambos |
| works_resources_file_id | FK opcional a File | Relación Resource–File | Verificar hash/ubicaciones; no asumir ubicación activa |
| works_resources_url | Puede ser URL de página o descarga; semántica no garantizada | SourceLink o ExternalArtifactReference tipado | Distinguir página, descarga directa y URL derivada; no crear File ficticio |
| works_resources_archive_id | Referencia al archivo comprimido heredado | Procedencia/staging o ubicación de archivo si se demuestra necesaria | No trasladar automáticamente a StorageLocation |
| timestamps | Auditoría técnica | Auditoría de Resource o asociación, según semántica | Preservar en mapping si se dividen filas |

### 17.5 File, StorageLocation y archivo legado

| Entidad/campo | Destino V6 | Condición |
|---|---|---|
| files.id | File.id si se conserva el espacio de IDs | Mapping si cambia; identidad lógica por SHA-256 verificado |
| files.sha256 | SHA-256 binario de File | Verificar bytes disponibles; nunca confundir con digest musical |
| files.name, mime_type, size_bytes, status | Metadatos técnicos de File | Distinguir MIME declarado/detectado; validar al subir |
| storage_locations | Ubicación física de File por proveedor/localización | Una fila por copia física; la URL no concede permiso |
| archives, archive_entries | Fuente de migración o subsistema explícito si sigue requerido | Inventariar lectores, offsets y cobertura; retirar fallback solo tras probar equivalencia |
| archive_entries.relative_path, offset_bytes, size | Metadatos de extracción/archivo, no de Work | Migrar solo si el archivo comprimido sigue siendo fuente necesaria |
| archive_entries.logical_id, composer, title | Procedencia/staging y reconciliación | Promover solo si aporta dato no duplicado y se resuelve conflicto |

### 17.6 Relaciones normalizadas y catálogos

| Dominio actual | Destino V6 | Regla |
|---|---|---|
| works_person_roles, persons, roles | WorkPersonRole, Person, Role | Preservar rol, orden, procedencia y atribución; editor de Resource no es compositor de Work |
| representation_persons o equivalente | ResourcePersonRole | Migrar editores/arreglistas/transcriptores al ámbito correcto; nombres no resueltos son evidencia, no Personas falsas |
| work_genres, genres | WorkGenre + catálogo | Resource solo si la edición cambia clasificación |
| work_instruments, instruments | WorkInstrument + catálogo | IDs canónicos; Resource puede declarar variación del arreglo |
| work_ensembles, ensembles, ensemble_voices | WorkEnsemble y voces canónicas | No persistir voice_signature como segunda verdad |
| work_language e idiomas | WorkLanguage para idioma de la obra; ResourceLanguage para traducción/edición | Distinguir idioma original del idioma de la realización |
| tags | WorkTag o ResourceTag según sujeto | No copiar tags de proveedor a todas las ediciones |
| época, catálogo y opus | Relaciones/identificadores tipados | No guardar IDs de catálogo como texto ambiguo si se puede normalizar sin pérdida |

### 17.7 Contratos, productores y consumidores

| Productor/consumidor localizado | Dependencia actual | Cambio V6 | Prueba de retirada |
|---|---|---|---|
| SqlWorkRepository | SQL sobre works; deriva compositor/intérprete/género/instrumentación/tags desde relaciones | Repositorio Work V6 | Lectura/escritura, listados y detalle sin columnas legacy |
| SqlRepresentationRepository | Traduce representations y works_resources a dos dataclasses; Resource permite work_id o representation_id | Repositorios Work/Resource/File/Blob | Cero SQL o símbolos legacy en consumidores activos |
| SqlResolutionSource | Combina origen, ID, licencia, tonalidad y relaciones | Resolver Work + Resource + identificadores externos tipados | PDMX, CPDL, IMSLP, varias ediciones y sin fichero |
| SqlResourceAdminRepository y SqlArchiveEntryRepository | CRUD/fallback con rutas, URL, file_id, archive_id y relative_path | Administración y descarga por servicio autorizado | ACL, descarga, archivo y ausencia de fallback |
| RepresentationAdminCrud, ResourceAdminCrud y rutas admin | IDs/campos representation_id, licencia, origen, ruta y file_id | API V6 Work/Resource/File con permisos | Pruebas contractuales/scopes; sin dependencia de representation_id |
| api/routes/works.py y schemas WorkRead/WorkDetailRead/ResourceRead | Serializan resources, relative_path, formato, file_id y URL | DTO V6 sin rutas físicas; URLs por servicio de acceso | Tests contractuales, enlaces y redirects |
| Importadores PDMX, CPDL e IMSLP | Mapean origen de formas distintas; algunos escriben directamente en tablas | Adaptadores idempotentes con contratos de ingesta V6 | Reimportación sin duplicados y conflictos auditables |
| scripts/analyze_works_content.py y works_music_digest | Digest musical para comparación/reconciliación | Proceso derivado optativo | Demostrar consumidor antes de retirar |
| ContributionService, ContributionsMixin y StorageContributionClient | Aportación a representation; plataforma materializa antes de accepted | Workflow API + materialización idempotente de Resource y relación de File en Storage | Reintento/fallo parcial; accepted implica materialización completa |
| Frontend, búsqueda e índice | IDs de obra/recurso, títulos, URLs y esquema actual | Contrato V6 e índice reconstruible | E2E, redirects y reconstrucción |
| ai_recogeYouTube, futura AI_Guitarra y consumidores | Riesgo de dependencia de IDs/estructura actual | API pública estable, sin SQL interno | Pruebas de integración |
| osap-auth | Identidad y tokens | Mantener identidad fuera del catálogo; Storage solo guarda ID estable del propietario | Tests de token y ACL |

### 17.8 Condiciones de retirada por grupo

1. **Work:** no quedan consumidores de works_key, works_origin, works_origin_id, rutas ni columnas duplicadas; todo ID externo está mapeado.
2. **Representation:** cada fila tiene Resource destino o exclusión justificada; editores/licencia/procedencia reconciliados; volver a contar con snapshot reciente las filas sin fichero históricamente reportadas.
3. **works_resources:** cada fila se clasifica como Resource, asociación de fichero, referencia externa o inválida; no se pierde una edición al convertir varios hijos.
4. **File/ubicación:** hashes y tamaños se verifican donde hay bytes; ubicaciones activas se distinguen de huérfanos; deduplicar no elimina asociaciones.
5. **archive_entries:** todos los lectores/fallbacks sustituidos y descarga probada desde V6.
6. **Relaciones:** cada vínculo tiene catálogo destino y tratamiento de valores sin resolver; textos se retiran solo con métricas de cobertura.
7. **API/frontend/importadores:** no hay contrato activo que exija columnas/IDs legacy; enlaces externos tienen mapping/redirect.
8. **Aportaciones/privacidad:** aceptación, propiedad, visibilidad, cuota, descarga privada y archivo probados en Storage V6.

## 18. Prompt para auditoría de desarrollo antes de declarar V6 lista para implementar

La matriz §17 es el inventario documental inicial. El programador debe ejecutar esta auditoría **en modo lectura**, desde las copias locales actuales de los repositorios, para descubrir consumidores omitidos y discrepancias entre documentos y código. No se solicita implementar V6 ni corregir el código actual.

Copiar y entregar al programador el prompt siguiente:

---

### PROMPT DE AUDITORÍA OSAP V6 — SOLO INVESTIGACIÓN, CERO CAMBIOS

Actúa como auditor técnico de los repositorios actuales de OSAP y prepara evidencia para cerrar la planificación de V6.

**Restricción absoluta:** no modifiques ningún archivo, código, configuración, migración, base de datos, rama, tag ni commit. No hagas escrituras en producción ni ejecutes importadores, migradores, jobs, scripts de reparación o pruebas que puedan modificar datos. No instales dependencias. No hagas commit. Puedes ejecutar búsquedas estáticas y pruebas existentes únicamente si demuestras que son locales, aisladas y no destructivas. Si no puedes garantizarlo, no ejecutes la prueba y anota la limitación. No muestres secretos, tokens, contraseñas ni valores de configuración sensibles.

#### Repositorios que debes revisar

- AI_GAMEPC2 (osap-api).
- AI_osap-storage.
- AI_osap-auth.
- ai-importacion.
- ai_recogeYouTube y otros repositorios consumidores que estén presentes localmente o estén declarados como dependencias.

No des por hecho que las copias locales están sincronizadas con GitHub. Registra para cada repo la ruta, branch, commit HEAD, estado de git (limpio/sucio) y si hay cambios locales preexistentes. No cambies de branch ni hagas fetch/pull que altere el workspace. Si un repo no está disponible, decláralo.

#### A. Inventario de esquema SQL real versionado

1. Localiza todas las definiciones SQL y ORM de las tablas actuales relevantes: works, representations, works_resources, files, storage_locations, archives, archive_entries, tablas de relaciones de personas/roles, géneros, instrumentos, ensembles/voces, idiomas, tags, identificadores, estadísticas y aportaciones.
2. Para cada tabla, recoge todas las columnas, tipo, nullabilidad, default, PK/FK, unique keys e índices de los artefactos versionados. Distingue el esquema activo del esquema legacy, staging y snapshots/dumps.
3. Compara el DDL con entidades de dominio, repositorios, schemas/DTOs y consultas SQL. Señala columnas leídas/escritas por código pero ausentes del baseline versionado, y columnas del baseline sin consumidor localizado.
4. No conectes a ninguna base de datos, ni siquiera una llamada que pueda cambiar estado. Si existe un dump local ya disponible, solo úsalo si su origen está documentado y el acceso es de solo lectura; no lo presentes como producción sin evidencia.

#### B. Matriz exhaustiva de columnas

Para cada columna de works, representations, works_resources, files, storage_locations, archives y archive_entries, produce una fila con:

- repositorio/ruta y tabla.columna;
- definición SQL encontrada y versión/esquema al que pertenece;
- productores (INSERT, UPDATE, importer, endpoint, admin, job);
- lectores (SELECT, join, serializador, frontend, descarga, indexador, consumidor externo);
- evidencia precisa (archivo y línea, o símbolo y consulta);
- semántica demostrada y nivel de certeza;
- propuesta de destino V6: Work, Resource, relación Resource–File, File, StorageLocation, identificador externo, catálogo/relación normalizada, staging/auditoría, proyección reconstruible o retirar;
- transformación de migración, tratamiento de nulos/valores inválidos/duplicados;
- prueba de aceptación;
- consumidores que deben cambiar antes de retirar;
- criterio verificable de retirada.

No concluyas que un campo está muerto por no encontrarlo en una búsqueda simple. Busca también SQL dinámico, strings construidos, schemas, frontend, scripts, jobs y tests.

#### C. Grafo de consumidores y contratos

Rastrea referencias directas e indirectas a:
- works_key, works_origin, works_origin_id, works_source_url, works_relative_path, works_type_file, works_music_digest, works_musical_key, works_duration, works_measures, works_pages, works_parts, works_complexity, works_license, works_public_domain, works_voicing e instrumentation;
- representations_id y todos los campos representations_*;
- works_resources_* (en especial work_id, representation_id, type, name, relative_path, status, file_id, url y archive_id);
- files.sha256, mime_type, size_bytes, status y storage_locations;
- archive_entries, archive_id, logical_id, relative_path, offset_bytes y cualquier fallback de descarga;
- representation_id en contratos HTTP, API, frontend, importadores y aportaciones.

Para cada endpoint y contrato, identifica productor, consumidor, esquema de request/response, auth/scope, URL pública y compatibilidad requerida. Distingue las APIs públicas de las rutas admin/internas. Localiza URLs de descarga que se construyan a partir de rutas físicas.

#### D. Casos de dominio que deben quedar demostrados

Evalúa, con ejemplos de datos de fixtures/tests o trazado de código (no producción), cómo se representa cada caso:
1. Una Work sin Resource.
2. Un Resource de edición sin fichero.
3. Un Resource con PDF, MusicXML y MIDI.
4. Un File idéntico compartido por dos Resources.
5. PDMX actual: recursos directos a Work.
6. CPDL: edición con varios ficheros, edición sin fichero y múltiples ediciones de una Work.
7. IMSLP: página fuente sin descarga alojada.
8. URL externa de página frente a URL directa de descarga y File almacenado.
9. Un Resource que modifica la tonalidad/instrumentación respecto de Work.
10. Editor/arreglista de Resource frente a compositor de Work.
11. licencia de Work, licencia de edición y licencia de fichero; visibilidad privada frente a dominio público.
12. Resource privado de usuario, cuota, autorización de descarga, archivado y File compartido.
13. Aportación aceptada, error de Storage durante aceptación, reintento idempotente y fallo parcial.
14. Identificadores externos duplicados o no únicos, especialmente CPDLno.
15. Fusión de Works y redirección de IDs/URLs antiguos.

Por caso, indica si está soportado actualmente, dónde, evidencia, riesgos y comportamiento V6 que necesita una prueba.

#### E. Auditoría del flujo de aportaciones y almacenamiento

Lee el código actual, no solo docstrings. Confirma el orden real entre materialización en Storage y transición a accepted, idempotencia, reintentos y operaciones soportadas. Localiza la migración de las tablas de aportaciones y determina únicamente desde los archivos disponibles si está preparada, aplicada en tests o no hay evidencia suficiente de aplicación en producción.

Localiza todas las rutas de upload, download, streaming, autorización y almacenamiento físico. Distingue código, configuración de ejemplo y configuración efectiva. No leas ni expongas secretos. No afirmes que el almacenamiento privado está correctamente configurado solo porque exista un ejemplo.

#### F. Evaluación de ResourceFile

No des por obligatoria una entidad de dominio llamada ResourceFile. Compara y evalúa:
- A) Resource.file_id (uno a uno/uno a muchos limitado);
- B) tabla de unión Resource–File muchos a muchos con atributos propios;
- C) tabla de unión mínima sin entidad de dominio independiente.

Comprueba si el código y los casos de uso requieren que un Resource tenga múltiples ficheros, que un File se comparta, que un artefacto tenga formato/papel/orden/atribución propia o que exista una referencia externa sin bytes. Recomienda la alternativa mínima que cubra los casos reales y separa la decisión física de tabla SQL de la decisión de modelo de dominio.

#### G. Discrepancias y errores actuales

Señala por separado:
- errores reales del código/esquema actual, con evidencia reproducible;
- documentación obsoleta o contradictoria;
- incertidumbres que no pueden resolverse sin datos actuales;
- propuestas de rediseño V6 que no deben describirse como bugs actuales.

No corrijas ninguno de esos problemas durante esta auditoría.

#### H. Entregables

Devuelve:
1. Resumen ejecutivo y conclusión: ¿plan V6 listo para implementación? Sí/no, con razones.
2. Tabla de estado de cada repositorio (HEAD, branch, dirty).
3. Inventario DDL completo con separación actual/legacy/staging.
4. Matriz de columnas completa en CSV o Markdown, sin omitir columnas porque parezcan obvias.
5. Grafo/lista de productores y consumidores por tabla/campo y contratos API.
6. Lista priorizada de discrepancias, errores y documentación obsoleta, con ruta y líneas.
7. Evaluación de ResourceFile A/B/C y recomendación.
8. Lista de decisiones de modelo aún abiertas; para cada una, recomendación por defecto.
9. Pruebas existentes ejecutadas y resultado; cualquier prueba no ejecutada y por qué.
10. Plan de migración por lotes, reconciliación de datos, mapping de IDs y criterios de rollback, sin ejecutar migración.
11. Lista concreta de cambios documentales necesarios en docs/osap/v6-work-resource-model.md.
12. Prompt/órdenes de seguimiento solo si falta evidencia imprescindible.

No uses conteos históricos como cifras actuales. No inventes resultados de producción. No declares “sin consumidores” sin describir el método de búsqueda y sus límites. Cita rutas y líneas para que otra persona pueda reproducir cada conclusión.

**Final obligatorio:** confirma explícitamente que no has modificado ningún archivo, base de datos, rama, tag ni commit.

---

## 19. Modelo Resource–File y decisión de cardinalidad (2026-10-29)

Esta sección fija el criterio de V6: **no se introduce una entidad Blob ni se comparte un objeto físico entre Files**. La relación conceptual es Work 1:N Resource; Resource 0:N File; cada File pertenece a un único Resource y representa un único artefacto almacenado.

```text
Work (obra)
  └── Resource (realización musical)
        ├── File (PDF)
        ├── File (MusicXML)
        └── File (MIDI)
```

- **Resource** describe una realización musical; no es un formato de fichero. Puede existir sin ficheros y puede reunir varios artefactos de esa misma realización.
- **File** es la identidad del artefacto concreto, con nombre, formato, estado, tamaño, hash de integridad si se necesita y referencia al objeto físico almacenado.
- **Un objeto físico solo puede estar asociado a un File.** No hay una tabla de unión `ResourceFile` ni una relación M:N.
- Si el mismo PDF parece corresponder a dos Resources, no se comparte el objeto mediante dos Files. Se revisa si se han creado dos Resources para una misma realización; si son realizaciones distintas, cada una tendrá su propio File y objeto físico, aunque los bytes coincidan.
- Los arreglistas, editores y demás personas se registran mediante las relaciones de personas y roles correspondientes al objeto musical correcto. La presencia de varias personas no justifica duplicar Resources ni compartir un File entre ellos.
- SHA-256, si se conserva, se utiliza para verificar integridad y detectar alteraciones; no define la identidad de File ni fuerza una deduplicación. La restricción `UNIQUE` existente en `files.sha256` debe revisarse en el diseño V6.
- Las ubicaciones, réplicas y copias de seguridad físicas son responsabilidad del servicio de almacenamiento. No justifican por sí mismas una entidad de catálogo Blob.

La decisión evita complejidad de deduplicación, permisos y cuotas. Antes del DDL se comprobarán los consumidores actuales de `files.sha256` y `storage_locations` para decidir qué campos y servicios de almacenamiento se mantienen. No se cambiará el modelo por una supuesta optimización de bytes sin evidencia y necesidad operativa.

## 20. Modelo canónico independiente de proveedores (criterio rector V6, 2026-10-29)

Esta sección establece un principio de arquitectura que prevalece sobre cualquier ejemplo de migración que describa la estructura de CPDL, PDMX, IMSLP u otro proveedor como si fuese el modelo interno. **Un proveedor externo aporta datos; no define las entidades ni las cardinalidades de OSAP.** CPDL debe tratarse como una fuente de información entre varias, no como plantilla del catálogo.

El objetivo es diseñar primero un esquema de dominio musical coherente e importar únicamente los datos que OSAP necesita, normalizados en sus propias tablas. No se conservarán copias completas de registros externos, payloads ni snapshots históricos. Se mantendrá solo la referencia mínima necesaria para identificar y volver a consultar el registro del proveedor. No se crearán entidades internas solo para imitar páginas, ediciones, números o agrupaciones particulares de un proveedor.

### 20.1 Tablas de dominio propuestas

El conjunto siguiente es la propuesta conceptual inicial para precisar con la auditoría; los nombres y tipos SQL definitivos requieren contrastar todos los productores y consumidores.

| Tabla/entidad | Propósito y datos que le corresponden |
|---|---|
| `works` / Work | Obra musical intelectual canónica. Identidad y atributos compartidos por sus realizaciones; relaciones normalizadas con personas creadoras y roles, catálogos, géneros, etc. |
| `resources` / Resource | Realización musical identificable: arreglo, transcripción, edición, versión o interpretación publicada cuando constituya un objeto catalogable distinto. Siempre pertenece a un Work. No depende de que exista un fichero ni de que una fuente externa la denomine “edición”. |
| `files` / File | Artefacto digital lógico de un único Resource: partitura completa, formato alternativo, parte, audio, imagen o derivado. Incluye nombre de fichero necesario para identificar/descargar el artefacto, formato, MIME, tamaño lógico, rol, orden/etiqueta de parte, estado y metadatos técnicos propios. No copia metadatos descriptivos completos del registro externo. |

| `external_providers` | Catálogo de proveedores/fuentes: código estable, nombre, tipo, URL base, política de atribución, estado y configuración no secreta. CPDL, PDMX e IMSLP serían filas, no tablas ni ramas especiales del modelo. |
| `external_records` (opcional; alternativa a `external_identifiers`) | Solo referencia mínima para volver a localizar un registro en el proveedor: proveedor, tipo de registro, ID externo estable y URL de consulta si resulta útil. No almacena título copiado, payload, metadatos brutos ni snapshots. Confirmar si hace falta esta tabla separada o si basta con `external_identifiers`. |
| `external_identifiers` | Referencia mínima para volver a localizar el origen: proveedor, tipo de registro externo, identificador externo exacto, entidad OSAP de destino y discriminante solo cuando sea necesario. No duplicar el mismo ID en variantes bruta y normalizada salvo que el adaptador demuestre que ambas son imprescindibles. Debe permitir colisiones reales y múltiples IDs externos para una entidad. |
| `external_record_links` | Relación entre registros externos y entidades OSAP (Work, Resource o File según la evidencia), con tipo de vínculo, confianza, método, fecha y estado de revisión. Evita forzar una equivalencia uno-a-uno cuando una ficha externa agrupa varias realizaciones o cuando varias fuentes describen la misma entidad. |
| `source_links` | Enlaces a páginas informativas, páginas de licencia, páginas de descarga y URLs externas, tipados por finalidad y asociados al objeto OSAP correcto. Una URL de página no equivale a un File ni prueba que exista descarga directa. |
| `resource_credits` / relación equivalente | Créditos y roles vinculados a un Resource cuando describen arreglo, edición, transcripción u otra contribución a esa realización. Los créditos de la composición se mantienen en Work; los roles no se trasladan de ámbito sin evidencia. |
| `resource_attributes` o relaciones normalizadas | Atributos específicos de la realización que no sean campos centrales ni relaciones ya normalizadas: instrumentación, voces, tonalidad, idioma, número de partes, duración, compases, páginas, etc. Se prefiere esquema relacional tipado/catálogos para atributos con consultas, validaciones o vocabulario estable. No se guardará JSON con payloads o metadatos originales del proveedor. |
| `ingestion_runs` | Registro operativo mínimo de cada proceso: proveedor, versión del adaptador, fecha, resultado, contadores y errores técnicos sin payloads de origen. No almacenar snapshots ni una tabla `source_observations` con copias de cada captura. La necesidad y retención de estos logs se confirmarán en el diseño operativo. |

Las tablas actuales normalizadas de personas, roles, géneros, instrumentos, idiomas, conjuntos y catálogos se conservarán o evolucionarán según el inventario; no se duplicarán dentro de JSON ni se desnormalizarán para reproducir la estructura de un proveedor.

### 20.2 Reglas canónicas del dominio

1. **Work no es una fuente.** Una obra puede estar descrita por varios proveedores y no tener ningún fichero alojado.
2. **Resource no es una ficha externa.** Representa una realización musical distinguible por su contenido o función, aunque se haya descubierto a través de una ficha externa.
 - File incluye identidad, nombre, formato, estado, hash de integridad cuando exista y referencia al almacenamiento. No se separan los bytes en una entidad Blob.
4. **La procedencia es transversal.** Un Work, Resource o File puede estar respaldado por varias fuentes. Una fuente puede describir varios objetos OSAP. La relación se representa explícitamente y no se codifica en un único `origin` genérico.
5. **Los IDs externos no son IDs canónicos.** Se conserva únicamente el identificador necesario para volver a consultar el registro, con su proveedor y tipo; no se almacena una copia del registro externo ni un duplicado normalizado de sus metadatos.
6. **No se conservan copias de los datos de origen.** OSAP guarda los datos normalizados que necesita para su catálogo y una referencia externa mínima para poder volver a consultar el proveedor. No almacena payloads, títulos originales duplicados, metadatos brutos ni snapshots históricos de la fuente.
7. **No inferir recursos por existencia de fichero.** Un artefacto solo se agrupa con otros bajo el mismo Resource cuando haya evidencia de que pertenecen a la misma realización. La extensión o el nombre no bastan.
8. **No inventar recursos por existencia de ficha.** Una referencia externa que solo identifica una página puede permanecer como correspondencia mínima pendiente de clasificar hasta determinar si describe una obra (Work), un Resource o un File; no se conserva el contenido de la ficha.
9. **La importación es idempotente y revisable.** Conflictos de identidad, duplicados y correspondencias ambiguas quedan registrados; no se resuelven fusionando silenciosamente entidades.
10. **La licencia se asigna al objeto correcto.** Una licencia de composición, de arreglo/edición, de fichero y condiciones de descarga pueden ser distintas. OSAP guarda el código/valor normalizado que necesita y una URL de referencia cuando proceda, no una copia extensa del texto de la fuente. Se registra a qué objeto y jurisdicción se refiere.

### 20.3 Modelo de relaciones externas sin acoplarse a CPDL

El contrato debe poder expresar todos estos casos sin cambiar el esquema de dominio:

- un proveedor identifica directamente una obra;
- un proveedor identifica una realización dentro de una obra;
- una ficha externa describe una obra y enlaza a varias realizaciones;
- una ficha externa enlaza a varios ficheros, algunos equivalentes y otros de realizaciones diferentes;
- dos proveedores describen la misma Work o Resource con identificadores distintos;
- un identificador externo cambia, desaparece o colisiona;
- una URL es una página de información, una licencia, una descarga directa o una ubicación de un fichero ya alojado;
- una captura contiene información incompleta o contradictoria que necesita revisión.

`external_identifiers` (y, si la auditoría lo justifica, `external_records`) guarda solo las claves y referencias mínimas para volver a localizar la fuente; las relaciones de correspondencia enlazan esas referencias con Work, Resource o File. `source_links` se limita a URLs externas que tengan utilidad operativa o de atribución. Ninguna de estas tablas conserva la representación completa de la fuente ni snapshots.

La cardinalidad y el DDL exactos de estas tablas quedan abiertos a la auditoría. En particular, se debe evitar un diseño de enlaces externos que permita asociar un File a un Resource distinto del que declara `files.resource_id`; el contrato debe validar esa consistencia o separar claramente enlaces de procedencia de relaciones de propiedad. Si `external_records` no aporta nada que no cubra `external_identifiers` y `source_links`, se elimina y no se crea.

### 20.4 Cómo usar los datos de CPDL y de los demás proveedores

CPDL se importará mediante un adaptador que traduzca la información necesaria a las tablas canónicas. Se conservarán únicamente identificadores externos y URLs útiles para volver a consultar la fuente, más los datos normalizados que OSAP necesite para funcionar. No se copiarán páginas completas, créditos en bruto, licencias en texto duplicadas ni payloads de origen; cuando un dato deba actualizarse, el adaptador volverá a solicitarlo al proveedor. Los conceptos particulares —incluidos números de página o edición— solo se guardarán si son necesarios para identificar o volver a localizar el registro, sin convertirse automáticamente en entidades de dominio.

Se aplicará el mismo criterio a PDMX, IMSLP y futuras fuentes. Si una fuente agrupa varios arreglos en una ficha, OSAP creará los Resources que justifique la evidencia musical, no un Resource por ficha por defecto. Si una fuente publica varios formatos del mismo arreglo, OSAP podrá vincularlos como Files de un Resource. Si no se puede determinar si son formatos equivalentes o realizaciones distintas, se conservarán como candidatos separados y se marcará la revisión pendiente.

### 20.5 Criterio de aceptación del diseño de datos

Antes de aprobar el DDL, el inventario debe entregar:

- el diccionario de cada tabla canónica, con propósito, PK/FK, cardinalidades, índices, restricciones y política de borrado;
- el mapa de todos los campos actuales hacia Work, Resource, File, almacenamiento, identificadores externos mínimos, créditos o atributos normalizados;
- ejemplos reales anonimizados de cada patrón de importación, incluidos conflictos y datos incompletos;
 - reglas de identidad para Work, Resource y File; el hash se usa para verificar integridad, no para compartir Files u objetos físicos;
- estrategia de actualización desde el proveedor, con almacenamiento mínimo de identificadores externos y sin conservar payloads ni snapshots;
- pruebas de idempotencia, colisiones de IDs, varias fuentes por entidad, varias realizaciones por ficha, varios Files por Resource y Resources sin File;
- una lista de decisiones pendientes explícitas; ninguna cardinalidad debe justificarse solo por la estructura de una web externa.

### 20.6 Por qué V6 no separa File y Blob

En V6, `File` será la identidad del artefacto y la referencia a su almacenamiento. No habrá una entidad `Blob` adicional:

 - **File:** representa el artefacto digital concreto dentro de un Resource: PDF, MusicXML, MIDI, una parte, audio u otro fichero. Tiene identidad propia, nombre, formato, función, estado y reglas de acceso.
 - El propio File se vincula a un único objeto físico de almacenamiento. El hash y el tamaño son datos de integridad, no una identidad compartida ni una tabla de deduplicación.

Ejemplo: un Resource puede tener un PDF, un MusicXML y un MIDI; son tres Files porque son tres artefactos/formats distintos de esa realización. Si un mismo PDF aparece bajo dos supuestos Resources, no debe compartirse mediante una referencia física común: primero hay que determinar si realmente describen la misma realización. Si lo son, debe existir un solo Resource; si no lo son, cada Resource tendrá su propio File y objeto físico.

La decisión es eliminar Blob del modelo conceptual. La eventual replicación física, si la infraestructura la necesita por disponibilidad o copias de seguridad, queda dentro del servicio de almacenamiento y no permite que un objeto se asocie a varios Files.

La decisión de arquitectura es firme: **el esquema canónico se diseña desde el dominio musical de OSAP; los proveedores se conectan mediante referencias mínimas de identidad y enlaces útiles para volver a consultarlos, no mediante copias de sus registros**. El DDL final solo se cierra después de comprobar que estas entidades cubren los datos y consumidores reales.
