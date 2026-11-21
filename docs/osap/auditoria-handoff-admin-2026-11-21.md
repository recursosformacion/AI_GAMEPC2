# Auditoría y contrato de handoff administrativo entre OSAP y paneles

Fecha: 2026-11-21  
Estado: diseño técnico contrastado; implementación pendiente  
Alcance: `osap-api`, `osap-storage`, `osap-support`, `ai_publicidad`

## 1. Hallazgos verificados

### osap-storage
- `SystemMixin.storage_web()` obtiene un service token `storage:admin` y lo añade a la URL de destino (`/admin...`).
- `ServiceAuthMiddleware` valida ese token en la query para los shells `/admin`.
- La SPA lo copia desde `window.location.search` a `sessionStorage` y lo envía como Bearer en todas las llamadas.
- Las páginas curadas (`/admin/maestros`, `/admin/obras`, etc.) reciben también el token en query y lo inyectan en el HTML.
- El middleware ya es protect-all-by-default, por lo que la solución debe cubrir tanto el SPA como las páginas curadas y sus APIs.

### osap-support
- `SystemMixin.support_web()` devuelve la ruta pública del panel con `?token=<service-token>`.
- `GET /api/v1/admin/web/recognitions` valida el token y lo incrusta en el HTML como constante JavaScript.
- El JavaScript usa ese valor como Bearer en `/api/v1/admin/recognitions`.
- Las rutas de API vuelven a validar el scope `support:admin`; el shell no es el único control de acceso.

### ai_publicidad
- `SystemMixin.ads_web()` construye `/auth/session?token=<user-access-token>&next=...`.
- El receptor solo ofrece `GET /auth/session`; valida el usuario consultando `osap-auth /auth/me`.
- La cookie `ai_publicidad_session` es firmada, HttpOnly y SameSite=Lax, pero conserva los roles durante siete días y no reconsulta su vigencia. Una revocación de admin puede tardar hasta siete días en reflejarse.

### osap-api
- Los tres endpoints `GET /api/v1/admin/{storage,ads,support}-web` devuelven URL preparada para navegar.
- `AdminLayout.tsx` abre esa URL con `window.open()`; el token queda en la URL del servicio destino.
- Cambiar únicamente el frontend de osap-api no basta: los servicios destino deben aceptar y validar el nuevo handoff.

## 2. Contrato de destino

No se enviarán tokens en query strings ni se incrustarán credenciales en HTML.

### Storage
- Nuevo endpoint: `POST /admin/session`.
- Content-Type: `application/x-www-form-urlencoded`.
- Campos: `token` (service token) y `next` (ruta local permitida bajo `/admin`).
- El receptor valida `token` con scope `storage:admin`; si es válido, establece cookie host-only, HttpOnly, Secure en HTTPS, SameSite=Lax, con caducidad nunca superior a `exp` del JWT, y responde 303 a `next`.
- El middleware acepta esa cookie para las peticiones del panel. Las llamadas API no deben volver a leer tokens de query ni de `sessionStorage`.
- Todas las páginas admin, incluido el SPA, deben exigir sesión válida. No se debe dejar una página curada sin protección durante la transición.

### Support
- Nuevo endpoint: `POST /api/v1/admin/web/session`.
- Content-Type: `application/x-www-form-urlencoded`.
- Campos: `token` y `next` (solo ruta local permitida).
- Valida `support:admin`, establece cookie host-only HttpOnly/Secure/SameSite=Lax con caducidad limitada por el JWT y redirige 303.
- El shell de reconocimientos deja de incrustar el token. El JavaScript realiza las llamadas same-origin y el middleware/dependencia de autenticación valida la cookie y el scope.
- Las operaciones de escritura quedan protegidas contra CSRF: SameSite=Lax, validación de Origin/Referer en POST y rechazo de peticiones cross-site.

### Publicidad
- Cambiar `POST /auth/session` para recibir `token` y `next` en el cuerpo, nunca en query.
- Validar el token contra `osap-auth /auth/me`; establecer cookie firmada HttpOnly con duración corta (objetivo inicial: 5 minutos, nunca siete días) y sin almacenar el access token.
- Validar Origin en el handoff y en las operaciones mutables autenticadas por cookie; logout mediante POST con protección CSRF.
- El endpoint GET antiguo debe retirarse cuando el emisor y el frontend estén migrados; no mantener una vía alternativa que siga exponiendo tokens.

