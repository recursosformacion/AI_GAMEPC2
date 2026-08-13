# ROADMAP — osap-api (Puerta pública de aplicación)

Rol en la arquitectura: **única puerta pública**. API del Web, búsqueda, obras,
compositores, votos, valoración, administración, integración con osap-auth y osap-storage,
gestión de proveedores y estado operativo propio.

Roadmap global de referencia: `_docs/roadmap.md` (raíz del proyecto).

> El ROADMAP histórico V2–V4 (dominio OSAP único) quedó superado por la división en
> osap-auth / osap-api / osap-storage.

---

## Fase B — OIDC (P1)

| Tarea | Estado |
|---|---|
| RP OIDC: PKCE, state, nonce, discovery desde issuer | ✅ |
| Callback backend (`/api/v1/auth/oidc/callback`) y canje del code | ✅ |
| Web → login en popup (centrado, sin URL) con `postMessage` | ✅ |
| `JwtAuthenticator` (valida `token_use=user`, `aud=osap-api`) | ✅ |
| Respaldo email/password cuando OIDC no está configurado | ✅ |
| Eliminar definitivamente el login paralelo del Web (OIDC único) | 🟡 Pendiente |

## Fase C — BD propia de osap-api (P2, P3)

| Tarea | Estado |
|---|---|
| BD MySQL operativa (tablas `providers`, `source_suggestions`, `app_config`) | ✅ |
| Migrar `source_suggestions` (JSON → BD) | ✅ |
| Endpoints operativos proveedores/config (admin) | ✅ |
| Tabla `audit_log` (auditoría de decisiones) | 🟡 Pendiente |
| UI de proveedores distinguiendo configurados/activos/disponibles/pendientes/sugeridos/no conectados | 🟡 Pendiente |
| Revisar estado operativo restante (`_searches`, `_representations`, `_jobs`, `KnowledgeStore`, métricas) | 🟡 Pendiente |

Criterio: reiniciar osap-api no pierde estado operativo que deba persistir; la BD no contiene catálogo.

## Fase D — Catálogo (P5, P8)

- Consistencia `composer_id` → obras de storage → representaciones/proveedores (búsqueda por identidad, no solo texto).
- Detalle de obra rico (identidad, representaciones, recursos, valoración).
- Fallback de obras de storage en el detalle de compositor: ✅ aplicado.

## Fase F — Web / UX (P7, P9, P10)

- `/about` — "Cómo funciona OSAP" (Descubrir → Entender → Actuar).
- Sistema `<Hint />` reutilizable (i18n 5 idiomas).
- Ayuda contextual (búsqueda, representaciones, proveedor, voto, valoración, compositores, registro, login, administración).
- Mejorar flujo de compositores y detalle de obra.
- Administración consolidada (revisar/fusionar compositores, proveedores, sugerencias, auditoría, estado operativo).

## Fase G — Operación (P11–P15)

| Tarea | Prioridad | Estado |
|---|---|---|
| Observabilidad (latencia, errores, llamadas a storage/auth, proveedores, búsquedas, jobs, rate limits) | P11 | 🟡 En evolución |
| Rate limiting (búsqueda, registro, OIDC/login, verify, sugerencias, costosos) | P12 | 🟡 En evolución |
| Tests de contrato Web ↔ api y api ↔ storage | P13 | 🟡 Pendiente |
| Despliegue separado (Servidor A/B/C) | P14 | 🟡 En evolución |
| Limpieza de configuración (Código/YAML · Environment/secretos · BD estado operativo) | P15 | 🟡 Pendiente |

---

## Estado actual

| Área | Estado |
|---|---|
| Búsqueda multi-proveedor + pipeline | ✅ |
| Registro / verificación email (vía osap-auth) | ✅ |
| Fusión dirigida de compositores + inspección profunda | ✅ |
| BD operativa (providers, source_suggestions, app_config) | ✅ |
| OIDC RP (popup login/registro) | 🟡 Funcionando en dev; prod listo |
| Proveedores dinámicos (endpoints) | 🟡 Parcial |
| `audit_log` | 🟡 Pendiente |
| Consistencia composer → works/pipeline | 🟡 Fallback; ruta por `composer_id` pendiente |
| Ayuda Web + Hints | 🟡 Pendiente |
| Observabilidad / rate limiting | 🟡 En evolución |

---

## Criterio de cierre

- El Web solo habla con osap-api; osap-api es la única puerta pública (auth/storage no
  accesibles desde Internet).
- Reiniciar osap-api no pierde el estado operativo que debe persistir.

*Fuente: `_docs/roadmap.md` (fases B, C, D, F, G).*
