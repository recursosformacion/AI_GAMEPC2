# OSAP — Contrato de Compositores (consulta pública + fusión admin) (v1)

**Estado:** CONTRATO (congelado). Backend/frontend implementado; pendiente de verificación.
**Base:** decisiones de identidad/autorización ya congeladas.
**Alcance:** solo consulta pública de compositores y fusión (admin). Fuera: creación/edición,
`tier`, modificación de osap-storage.

---

# 1. Acceso

| Acción | ANONYMOUS | USER | ADMIN (role=admin) |
|---|---|---|---|
| Listar/buscar compositores | ✅ | ✅ | ✅ |
| Ver detalle | ✅ | ✅ | ✅ |
| Ver obras | ✅ | ✅ | ✅ |
| **Fusionar** | ❌ | ❌ | ✅ |

- Un usuario autenticado **no** obtiene capacidades extra por ser user.
- `role=admin` es lo que manda; la fusión **nunca** depende de `tier`.

---

# 2. Endpoints de osap-api

## Consulta pública

### `GET /api/v1/composers?q=&limit=&offset=`
```json
{ "items": [ { "id": "comp", "name": "Mozart", "status": "active", "aliases_count": 3, "works_count": 264 } ], "total": 1 }
```

### `GET /api/v1/composers/{composer_id}`
```json
{ "id": "comp", "name": "Mozart", "status": "active", "aliases": ["W. A. Mozart"], "works_count": 264, "merged_into": null, "merged_at": null }
```
- **404** si no existe.

### `GET /api/v1/composers/{composer_id}/works?limit=&offset=`
```json
{ "items": [ { "work_id": 264, "title": "Ave verum", "composer_id": "comp" } ], "total": 1 }
```

## Fusión (admin)

### `POST /api/v1/admin/composers/{target_id}/merge`
- Body: `{ "source_ids": ["src1", ...] }`.
```json
{ "target_id": "target", "sources_merged": ["src1"], "aliases_transferred": 3, "works_moved": 2, "merge_operation_id": "op-1" }
```

## Errores

| Código | Caso |
|---|---|
| 401 | Fusión sin token |
| 403 | Fusión con usuario sin `role=admin` |
| 404 | Composer inexistente |
| 422 | Body inválido (fusión) |
| 503 | Identidad de servicio no configurada (consulta o fusión) |

---

# 3. Backend → osap-storage

| Operación | Storage | Scope SERVICE |
|---|---|---|
| Listar compositores | `GET /api/admin/composers` | `storage:read` |
| Detalle | `GET /api/admin/composers/{id}` | `storage:read` |
| Obras | `GET /api/admin/composers/{id}/works` | `storage:read` |
| Fusión | `POST /api/admin/composers/{target}/merge` | **`storage:admin`** (service client administrativo) |

- Consulta: client normal (nunca `storage:admin`).
- Fusión: **service client administrativo separado** (`storage:admin`); osap-api NO recibe
  `storage:admin` por defecto.
- Los DTOs de osap-api reproducen los shapes de storage sin inventar campos.

---

# 4. Web

- **CompositoresPage**: listado + búsqueda `q` + paginación (público).
- **ComposerDetailPage**: detalle + obras (público); **formulario de fusión solo si
  `role=admin`**.
- **Navegación**: enlace "Compositores"; Login/Logout según sesión.
- **Seguridad**: el frontend solo muestra la acción de fusión; **osap-api vuelve a comprobar**
  `role=admin`. La UI no decide permisos.

---

# 5. Fuera de alcance

- Creación y edición de compositores.
- `tier`.
- Cualquier modificación de osap-storage.

---

*Contrato de Compositores v1 (2026-08) — congelado; verificación pendiente.*
