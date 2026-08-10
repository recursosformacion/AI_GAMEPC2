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
