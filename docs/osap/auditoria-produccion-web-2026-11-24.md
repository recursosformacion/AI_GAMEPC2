# Auditoría funcional de producción — 2026-11-24

**Estado:** revisión pública de solo lectura; pruebas autenticadas pendientes.  
**Web:** https://app.openmusicrepository.com/  
**Repositorio de referencia:** `main`, commit observado `d0e3b36847b7c43dd2af62cfab722e7fbbf21a5d`.  
**Versión mostrada por la web:** 6.4.1.  
**Importante:** el pie de página no identifica el SHA desplegado; no se afirma que producción ejecute exactamente el HEAD actual de `main`.

## 1. Alcance y método

Se han abierto páginas públicas reales de portada, índice de compositores, ficha de obra y todas las secciones del manual español: índice, búsqueda, catálogo, clasificación, fuentes, herramientas, comunidad y cuenta.

La revisión no ha usado credenciales ni ha realizado escrituras, descargas autenticadas, pagos, cambios de catálogo, migraciones o despliegues. Las acciones que requieren sesión quedan pendientes de una cuenta de pruebas.

## 2. Hallazgos confirmados

### 2.1 Asociación incorrecta de una representación — abierta

URL pública: https://app.openmusicrepository.com/obras/index-533295

La ficha se identifica como **Violin Concerto No.3 in B-flat major (IDP 3)**, pero muestra estas representaciones:

- Violin Concerto No.3 in B-flat major (IMSLP).
- Violin Concerto No.1 in F major (IMSLP).

La segunda representación no debe estar asociada a IDP 3 sin evidencia de que sea una edición o arreglo de la misma obra. El defecto continúa visible en producción.

El código actual contiene una protección en `_title_core_match()` para impedir que el enriquecimiento relacione títulos con números explícitos incompatibles. Esa protección evita una vía de nuevas asociaciones, pero no sanea filas ya persistidas en `index_representations`.

Existe el diagnóstico `script/audit_index_associations.py`, limitado a una Work y con transacción SQL `READ ONLY`. La consulta productiva requiere autorización explícita mediante `--allow-production-read`, además de confirmar el nombre exacto de la base de datos.

**Siguiente paso seguro:** ejecutar la auditoría SQL de solo lectura sobre `index-376284cace625701f1ef`, rastrear `source_rep_id`, `resource_id`, proveedor y URL de origen; después reproducir la reparación en desarrollo. No borrar ni mover filas en producción hasta identificar inequívocamente los registros y preparar backup, transacción, invariantes y rollback.

Detalle técnico: [auditoría de asociaciones del índice](auditoria-index-2026-11-24.md).

### 2.2 Índice de compositores — recuento coherente en esta revisión

La página pública https://app.openmusicrepository.com/composers muestra **Total: 20.106**. La diferencia de 198 registros comunicada en una inspección anterior no se ha reproducido en esta consulta y no se mantiene como incidencia confirmada.

### 2.3 Versión y revisión desplegada — identificación incompleta

Las fichas públicas muestran el pie **OpenMusicRepository v6.4.1**. La rama `main` consultada está en `d0e3b36847b7c43dd2af62cfab722e7fbbf21a5d`, pero la versión visible no permite deducir el SHA desplegado ni el método usado por el último despliegue.

El procedimiento versionado en el repositorio describe despliegue directo al VPS mediante SSH/SCP y servicios del sistema. No hay evidencia suficiente para atribuir el despliegue más reciente a Vercel o para asegurar qué commit está ejecutándose. Se debe obtener el registro de despliegue de quien lo ejecutó y contrastarlo con una identificación de build expuesta por la aplicación.

### 2.4 Manual español servido — divergencia entre producción y `main`

La guía pública de búsqueda todavía muestra la redacción antigua que promete «miraremos de redirigirte a ella la próxima vez». El archivo de `main` (`web/public/manual/es/buscar.html`) ya contiene una redacción más prudente: el equipo revisará el caso y valorará cómo incorporarlo o enlazarlo.

Por tanto, el texto fuente del manual español está corregido en `main`, pero la respuesta pública consultada no refleja ese mismo contenido. Antes de cambiar el manual otra vez, comprobar si el despliegue está sirviendo una copia anterior o si existe caché intermedia. No duplicar la corrección en el texto fuente.

