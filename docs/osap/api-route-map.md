# Mapa de rutas de OSAP API

**Estado:** VIGENTE, mapa por familias contrastado con `src/osap/api/platform_app.py`.  
**Revisión:** 2026-11-24.  
**Límite:** no sustituye al OpenAPI generado; los paths, modelos y requisitos de autenticación de cada operación se verifican en el router y sus pruebas.

## 1. Composición de la aplicación

La factory `src.osap.api.platform_app:create_platform_app` crea la aplicación FastAPI y registra los routers. Es el punto de entrada para saber qué familias están activas. La composición actual incluye:

| Familia | Router | Responsabilidad |
|---|---|---|
| Sistema | `http/system.py` | Estado y salud operativa |
| Búsqueda | `http/search.py` | Búsqueda federada, resultados y resolución |
| Trabajos asíncronos | `http/jobs.py` | Estado de trabajos y operaciones asíncronas |
| Obras | `http/works.py` | Consulta y operaciones de Work |
| Compositores | `http/composers.py` | Catálogo y mantenimiento de compositores |
| Personas | `http/persons.py` | Identidad y consulta pública de personas |
| Representaciones / OMR | `http/omr.py` y contratos de representación | Acceso a recursos y operaciones OMR |
| Sesiones | `http/sessions.py` | Sesiones de resolución y selección |
| Proveedores | `http/providers.py` | Catálogo de proveedores |
| Fuentes | `http/sources.py` | Fuentes y sugerencias |
| Conocimiento | `http/knowledge.py` | Clasificaciones y conocimiento musical |
| Cuotas | `http/quota.py` | Cuotas y límites de acceso |
| Analítica | `http/analytics.py` | Analítica personal y administrativa |
| Autenticación | `http/auth.py` | Login, callback y operaciones de identidad |
| Espacio personal | `http/workspace.py` | Área y recursos del usuario |
| Aportaciones | `http/contributions.py` | Aportaciones y revisión |
| Colaboradores | `http/collaborators.py` | Información y reconocimientos públicos |
| Los Amigos | `http/amigos.py` | Grupos, coros y comunidad |
| Votos | `http/votes.py` | Votos y estadísticas de valoración |
| Support | `http/support.py` | Integración con osap-support |
| Administración | `http/admin.py`, `http/admin_ops.py` | Operaciones administrativas y configuración |
| Noticias | `http/news.py` | Integración de noticias |
| Notificaciones | `http/notifications.py` | Notificaciones |
| Publicidad | `http/ads.py` | Integración de anuncios |
| SEO HTML | `http/seo.py` | Fichas indexables de obras, personas y representaciones |
| Sitemaps | `http/sitemap.py` | Índices y páginas de sitemap |

## 2. Endpoints de referencia comprobados

| Método | Ruta | Autenticación / alcance |
|---|---|---|
| GET | `/api/v1/system/health` | Comprobación operativa |
| POST | `/api/v1/searches` | Búsqueda pública |
| GET | `/api/v1/searches/{search_id}` | Consulta del resultado de búsqueda |
| GET | `/api/v1/representations/{representation_id}` | Ficha de representación |
| GET | `/api/v1/representations/{representation_id}/probe` | Comprobación de disponibilidad |
| GET | `/api/v1/representations/{representation_id}/download` y `/download/{filename}` | Apertura/descarga, según proveedor y disponibilidad |
| GET | `/api/v1/works/public/{work_id}` y `/details` | Ficha pública del índice y datos enriquecidos disponibles |
| GET/POST/DELETE | `/api/v1/workspace/library` y `/{item_id}` | Biblioteca personal autenticada |
| POST/GET | `/api/v1/contributions` y `/{contribution_id}` | Aportaciones propias autenticadas |
| POST | `/api/v1/contributions/{contribution_id}/upload` | Subida asociada a una aportación autenticada |
| GET/POST | `/api/v1/admin/contributions` y `/{contribution_id}/review` | Revisión administrativa de aportaciones |
| GET | `/api/v1/amigos/my` y `/my/groups`, `/my/events`, `/my/blog` | Área personal de Los Amigos |
| GET | `/api/v1/analytics/me` | Usuario autenticado; identidad derivada del token |
| GET | `/api/v1/activity/me` | Usuario autenticado; panel personal |
| GET | `/api/v1/admin/analytics/overview` | Rol admin |
| GET | `/api/v1/admin/analytics/funnel` | Rol admin |

Los endpoints de representación pueden aceptar `?view=1` para solicitar visualización inline. La disponibilidad y la descarga dependen del proveedor: OMR/Storage y Mutopia pueden ofrecer ficheros servibles por OSAP; IMSLP y CPDL se presentan como fuentes externas cuando el fichero directo no es servible.

## 3. Rutas HTML públicas

Estas rutas son HTML server-rendered y no forman parte de `/api`:

- `/composers` y `/composers/{person_id}/{slug}`.
- `/obras/{work_id}/{slug}`.
- `/representacion/{representation_id}`.
- `/amigos/corales/{group_id}/{slug}`, `/amigos/articulos` y `/amigos/articulo/{article_id}/{slug}`.
- Los aliases heredados `/obra/{work_id}` y `/compositor/{person_id}` siguen registrados y redirigen a las rutas canónicas plurales.
- `/sitemap.xml` y `/sitemaps/{kind}-{page}.xml`.

Los IDs son la identidad estable; los slugs son descriptivos. Los aliases y redirecciones deben preservar URLs históricas y nunca redirigir una identidad ambigua a una obra distinta.

## 4. Seguridad de los contratos

- No asumir que una ruta es pública por el nombre del router. Revisar dependencias y pruebas de cada endpoint.
- Los tokens de usuario y los tokens M2M son distintos; un service token no debe autorizar acciones de usuario.
- Las rutas administrativas exigen rol o scope administrativo según el contrato concreto.
- La SPA no debe recibir secretos de servicio.
- La identidad del usuario se obtiene del token validado, no de un `user_id` enviado por el cliente.

## 5. Versiones

El release del conjunto OSAP visible en la web el 2026-11-24 es 6.4.1. El objeto FastAPI declara `version="3.1"` como versión interna del contrato/plataforma. No confundir ese valor con la versión de producto del conjunto. Si se decide unificar ambas, debe hacerse como cambio explícito del contrato OpenAPI.

## 6. Fuente de verdad

- Registro de routers: `src/osap/api/platform_app.py`.
- Paths, parámetros y modelos: cada módulo `src/osap/api/http/*.py`.
- DTO: `src/osap/api/contracts/`.
- Integración y casos de uso: `src/osap/api/platform/`.
- Cobertura: pruebas `tests/osap/` y pruebas HTTP correspondientes.

Cuando cambie una ruta, actualizar pruebas, OpenAPI, este mapa y el manual si la operación afecta a usuarios.
