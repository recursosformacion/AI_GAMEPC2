# «Los amigos» — miniblog de grupos musicales

Sección integrada en OSAP (no es WordPress ni una app aparte). Reutiliza la arquitectura
hexagonal, la autenticación de osap-auth, el almacén operativo (MySQL/Memoria) y la capa
SEO server-rendered existentes.

## Jerarquía funcional

```
Los amigos → Corales → CTV → Artículos
```

- `Los amigos`: entrada de la sección (SPA `/amigos`).
- `Corales`: índice de agrupaciones (SPA `/amigos/corales`).
- `CTV`: página estable del grupo, HTML server-rendered (`/amigos/corales/{id}[/{slug}]`).
- `Artículos`: publicaciones individuales con URL pública permanente, HTML server-rendered
  (`/amigos/articulo/{id}[/{slug}]`).

Los artículos **no** son ítems de menú: viven dentro de la página de su coral. La identidad
viaja en el `id` estable; el slug es descriptivo y un slug distinto provoca un 301 al canónico
(igual que `/obra` y `/compositor`), de modo que el enlace permanente nunca se rompe.

## Modelo (BD `osap-api`)

| Tabla | Contenido |
|---|---|
| `amigos_groups` | Grupos: `id`, `slug` (único), `name`, `kind` (hoy `coral`), `description`, `image_url`, `status` (`active|inactive`), `editorial_mode` (`direct|moderated`), `created_by`. |
| `amigos_members` | Membresías por grupo: `(group_id, user_id)` único, `role` (`admin|collaborator`), `status` (`active|revoked`), `granted_by`. |
| `amigos_articles` | Artículos: `id`, `group_id`, `title`, `slug` (único por grupo), `event_date` (fecha del evento), `summary`, `body`, `cover_url`, `author_user_id` (**inmutable**), `status` (`draft|pending|published|withdrawn`), `published_at`, `reviewed_by/at`, `review_note`. |
| `amigos_media` | Recursos: `article_id`, `kind` (`video|photo`), `url`, `provider`, `video_id`, `caption`, `credit`, `position`. |
| `amigos_events` | Auditoría append-only: `event_type`, `actor`, `from_status`, `to_status`, `detail_json`. |

`event_date` (fecha del evento) es independiente de `published_at` (cuándo se hizo público).
Los artículos se ordenan por `event_date` DESC.

### Categoría vs. grupo, y especialización por tipo

«Corales» es una **categoría/tipo de grupo**, no una tabla que haga de grupo. Los grupos
concretos (CTV) son instancias de un tipo; la categoría de navegación equivale al `kind` del
grupo (`coral` hoy; futuras orquestas, entidades anunciantes… se añaden sin rehacer el modelo).
Los artículos y los permisos se vinculan al **grupo** (CTV), nunca a la categoría.

Los datos específicos de cada tipo viven en una **tabla especializada** (1:1 con el grupo), no
en columnas de `amigos_groups`:

| Tabla | Contenido |
|---|---|
| `amigos_coral_details` | Ficha estructurada del coral (1:1 con un grupo `kind='coral'`): `foundation_date`, `dissolution_date`, `locality`, `region`, `country_code` (ISO-3166-1 alfa-2), `venue`, `formation_type`, `member_count`, `website`, `public_email`, `director_person_id`, `director_label`, `linked_entity`. |
| `amigos_coral_attributes` | Multivalor normalizado (nunca CSV): `(group_id, facet, value)`, con `facet ∈ {repertoire, language}`. |

`formation_type` usa un vocabulario controlado en código
(`mixed, equal_voices, children, youth, male, female, other`). `director_person_id` es un enlace
opcional a una persona identificada (osap-storage); `director_label` es solo un rótulo de
respaldo para cuando no exista persona enlazada. El estado del grupo admite `dissolved`
(desactivar/disolver **no** borra artículos, membresías ni la ficha).

## Permisos (aplicados en el servidor, nunca en el frontend)

- **Visitante**: lee artículos publicados y páginas públicas.
- **Usuario sin autorización**: no puede publicar en un grupo.
- **Colaborador** (miembro `active`): crea borradores; publica según la modalidad del grupo.
- **Administrador del grupo**: gestiona miembros/colaboradores, configura la modalidad
  editorial, aprueba/devuelve/retira publicaciones. **No** recibe privilegios globales.
