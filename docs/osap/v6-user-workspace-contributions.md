# V6 — integración de Mi Actividad y aportaciones en OSAP-API

> **Estado:** especificación de integración funcional para V6; pendiente de inspección detallada de auth, diseño de endpoints, implementación y pruebas.  
> **Modelo de catálogo:** `Work → Resource → File`.  
> **Especificación funcional principal:** [AI_osap-storage/docs/v6-user-workspace-contributions.md](https://github.com/recursosformacion/AI_osap-storage/blob/main/docs/v6-user-workspace-contributions.md).

## 1. Alcance obligatorio

OSAP-API debe incluir en V6 un área autenticada de usuario, presentada en la interfaz como **Mi Actividad** o **Mi espacio de trabajo**, y un flujo para aportar nuevas piezas o nuevos Resources al catálogo.

No es una aplicación separada ni un catálogo alternativo. Es una superficie de usuario sobre el catálogo canónico y sobre expedientes privados de aportación.

## 2. Capacidades de Mi Actividad

El usuario autenticado podrá:

1. Consultar su espacio personal.
2. Añadir una Work pública existente a su espacio sin duplicarla.
3. Quitar esa relación personal sin borrar la Work ni sus Resources/Files.
4. Organizar sus Works mediante estado personal, notas y etiquetas privadas.
5. Crear borradores de piezas nuevas.
6. Proponer un Resource nuevo para una Work existente.
7. Adjuntar uno o varios Files a un Resource propuesto.
8. Guardar un Resource externo URL-only sin File cuando corresponda.
9. Enviar una aportación a revisión.
10. Consultar el estado, comentarios y decisiones de sus aportaciones.

Las notas, etiquetas y estados personales no se escriben en Work ni Resource y no se exponen en páginas o endpoints públicos.

## 3. Tipos de aportación

La interfaz debe distinguir al menos:

- **Nueva Work:** pieza que no se encuentra en el catálogo tras revisar posibles coincidencias.
- **Nuevo Resource de una Work existente:** arreglo, edición, transcripción, partitura, grabación, interpretación u otro material.
- **Nuevo File de un Resource:** otro formato útil de la misma realización, si el usuario tiene autorización para proponerlo.
- **Corrección de metadatos:** propuesta revisable sobre una Work o Resource existente; no actualización pública directa por defecto.

No se debe confundir un nuevo formato con una nueva realización ni una realización nueva con una Work nueva.

## 4. Seguridad y autenticación

Antes de implementar, inspeccionar el mecanismo real de autenticación y autorización de AI_GAMEPC2. No inventar scopes ni reutilizar permisos sin comprobar su semántica.

Requisitos:
- derivar el usuario desde la sesión/token autenticado en servidor;
- no confiar en un `user_id` enviado por el cliente;
- comprobar propiedad y permisos en cada operación;
- impedir lectura/escritura cruzada entre usuarios;
- separar permisos de aportante, revisor y publicador;
- acceso de revisor limitado al expediente asignado/autorizado, no al espacio completo del usuario;
- registrar las decisiones administrativas y de publicación;
- exigir autorización también para descargar Files privados.

La UI no sustituye a las comprobaciones de servidor.

## 5. Estados y revisión

Estados mínimos del expediente:

`draft → submitted → in_review → accepted | rejected | changes_requested`

La transición se valida en servidor. Al enviar se congela una versión revisable, incluidos metadatos declarados, créditos/licencia y lista de Files. Si se solicitan cambios, la nueva entrega no sobrescribe la versión revisada.

La aceptación y la publicación deben ser distinguibles si la operación de integración puede fallar. Solo cuando la publicación termine correctamente el material se considera público.

## 6. Integración con Storage V6

El área personal usa el contrato Work/Resource/File, sin Representation.

- Una Work existente se vincula al usuario mediante una relación personal.
- Un borrador nuevo no se presenta como Work pública.
- Un Resource propuesto apunta a una Work existente o a una Work nueva propuesta.
- Cada File pertenece a un único Resource.
- Un Resource puede tener cero Files o varios.
- Los Files privados no aparecen en búsqueda ni descarga pública.
- Storage gestiona carga, persistencia, verificación y entrega; OSAP-API gestiona identidad, permisos, expediente editorial y publicación.
- Publicar un File ya cargado no debe requerir subirlo de nuevo ni cambiar su puntero R2.
- Nunca se expone al cliente la clave física R2 ni se permite que la construya.

La carga debe confirmar la existencia/estado del objeto antes de activar el File. Un fallo no debe dejar un File disponible sin objeto físico.

## 7. Búsqueda e índice

El índice general solo incorpora Works y Resources publicados. Los borradores, relaciones personales, notas privadas, aportaciones pendientes y Files privados quedan fuera.

La búsqueda dentro de Mi Actividad puede combinar:
- Works públicas del catálogo;
- relaciones personales del usuario;
- borradores y aportaciones propias, según estado y permisos.

Toda consulta personal debe filtrar por el usuario autenticado. El índice no es fuente de verdad de propiedad ni autorización.

Tras publicar una aportación:
- actualizar o invalidar la proyección de índice correspondiente;
- mantener idempotencia;
- permitir que el rebuild completo reproduzca el estado canónico publicado.

## 8. Impacto en las superficies de OSAP-API

Durante la implementación se debe inventariar y adaptar:
- menú y navegación para usuario autenticado;
- página/listado de Mi Actividad;
- buscador/selector de Works públicas para añadir al espacio;
- detalle personal de Work;
- formularios de borrador de Work y Resource;
- gestión de Files y progreso/resultado de carga;
- bandeja de aportaciones propias y estado;
- cola de revisión restringida;
- vistas de revisión con acceso a Files;
- acciones de aceptar, rechazar, solicitar cambios y publicar;
- endpoints, schemas, servicios, permisos y tests;
- enlaces de vuelta al catálogo público una vez publicado.

Los nombres y rutas definitivos deben seguir la arquitectura existente de OSAP-API y se fijarán después de inspeccionar sus routers y convenciones. Este documento define capacidades, no inventa endpoints ya existentes.

## 9. Decisiones pendientes antes del DDL y de la API

1. Inspeccionar usuarios, roles, scopes y sesión/token reales.
2. Determinar si Mi Actividad necesita una entidad Workspace o basta con relaciones por usuario.
3. Definir almacenamiento tipado de borradores y versiones sometidas.
4. Definir cómo se representa una Work propuesta sin ID canónico.
5. Definir asignación de revisores y política de publicación.
6. Determinar qué cambios de metadatos requieren revisión.
7. Definir notas, etiquetas, archivado y eliminación personal.
8. Definir cuotas, formatos, límites y retención de Files.
9. Definir qué información del aportante se hace pública tras aceptación.
10. Definir proceso de reclamación/licencia y retirada de material.

No cerrar el DDL ni los scopes hasta verificar el sistema real y resolver estas decisiones.

## 10. Criterios de aceptación

- [ ] Usuario autenticado accede solo a su espacio.
- [ ] La misma Work puede añadirse por varios usuarios sin duplicar Work.
- [ ] Quitar una Work del espacio no borra datos canónicos.
- [ ] Notas y estados personales permanecen privados.
- [ ] Borradores y Files privados no aparecen en catálogo ni índice público.
- [ ] El usuario no puede leer ni modificar aportaciones ajenas.
- [ ] Los revisores acceden solo a expedientes autorizados.
- [ ] Las transiciones de estado inválidas se rechazan.
- [ ] Cada revisión queda auditada.
- [ ] Se puede aportar un Resource a una Work existente.
- [ ] Se puede proponer una Work nueva sin duplicar una existente.
- [ ] Un Resource admite cero o varios Files.
- [ ] Fallos de carga no dejan Files activos sin objeto.
- [ ] La descarga privada comprueba autorización.
- [ ] La aceptación/publicación es idempotente.
- [ ] La publicación conserva el vínculo con aportante y expediente.
- [ ] Solo el contenido publicado se incorpora al índice.
- [ ] El rebuild del índice reproduce el catálogo publicado.

## 11. Secuencia de implementación

1. Auditar autenticación y autorización actuales.
2. Cerrar decisiones pendientes de producto/editoriales.
3. Diseñar DDL y restricciones de aislamiento.
4. Diseñar contratos API y servicios.
5. Implementar Mi Actividad y relaciones personales.
6. Implementar borradores y carga privada.
7. Implementar envío, revisión y versiones.
8. Implementar aceptación/publicación idempotente.
9. Integrar el índice y las estadísticas.
10. Ejecutar pruebas de seguridad, integridad, carga, revisión y rebuild.

**Mi Actividad y las aportaciones de usuarios forman parte del alcance obligatorio de V6. No deben aplazarse a una versión posterior al corte Work → Resource → File.**

## Regla de propiedad editorial: modificación de Works ajenas

Solo el aportante original puede modificar directamente una Work. Si el usuario actual no es ese aportante y solicita modificarla, la operación debe crear automáticamente una Work derivada independiente en su área personal, privada desde el inicio. La Work original no cambia. El usuario recibe crédito de arreglista (rol canónico arranger, ID 3, sujeto a vínculo User↔Person válido) y la derivada conserva el linaje de la original. Añadir al espacio personal sin modificar sigue siendo una relación sin copia. La copia solo se hace pública mediante una aportación/publicación separada, respetando licencia y trazabilidad. Véase [inventario de migración y propiedad editorial](https://github.com/recursosformacion/AI_osap-storage/blob/main/docs/v6-data-migration-mapping.md).
