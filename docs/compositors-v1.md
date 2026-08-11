# OSAP — compositors-v1 (consolidado)


## Parte: compositors-provenance-revision-notes.md

---

# OSAP — Compositores: proveniencia, revisión e inspección (notas de diseño)

**Estado:** NOTAS / PENDIENTE. **No congelado, no contrato, no código.**
Línea de trabajo para administración de compositores (fusión dirigida e inspección).

---

# 1. Proveniencia de un compositor

Conservar la relación:

```
Compositor
    id
    nombre
    ...
    ├── origen/evidencia
    │     work_id
    │     proveedor
    │     autor_extraido
    │     fecha/dato de extracción
    │     obra (título completo)
    │     representaciones / partitura
    │     enlace a fuente
    └── estado de revisión
```

Permite responder: **"¿Por qué existe este compositor?"** y **"¿El algoritmo extrajo bien el
autor?"** (p. ej. un "autor" que en realidad es "!! Go to settings ... !!" revela extracción
incorrecta).

---

# 2. Fusión dirigida desde el compositor actual

- El sujeto de la fusión es el **compositor actual** (origen implícito).
- Se selecciona solo el **destino** entre todos los compositores existentes (búsqueda global).
- **Confirmación explícita** mostrando Origen + Destino antes de ejecutar.
- El texto deja claro: las obras, alias y relaciones del origen pasan al destino.

## Búsqueda global de destino

- Debe buscar entre **todos** los compositores (correctos, incorrectos, revisados, no
  revisados, generados, corregidos…). No filtrar a "válidos": la administración inspecciona la
  realidad del catálogo.

---

# 3. El detalle como herramienta de inspección

El detalle debe permitir (sin preocuparse por N+1 en esta pantalla administrativa):

- identidad y estado del compositor;
- aliases;
- obra que originó su creación;
- título completo de esa obra;
- autor extraído;
- proveedor;
- identificadores de la obra;
- información completa de la obra;
- representaciones disponibles;
- enlaces al proveedor;
- partitura/previsualización si es accesible.

---

# 4. Distinción: "compositor" vs "compositor revisado"

Conceptualmente distinguir (sin necesariamente añadir aún un estado al contrato):

```
"El algoritmo creó esto"
vs
"Un administrador ha comprobado que esto es correcto"
```

Relevante para futuros datos de usuario/publicación.

---

# 5. Estado

- Pendiente de implementar; notas de diseño para la futura fase de administración de
  compositores (inspección + fusión dirigida + revisión).

---

*Notas de diseño de compositores (2026-08) — pendiente.*



## Parte: compositors-v1-contract.md

---

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



## Parte: implementation-prompt-web-compositors-v1.md

---

# Web OSAP — Prompt de verificación: Compositores (consulta pública + fusión admin) (v1)

**Estado:** PROMPT DE VERIFICACIÓN. Backend y frontend de Compositores **ya implementados**;
este prompt pide verificar que cumplen el contrato `docs/compositors-v1-contract.md`.
**Alcance:** solo consulta pública y fusión. Fuera: creación/edición, `tier`, modificación de
osap-storage.

---

## Rol

Ingeniero sobre osap-api (backend) y el Web OSAP (`web/`). Verifica la pieza de Compositores
conforme al contrato. Si algo no cumple, corrígelo (sin tocar creación/edición ni storage).

---

## 1. Backend — endpoints

Verificar/corregir:

- `GET /api/v1/composers?q=&limit=&offset=` → lista pública (200), shapes exactos.
- `GET /api/v1/composers/{composer_id}` → detalle (200) / 404.
- `GET /api/v1/composers/{composer_id}/works?limit=&offset=` → obras (200).
- `POST /api/v1/admin/composers/{target_id}/merge` → 200 / 401 / 403 / 404 / 422.

**Identidad de servicio:**
- Consulta → SERVICE + `storage:read` (client normal).
- Fusión → SERVICE + `storage:admin` (client administrativo separado). Confirmar que el client
  normal **no** recibe `storage:admin`.

**Autorización backend (osap-api):**
- Consulta pública: ANONYMOUS/USER.
- Fusión: `UserPrincipal` + `role=admin` (nunca `tier`); osap-api comprueba el rol aunque la UI
  lo oculte.

**Fallo de infraestructura:** consulta/fusión sin identidad de servicio configurada → **503**
(no 500).

---

## 2. Web — páginas

Verificar:

- **CompositoresPage**: listado + búsqueda `q` + paginación; accesible sin autenticarse.
- **ComposerDetailPage**: detalle + obras; público.
- **Fusión**: el formulario solo se muestra a `role=admin`; un usuario autenticado sin admin no
  lo ve y, aunque lo invocara, el backend responde 403.
- **Navegación**: enlace "Compositores"; Login/Logout según sesión.
- El usuario autenticado normal ve **lo mismo** que un visitante (sin capacidades extra).

---

## 3. Tests

Verificar (o añadir si falta):

- Anónimo puede listar/buscar/ver detalle/obras (200).
- Usuario autenticado sin admin: igual que anónimo; fusión → 403 (backend).
- Admin (`role=admin`): puede fusionar (200).
- Fusión sin token → 401; usuario sin admin → 403; composer inexistente → 404.
- Consulta usa `storage:read`; fusión usa `storage:admin`.
- Fallo de identidad de servicio → 503 (no 500).
- Frontend muestra la fusión solo a admin; ocultarla en la UI no sustituye la comprobación
  backend.
- Navegación muestra Login/Logout.

---

## 4. NO hacer

- No crear/editar compositores.
- No añadir `tier`.
- No modificar osap-storage.

---

## 5. Validación

- Backend: `ruff`, `mypy`, `pytest` limpios.
- Frontend: `tsc --noEmit`, `vitest run`, `vite build`.

---

*Prompt de verificación de Compositores v1 (2026-08).*



