# OSAP — administration-v1 (consolidado)


## Parte: administracion-v1-decision.md

---

# OSAP — Administración (Web OSAP) — decisión v1

**Estado:** DECISIÓN APROBADA. **No implementado todavía.**
**Base:** decisiones de identidad/autorización ya congeladas; no se toca lo ya cerrado
(login, voto, compositores, valoración).
**Objeto:** cerrar qué cubre "Administración" en el Web OSAP, qué operación pertenece a cada
aplicación, qué exige `role=admin`, qué usa client normal vs administrativo, y qué queda fuera
de v1.

---

# 1. Panorama administrativo (inspección)

| Aplicación | Endpoints admin | Autorización |
|---|---|---|
| **osap-api** | `GET /api/v1/admin/votes`, `POST /api/v1/admin/composers/{target}/merge` | `role=admin` |
| **osap-storage** | `/api/admin/composers*` (list/detail/works/merge) | SERVICE + `storage:admin` |
| **osap-auth** | `/auth/admin/users*` (list/get/create/update/delete) | `role=admin` |

---

# 2. Decisión congelada — Administración

## Incluye (v1)

- **Dashboard administrativo** (solo `role=admin`).
- **Overview de votos** (osap-api `GET /api/v1/admin/votes`).
- **Administración de compositores**: consulta y fusión (osap-storage vía osap-api).
- **Indicadores/estado administrativo** que ya proporcionan esos servicios (p. ej.
  `last_execution` del overview, `status` de compositores).

## No incluye (v1)

- CRUD de usuarios.
- Gestión de contraseñas.
- Roles.
- Sesiones.
- Credenciales.
- Creación/edición de compositores.

> **La gestión de usuarios queda en osap-auth, fuera del Web OSAP v1.**

## Frontera (aprobada)

```
Web OSAP
   │
   ├── user JWT + role=admin
   │
   ▼
osap-api
   │
   ├── overview → storage:read
   │
   └── composer merge → storage:admin
   │
   └── usuarios → NO INTERMEDIAR
                         │
                         ▼
                    osap-auth
```

No se mezcla identidad con administración del catálogo.

## Operaciones y autorización

| Operación | App | role | Service client |
|---|---|---|---|
| Panel admin (dashboard) | Web | `role=admin` | — |
| Overview de votos | osap-api `GET /admin/votes` | `role=admin` | osap-api→storage: **`storage:read`** (normal) |
| Consulta compositores (admin) | osap-storage vía osap-api | `role=admin` | **`storage:read`** |
| Fusión compositores | osap-storage vía osap-api | `role=admin` | **`storage:admin`** (admin) |
| Gestión de usuarios | osap-auth | `role=admin` | **sin service token** (token de usuario) — **fuera del Web OSAP v1** |

- Todo lo administrativo exige `role=admin`. Nunca `tier`.
- El frontend solo **muestra** el panel a admin; **osap-api vuelve a comprobar** `role=admin`.

---

# 3. Service client normal vs administrativo

- **`storage:read`** (client normal de osap-api): lecturas admin (overview, consulta de
  compositores).
- **`storage:admin`** (client administrativo separado): solo operaciones de escritura admin
  (fusión de compositores).
- **osap-auth**: se autentica con el **token de usuario** admin; **no** usa service token.

---

# 4. Fuera de v1

- Creación/edición de compositores.
- CRUD de usuarios / contraseñas / roles / sesiones / credenciales.
- `tier`.
- Cualquier modificación de osap-storage (salvo la fusión ya cerrada).
- Nuevos roles/sistema de roles.

---

# 5. No implementar todavía

- No se implementa el panel aún.
- No se toca lo ya cerrado.

---

*Decisión de Administración v1 (2026-08) — aprobada; no implementado.*



## Parte: administration-v1-contract.md

---

# OSAP — Contrato de Administración (Web OSAP) (v1)

**Estado:** CONTRATO (congelado). **No implementado todavía.**
**Base:** decisión `docs/administracion-v1-decision.md`.
**Alcance:** panel administrativo (dashboard) con overview de votos y administración de
compositores (consulta + fusión). **Fuera:** CRUD usuarios, contraseñas, roles, sesiones,
credenciales, creación/edición de compositores.

---

# 1. Frontera