### 2.5 Publicidad de páginas públicas — observación, no defecto confirmado

Las fichas y el índice de compositores muestran dos bloques de patrocinio. El código incluye un espacio global del layout y otro espacio contextual en la página. La duplicación visible es coherente con esos dos emplazamientos; no se clasifica como error sin una decisión de producto que limite el número de espacios.

## 3. Manual de usuario

Se han podido leer las ocho páginas principales del manual español. La estructura general y la explicación de Obra / Representación / Recurso son coherentes con la interfaz y el modelo desplegado descrito en la documentación.

Puntos que requieren validación interactiva antes de cerrar el manual:

- Búsqueda rápida y avanzada, filtros y Estudio de búsqueda.
- Acciones reales de visor, descarga y apertura externa por proveedor.
- Formularios de contacto y propuesta de fuentes.
- Registro, login, cierre de sesión y edición del nombre visible.
- Mi Actividad, cuotas, aportaciones y biblioteca/recursos privados.
- Diferencias entre permisos ordinarios y administrativos.

La página de fuentes explica que CPDL se muestra como referencia externa y que sus ficheros no se sirven desde el repositorio propio. Las fichas pueden mostrar metadatos de formato de CPDL; eso no debe interpretarse como disponibilidad de un binario alojado en OSAP. Hay que verificar el comportamiento de sus enlaces desde la sesión de pruebas.

Las traducciones catalana, francesa, inglesa y alemana deben revisarse después de cerrar el texto español, incluida la coherencia de `canonical` y `hreflang`.

## 4. Pruebas pendientes con cuenta de usuario

Al disponer de una cuenta ordinaria de prueba, ejecutar el checklist [manual-verification-checklist.md](manual-verification-checklist.md). No se debe elevar la cuenta a administrador global para facilitar la auditoría.

No realizar pagos, compras, envíos de correo reales ni operaciones irreversibles. Para cada prueba registrar URL, pasos, resultado, código HTTP y evidencia sin datos personales.

## 5. Pruebas pendientes de servicios

No se consideran certificados por esta revisión:

- API: salud, errores y tiempos de respuesta.
- Auth: login real, issuer, JWKS, audiencia y expiración.
- Storage: consulta de catálogo, autorización y descarga de archivos.
- Support: llamadas M2M, scope correcto, 401/403/503 y separación de identidad.
- Noticias y publicidad: integración real, fallback, impresiones y clics.
- Operaciones de subida, biblioteca y recursos privados.

El código, las plantillas de configuración y los tests locales no demuestran por sí solos que las variables y credenciales de producción sean correctas.

## 6. Restricciones

- Solo lectura sobre la web pública.
- Ninguna escritura o consulta SQL en producción ejecutada durante esta revisión.
- Ninguna migración, reconstrucción de índice o modificación de datos.
- Ningún despliegue.
- Ningún cambio en Chorus.
- Trabajo documental y correcciones de código únicamente en `main`; sin ramas ni PR.

## 7. Segunda pasada: búsqueda, visor, descargas y proveedores

### 7.1 Búsqueda — contrato revisado; ejecución real pendiente

El router define `POST /api/v1/searches` (201, con Location) y `GET /api/v1/searches/{search_id}`. Rechaza búsquedas sin query, composer, title o catalogue. La búsqueda es pública en el router actual. Esto acredita el contrato del código, no la ejecución en producción. Quedan pendientes pruebas desde el navegador por título, compositor, catálogo, filtros combinados y navegación entre resultados.

### 7.2 Visor y descargas — comportamiento implementado en código

El router define ficha de representación, `/probe`, descarga normal y `?view=1`:

- `GET /api/v1/representations/{id}`: ficha.
- `GET /api/v1/representations/{id}/probe`: indica si el servidor puede leer el fichero externo. CPDL/Cloudflare puede devolver `readable=false` por anti-bot; no significa que el recurso no exista.
- `GET /api/v1/representations/{id}/download?view=1`: intenta servir inline para el visor.
- `GET /api/v1/representations/{id}/download`: descarga attachment.

