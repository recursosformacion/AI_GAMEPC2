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