## 3. Contrato emisor en osap-api

- Sustituir los tres endpoints de obtención de URL por endpoints POST autenticados con el access token de usuario.
- La respuesta contiene únicamente el destino público y los campos necesarios para el POST de handoff; no devuelve una URL con credenciales.
- En el click del usuario, abrir sincrónicamente una ventana vacía para evitar el bloqueo de popups. Tras obtener la respuesta, enviar un formulario POST al destino, con `token` y `next` en el cuerpo.
- La ventana debe cerrarse si falla la petición o el handoff. No registrar tokens ni incluirlos en mensajes de error.
- El navegador nunca debe navegar a una URL que contenga token, ni el frontend debe persistirlo en localStorage/sessionStorage.

## 4. Secuencia segura de implementación

1. Añadir pruebas de contrato y sesión en cada servicio destino.
2. Implementar los receptores POST y cookies en Storage, Support y Publicidad, conservando temporalmente el contrato anterior solo durante el despliegue coordinado.
3. Adaptar las APIs de los servicios para aceptar exclusivamente la sesión nueva; eliminar query-token y token incrustado en HTML.
4. Adaptar `osap-api` (métodos de plataforma, rutas HTTP, ApiClient y AdminLayout) para usar POST de extremo a extremo.
5. Eliminar los endpoints GET antiguos y las rutas de compatibilidad con tokens en URL.
6. Ejecutar pruebas unitarias, de integración y de navegador entre los cuatro repositorios. Verificar redirecciones, caducidad, revocación, CSRF, deep links y ausencia de tokens en URL/logs/referrer.
7. Solo después de la validación, planificar despliegue coordinado. No se modifica producción como parte de esta tarea.

## 5. Criterios de aceptación

- Ningún access token o service token aparece en query strings, fragmentos, HTML, historial, Referer o logs de acceso.
- Las cookies son host-only, HttpOnly, Secure bajo HTTPS y SameSite=Lax; nunca se comparte una cookie entre subdominios.
- La caducidad de Storage/Support no supera el `exp` del service JWT; la sesión de Publicidad es corta y no puede conservar un rol revocado durante días.
- Las rutas de lectura y escritura de los tres paneles exigen la sesión correspondiente.
- Las mutaciones autenticadas por cookie rechazan solicitudes cross-site.
- Los deep links actuales de Storage siguen abriendo la sección/tabla solicitada.
- Los tokens inválidos, caducados, sin scope o con Auth no disponible fallan cerrados.
- No se rompe el acceso público ni los tokens M2M de los servicios.


## 6. Hallazgos adicionales de la revisión de implementación

### Storage: propagación de credenciales dentro del propio panel
- Además del query inicial, `admin_maintenance.py`, `admin_composers_crud.py` y `admin_works_crud.py` leen el token de `location.search` y lo conservan al navegar entre páginas y modos de edición.
- `admin_maintenance.py` mantiene también una caja manual para pegar el service token.
- Por ello, no basta con cambiar la lectura inicial de `frontend/src/auth.ts`: hay que eliminar la propagación de `?token=` de los enlaces y de los cambios de modo de las tres páginas curadas, y eliminar el almacenamiento de credenciales en `sessionStorage`.
- Los enlaces de deep-link (por ejemplo, persona/obra, modo view/edit y tabla) deben conservar solo sus parámetros funcionales (`person_id`, `id`, `mode`, `tab`), nunca credenciales.

### Support: autenticación de las operaciones
- El shell HTML valida el service token antes de servir la página, pero después lo sustituye en `__TOKEN__` dentro del JavaScript.
- Las tres operaciones de reconocimientos usan una dependencia que exige exclusivamente `Authorization: Bearer`; el cambio a cookie exige adaptar esa dependencia para aceptar la cookie host-only y seguir validando el scope `support:admin` en cada operación.
- La ruta de handoff debe validar el origen del POST; no debe confundirse el token de servicio del panel con tokens de usuario, que también son aceptados por parte de la API de reconocimientos para otros consumidores.

### Storage: autenticación de las APIs
- El middleware protege las APIs y determina el scope requerido por ruta y método. La integración de cookie debe mantener esa validación centralizada y no limitarse a autorizar el shell HTML.
- Deben verificarse explícitamente los prefijos reales de todas las rutas admin antes de modificar `_required_scope`, para evitar que una ruta administrativa quede clasificada accidentalmente como `storage:read` o `storage:write`.