- **Administrador global**: crea/desactiva grupos y designa administradores de grupo. Es el
  único que puede nombrar/retirar administradores.

Principio de mínimo privilegio. Designar/retirar administradores de grupo está reservado a la
administración global.

## Flujo editorial (decisión cerrada)

`editorial_mode` es **por grupo**:

- `direct`: el colaborador autorizado publica sin aprobación previa.
- `moderated`: su artículo queda `pending` hasta que un admin del grupo lo aprueba.

El administrador del grupo publica siempre directamente. Al cambiar de modalidad, la decisión
adoptada es **no publicar retroactivamente**: pasar a `direct` deja los `pending` como están
(deben aprobarse explícitamente). Los `published` se conservan. `withdrawn` oculta sin borrar.

## Integridad y trazabilidad

- El autor original (`author_user_id`) es inmutable; una edición administrativa no lo cambia.
- Revocar una membresía impide nuevas contribuciones pero **no** borra artículos publicados.
- Retirar no borra (trazabilidad). Las decisiones editoriales y de permisos se registran en
  `amigos_events`.
- URLs e identificadores estables ante cambios de título o de permisos.

## Privacidad

El `author_user_id` identifica internamente al autor; las páginas públicas **no** exponen email
ni nombre personal (no hay consentimiento de nickname en este modelo). Los recursos permiten
`caption` y `credit`.

## API (osap-api, `/api/v1`)

Público: `GET /amigos/groups`, `GET /amigos/groups/{id}/articles`, `GET /amigos/articles/{id}`,
`GET /amigos/groups/{id}/coral` (ficha estructurada del tipo).

Autenticado: `GET /amigos/my`, `GET /amigos/my/groups`,
`POST /amigos/groups/{id}/articles`, `PATCH /amigos/articles/{id}`,
`POST /amigos/articles/{id}/{submit|publish|withdraw}`.

Admin de grupo/global: `POST|PATCH /admin/amigos/groups[/{id}]`,
`GET|POST /admin/amigos/groups/{id}/members`, `DELETE /admin/amigos/groups/{id}/members/{uid}`,
`GET /admin/amigos/groups/{id}/articles`, `GET /admin/amigos/pending`,
`POST /admin/amigos/articles/{id}/{approve|return}`, `GET /admin/amigos/groups/{id}/audit`.

## SEO y difusión social

Las páginas de grupo y de artículo son **HTML server-rendered** (Jinja2, `api/templates/amigos_*.html`)
con `og:title`, `og:description`, `og:image`, `og:url`, `twitter:card` y JSON-LD. El cuerpo del
artículo se trata como texto (párrafos), nunca como HTML del usuario; los vídeos de YouTube se
incrustan desde el `video_id` validado. Las URLs públicas se añaden al sitemap
(`/sitemaps/amigos-1.xml`), y **nunca** se listan borradores, pendientes ni retirados.

En desarrollo el proxy lo hace `web/public/.htaccess` (regla `[P]`); en producción la `location`
de `deploy/app.openmusicrepository.com.conf`.

## Migración y pruebas

```powershell
# Esquema (idempotente; las tablas también se crean al arrancar el store MySQL):
PYTHONPATH=. python script/migrate_amigos_schema.py --dry-run

PYTHONPATH=. python -m pytest tests/osap/test_amigos.py -q
```

Tras tocar el backend: reiniciar uvicorn. Tras tocar el frontend: rebuildar `web/dist`.

## Roadmap

### v6 — independizar «Los amigos» (dominio y BD propios)

**Anotado para la versión 6.** Extraer «Los amigos» a su **propio servicio/dominio y base de
datos**, siguiendo el patrón ya existente de osap-storage/osap-support/osap-auth (API + SPA de
mantenimiento + su esquema). Motivo: evitar que osap-api siga absorbiendo dominios y contener su
tamaño. Implica: mover las tablas `amigos_*` a una BD propia, exponer el dominio por API y adaptar
osap-api a un cliente de ese servicio (como hace hoy con storage). No se implementa ahora.