```
Web OSAP
   │
   ├── user JWT + role=admin
   │
   ▼
osap-api
   │
   ├── overview → storage:read
   │
   └── composer merge → storage:admin
   │
   └── usuarios → NO INTERMEDIAR  →  osap-auth
```

- Todo el panel exige `UserPrincipal` + `role=admin`.
- La gestión de usuarios se queda en **osap-auth** (fuera del Web OSAP v1); osap-api **no
  intermedia** usuarios.

---

# 2. Endpoints (osap-api, ya existentes)

## Overview de votos

`GET /api/v1/admin/votes` → `{ total_votes, top_works[], top_composers[], last_execution }`

- `top_works` / `top_composers`: `{ id, vote_count, rating, work_count }`.
- `last_execution`: `{ kind, status, started_at, finished_at }`.
- `role=admin` (user token). osap-api → storage con `storage:read`.

## Administración de compositores (consulta)

- `GET /api/v1/composers?q=&limit=&offset=` (público, usado también en admin).
- `GET /api/v1/composers/{id}` · `GET /api/v1/composers/{id}/works`.
- En el panel, la consulta usa `role=admin` (token de usuario) y osap-api → storage con
  `storage:read`.

## Fusión de compositores

`POST /api/v1/admin/composers/{target_id}/merge` → `{ target_id, sources_merged[],
aliases_transferred, works_moved, merge_operation_id }`

- `role=admin`. osap-api → storage con **`storage:admin`** (client administrativo).

---

# 3. Autorización

| Operación | role | Service client |
|---|---|---|
| Dashboard | `role=admin` | — |
| Overview de votos | `role=admin` | `storage:read` |
| Consulta compositores (admin) | `role=admin` | `storage:read` |
| Fusión compositores | `role=admin` | `storage:admin` |
| Gestión de usuarios | — | fuera del Web OSAP v1 (osap-auth) |

- Todo exige `role=admin`; nunca `tier`.
- El frontend solo muestra el panel a admin; osap-api re-chequea.

---

# 4. Errores

| Código | Caso |
|---|---|
| 401 | Sin token |
| 403 | Sin `role=admin` |
| 404 | Composer inexistente (fusión) |
| 422 | Body inválido (fusión) |
| 503 | Identidad de servicio no configurada (overview/consulta/fusión) |

- Mapear errores de storage según el patrón existente (503 para fallo de infraestructura).
- No inventar errores de negocio que storage no tenga.

---

# 5. Web — panel administrativo

- Ruta/panel accesible solo con `role=admin`.
- Muestra:
  - **Overview de votos** (total, top obras, top compositores, última ejecución).
  - **Compositores**: listado/consulta y acceso a la **fusión** (reutilizando la página de
    Compositores).
  - **Indicadores/estado** que ya proporcionan los servicios (p. ej. `last_execution`,
    `status` de compositores).
- Si el usuario no es admin, no se muestra el panel (y el backend responde 403 ante cualquier
  endpoint admin).

---

# 6. Fuera de alcance

## Fuera de esta Administración v1 (funcionamiento, no contenido)

Administración v1 administra el **funcionamiento actual de OSAP**, no contenido aportado por
usuarios. Por tanto, **queda fuera de v1**:

- moderación de obras;
- revisión de publicaciones;
- gestión de derechos;
- solicitudes de visibilidad;
- gestión de recursos;
- reclamaciones;
- aprobación de contenido.

> **Nota:** una futura **Administración de contenidos** probablemente necesitará esas
> capacidades (revisión, publicación, solicitudes, moderación).

## También fuera

- CRUD de usuarios, contraseñas, roles, sesiones, credenciales (→ osap-auth).
- Creación/edición de compositores.
- `tier`.
- Modificar osap-storage (salvo fusión).

---

# 7. Mapa provisional (contexto, NO congelado)

Mapa orientativo de los dominios de OSAP (nombres/tablas **no** congelados):

```
OSAP
│
├── Catálogo
│   ├── obras de proveedores
│   └── obras propias/catalogadas
│
├── Usuario
│   ├── obras privadas
│   ├── obras compartidas
│   └── obras públicas
│
├── Recursos
│   ├── archivos OSAP
│   └── referencias externas
│
├── Relaciones
│   ├── versiones
│   ├── arreglos
│   ├── interpretaciones
│   └── publicaciones externas
│
├── Visibilidad
│   ├── metadata
│   ├── descripción
│   ├── partitura
│   └── recursos
│
└── Administración futura
    ├── revisión
    ├── publicación
    ├── solicitudes
    └── moderación
```

