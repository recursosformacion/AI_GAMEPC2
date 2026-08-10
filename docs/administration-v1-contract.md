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
