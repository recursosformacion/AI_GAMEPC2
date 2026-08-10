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