> **Importante:** al terminar Administración, **no** diseñar la **subida de obras** como un
> simple `POST /works` con un fichero. Es un **submodelo de OSAP más grande** y merece su
> propia fase de **decisión → contrato → implementación**, igual que login, voto, compositores
> y valoración.

---

*Contrato de Administración v1 (2026-08) — congelado; no implementado.*



## Parte: implementation-prompt-web-administration-v1.md

---

# Web OSAP — Prompt de implementación: panel administrativo (v1)

**Estado:** PROMPT DE IMPLEMENTACIÓN. **Alcance:** dashboard administrativo (overview de votos
+ acceso a administración de compositores). **Fuera:** CRUD usuarios/roles/sesiones,
creación/edición de compositores, contenido (moderación/publicación/etc.).
**Base:** `docs/administracion-v1-decision.md`, `docs/administration-v1-contract.md`.

---

## Rol

Ingeniero sobre el Web OSAP (`web/`). Implementa el panel administrativo. El backend de
osap-api ya está implementado (`GET /api/v1/admin/votes`, `POST /api/v1/admin/composers/
{target}/merge`, `GET /api/v1/composers*`).

---

## Alcance

- Dashboard administrativo accesible **solo con `role=admin`**.
- Overview de votos (total, top obras, top compositores, última ejecución).
- Acceso a la administración de compositores (consulta + fusión, reutilizando
  CompositoresPage/ComposerDetailPage).
- Indicadores/estado que ya proporcionan los servicios (`last_execution`, `status`).
- No se intermedia usuarios (queda en osap-auth).

---

## 1. API client y tipos

- Añadir tipos en `api/types.ts`: `VotesOverview { total_votes, top_works[], top_composers[],
  last_execution }`, con `top_works`/`top_composers` = `{ id, vote_count, rating, work_count }`
  y `last_execution = { kind, status, started_at, finished_at }`.
- `ApiClient.getVotesOverview()` → `GET /admin/votes` (ya adjunta el Bearer y maneja 401).

## 2. Página AdminPage (`/admin`)

- Solo renderiza contenido si `role=admin` (`useAuth.isAdmin()`); si no, mensaje de acceso
  denegado (el backend devuelve 403 como seguridad real).
- Muestra:
  - **Overview**: total de votos.
  - **Top obras** (lista) y **top compositores** (lista) con `rating`/`vote_count`.
  - **Última ejecución** (`last_execution`: kind/status/fechas).
- Enlace a **Compositores** (`/composers`) para la administración de compositores (consulta y
  fusión) reutilizando las páginas existentes.

## 3. Navegación

- En el header, cuando `role=admin`, mostrar un enlace **"Admin"** (→ `/admin`) además del
  badge de usuario. Para no-admin, no se muestra.
- La ruta `/admin` en `routing/routes.tsx`.

## 4. Autorización

- El frontend **solo muestra** el panel a `role=admin` (comodidad).
- **osap-api re-chequea** `role=admin` (403 si no); no se depende de la UI.

## 5. i18n

- Claves de dashboard/overview en los 5 idiomas (en/es/ca/fr/de): admin.title, admin.totalVotes,
  admin.topWorks, admin.topComposers, admin.lastExecution, admin.accessDenied, admin.composers.

---

## 6. Tests

- `getVotesOverview()` devuelve el shape del contrato (fetch mockeado).
- AdminPage muestra overview con datos; con `role=admin`.
- Un usuario sin `role=admin` no ve el panel (y el backend responde 403 si invoca el endpoint).
- Navegación muestra "Admin" solo a admin.

---

## 7. NO hacer

- No tocar CRUD de usuarios/roles/sesiones (osap-auth).
- No crear/editar compositores.
- No añadir `tier`.
- No tocar osap-storage ni el backend de osap-api.

---

## 8. Validación

- `tsc --noEmit`, `vitest run`, `vite build`.

---

*Prompt de implementación del panel administrativo v1 (2026-08) — no implementado.*