Comportamiento observado en el código:
- Recursos OMR/Storage se recuperan desde Storage y se sirven con nombre legible y Content-Disposition adecuado.
- MusicXML comprimido (firma ZIP) se etiqueta como MXL.
- La descarga normal OMR consume cuota; la vista inline no.
- IMSLP/CPDL y otros proveedores externos pueden acabar en redirección 302 al navegador. Ante anti-bot, el navegador puede resolver el reto.
- Sin URL de descarga/vista: 404. Fallo al recuperar un recurso propio desde Storage: 502.
- La interfaz genera rutas de visor para MusicXML/MXL/XML/MEI/PDF y MIDI; las acciones dependen de URL, proveedor y flags available/downloadable.

**No se ha descargado ningún fichero real en esta pasada.** Para certificar producción hay que probar un PDF y un MusicXML/MXL de OMR, un PDF IMSLP y una referencia CPDL, anotando status, Content-Type, Content-Disposition y destino final.

### 7.3 Manual de fuentes — correspondencia con el código

El manual español explica que IMSLP se utiliza como referencia externa; CPDL conserva referencias y formatos declarados, pero los archivos siguen en ChoralWiki y pueden requerir resolver anti-bot en el navegador; OMR es repositorio propio y el visor depende de disponibilidad y compatibilidad; Mutopia depende del recurso incorporado. Estas afirmaciones son coherentes con las ramas proxy/redirect del router. Falta probar enlaces concretos y resultados HTTP de producción.

## 8. Auth, Storage y Support — rutas y límites de comprobación

### 8.1 Auth

La configuración versionada define host `auth.openmusicrepository.com`, prefijo `/auth-api/`, health backend `GET /health` (ruta pública esperada `/auth-api/health`), JWKS `/auth-api/auth/.well-known/jwks.json` e issuer `https://auth.openmusicrepository.com`. El virtual host aplica gate por Referer/Origin/IP con excepciones para discovery, authorize y OAuth. La herramienta de consulta no permite establecer las cabeceras esperadas y no recuperó health ni JWKS. **Auth no queda certificado en producción.**

### 8.2 Storage

La configuración versionada define host `storage.openmusicrepository.com` y health `GET /api/v1/health`, que consulta DB y repositorio y devuelve checks/contadores. El virtual host aplica gate por Referer/Origin/IP. La consulta externa sin esas cabeceras no pudo recuperar health. **No quedan certificados DB, repositorio ni descargas de Storage en producción.**

### 8.3 Support

La configuración versionada define `support.openmusicrepository.com`, con prefijo `/support-api/` reescrito al backend; la raíz del host devuelve un health estático del proxy. El backend documenta `GET /health` y `GET /ready`. Support valida tokens de usuario con audiencia `osap-api`, tokens de servicio con audiencia `osap-support`, y exige `support:admin` para administración.

La consulta externa no pudo recuperar el host por las restricciones del virtual host. El health estático del proxy no probaría DB ni M2M. La integración API→Support está implementada en código/tests, pero no se acreditan cliente de producción, variables efectivas ni smoke test HTTP real. **Support M2M no queda certificado en producción.**

## 9. Bloqueos y siguiente ejecución

El navegador disponible no permite fijar de forma fiable Referer/Origin de los virtual hosts protegidos ni mantener una sesión. La falta de respuesta de health no se interpreta como caída: es una limitación de acceso y una protección prevista en la configuración.

Pruebas técnicas pendientes desde el servidor o un navegador autorizado:
1. Auth: `/auth-api/health` y JWKS; validar issuer, firma, expiración y audiencia de token de usuario.
2. Storage: `/api/v1/health`; comprobar `database=true` y `repository=true`; solicitar recurso con token de servicio API y probar descarga pequeña.
3. Support: `/health` y `/ready` por proxy; M2M `aud=osap-support`; operación admin con `support:admin`, sin token (401), sin scope (403) y token usuario (rechazo).
4. API: POST/GET búsqueda y pruebas de visor/descarga por proveedor.
5. Registrar status, cabeceras y resultados sin guardar tokens, secretos, emails ni datos personales.

Estas comprobaciones no requieren modificar datos productivos. Subidas, aportaciones, pagos y cambios de cuenta quedan fuera hasta autorización expresa para crear datos de prueba.
