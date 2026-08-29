# Frontend — Fronteras v1 · SupportGateway y mapa de código (Chorus / osap-app / compartido)

> **Estado:** Fase Técnica 1 (modificación mínima y reversible).
> Referencias: `support-architecture-separation.md` (arquitectura), `support-ecosystem-architecture.md`, `support-phase1-support-page.md`.
> Fecha: 2026-08-29

---

## 1. Qué se ha hecho en esta fase

Se ha introducido la primera frontera real del frontend **sin extraer Chorus** ni crear `osap-support`:

- **`SupportGateway`** (interfaz/port) en `web/src/support/supportGateway.ts`.
- **Implementación temporal** (`LocalSupportGateway`) que **solo** refleja si hay sesión (deriva de `JWT.sub` vía `useAuth`); **no simula membresía ni pagos**.
- **`useSupport()`** hook de UI que expone `{ status, authenticated, subscriberId }` y reacciona a los cambios de sesión.
- **`SupportPage`** ahora usa `useSupport()` para el **estado de apoyo** (la lógica que en el futuro pertenecerá a `osap-support`); el login/registro sigue siendo de **Auth** (vía `useOidcLogin` + formularios Auth).
- **Tests mínimos** (gateway + página `/support`).
- **No se tocó Auth, no se creó `osap-support`, no se migró la SPA.**

### Archivos creados
```
web/src/support/supportGateway.ts       · interfaz SupportGateway + tipos
web/src/support/localSupportGateway.ts  · implementación temporal + hook useSupport
web/src/support/index.ts                · exporta la frontera
web/src/support/supportGateway.test.ts  · test mínimo del gateway
web/src/pages/SupportPage.test.tsx      · test mínimo de la página
```

### Archivos modificados
```
web/src/pages/SupportPage.tsx           · usa useSupport() en lugar de leer useAuth directamente
```

### Archivos NO tocados (por diseño)
`osap-auth`, `AuthClient`, `useAuth`, `useOidcLogin`, `ApiClient`, `routing`, `i18n`, `Layout`, backend, BD.

---

## 2. Mapa de código (conceptos)

> La SPA actual (`web/`) mezcla Chorus y osap-app. Este mapa es el límite **conceptual** objetivo.

### A. Chorus — experiencia musical
Funcionalidad que representa la **plataforma musical**:

| Área | Páginas / estado |
|---|---|
| Catálogo / obras | `Catalog`-relacionado, `WorkResolutionPage`, estudio (`SearchStudioPage`) |
| Compositores | `ComposersPage`, `ComposerDetailPage`, `ComposerPage`, `AliasPage` |
| Conocimiento | `KnowledgePages`, `HowItWorksPage` |
| Proveedores / fuentes (musicales) | `SourceCatalogPage`, `SourcesPage`, `ProvidersPage` |
| Jobs / resolución | `JobsPage`, `CandidatesPage` |
| Estado musical | `state/{searchModel,searches,sources,repositorySources,providers,composers,work?,knowledge,jobs}` |

> ⚠️ **Criterio:** no todo `web/` es Chorus. El límite exacto (qué página va a Chorus vs osap-app) se reclasificará al definir el plan de extracción físico; este mapa es provisional y deliberadamente conservador.

### B. osap-app — plataforma / aplicación general
| Área | Páginas / estado |
|---|---|
| Administración | `AdminPage`, `AdminComposersPage`, `AdminComposerDetailPage`, `AdminProvidersPage`, `AdminSourceSuggestionsPage` |
| Soporte / ayuda | `SupportPage`, `AboutPage`, `HowItWorksPage` (según decisión) |
| Autenticación | `AuthCallbackPage`, componentes de login/registro/OIDC |
| Preferencias / sistema | `state/{preferences,system}` |
| Estados de plataforma | `state/administration`, `api/` genérico |

### C. Compartido (librería compartida futura)
| Elemento | Path | Notas |
|---|---|---|
| i18n | `i18n/*` | `translations.ts`, `I18n.tsx` (Chorus y osap-app lo reutilizarían) |
| ApiClient | `api/ApiClient.ts` | único acceso HTTP a OSAP (`/api/v1`) |
| AuthClient | `api/AuthClient.ts` | frontera de identidad → Auth |
| types (API contract) | `api/types.ts` | DTOs de la API (independientes del dominio) |
| errors | `api/errors.ts` | envelope/errores |
| identity (UI) | `state/auth.ts` | leer `JWT.sub`, refresh/logout |
| OIDC login | `components/useOidcLogin.ts`, `OidcAuthButton.tsx` | flujo de identidad |
| UI genérica | `components/{Button,Card,Spinner,Loading,EmptyState,...}` | presentación |
| Layout / nav | `layouts/Layout.tsx` | shell / navegación (podría bifurcarse por app) |
| SupportGateway | `support/*` | frontera → futuro `osap-support` (compartida por Chorus y osap-app) |

---

## 3. Matriz de dependencias

| Componente | Chorus | osap-app | Compartido | Dependencias |
|---|---|---|---|---|
| `SupportGateway` (`support/*`) | ✅ consume | ✅ consume | ✅ | `state/auth` (identidad, para `sub`) |
| `SupportPage` | ✅ | ✅ | — | `SupportGateway`, `useOidcLogin`, i18n, forms Auth |
| `ApiClient` | ✅ | ✅ | ✅ | `api/types`, `api/errors`, `AuthHandler` (from `state/auth`) |
| `AuthClient` | ✅ | ✅ | ✅ | llamadas `/auth/*` a `osap-auth` |
| `state/auth` | ✅ | ✅ | ✅ | `AuthClient`, `ApiClient` |
| `useOidcLogin` | ✅ | ✅ | ✅ | `state/auth`, `ApiClient` |
| `i18n/*` | ✅ | ✅ | ✅ | (independiente) |
| `api/types` | ✅ | ✅ | ✅ | (puro) |
| `Layout` | ✅ | ✅ | ✅/rama | `state/auth`, `useOidcLogin`, i18n |
| `routing` | ✅ | ✅ | ✅ | todas las páginas; **no separa Chorus/osap-app hoy** |
| Páginas musicales (Composers, Catalog, Knowledge, Jobs...) | ✅ | — | — | `ApiClient`, `state/*` musical, i18n |
| Páginas admin | — | ✅ | — | `ApiClient`, `state/administration` |
| Backend `osap-api` | ✅ (vía `ApiClient` `/api/v1`) | ✅ (idem) | — | HTTP únicamente |

### Dependencias ocultas (las que impiden separar)
1. **`ApiClient` mezcla todo el contrato OSAP** en un único archivo (catalog+admin+auth+votes). Extraer Chorus no requiere romperlo, pero conviene agrupar métodos por dominio cuando se separe.
2. **`routing` y `Layout`** enrutan todas las apps juntas; separar exige desacoplar el shell (navbar/footer) por aplicación.
3. **`SupportPage` depende de `useOidcLogin`** (Auth) — correcto (identidad), pero al extraer conviene que consuma vía gateway/port Auth para no arrastrar la SPA.
4. **`state/auth` conecta `AuthClient` + `ApiClient`** con side-effects al importar (`apiClient.setAuthHandler`) — portabilidad a otro repo: es reproducir ese wiring, no tocarlo.
5. **`vite.config.ts`** proxy `/api → 127.0.0.1:8001` y nombre de build: en `chorus-web` migraría a URL de entorno.
6. **`import.meta.env`** no se usa; las URLs viven en `ApiClient.API_PREFIX` (constante) — al separar, parametrizar por entorno.

---

## 4. Plan de extracción de Chorus

Objetivo: pasar de `SPA actual (Chorus + osap-app)` → `osap-app` y `chorus-web` **sin romper el backend**.

Fases (cada una reversible y desplegable):

1. **Aislar la SPA como app autocontenida** (dentro de `osap-api/web`): asegurar que `osap-app` (Apache) sigue sirviendo `web/dist`, y que no hay acceso a módulos Python internos desde el front (ya es HTTP-only).
2. **Parametrizar URLs por entorno** en `ApiClient`/`AuthClient` (`API_PREFIX`, origen de Auth) para que el front no dependa de rutas internas del backend.
3. **Desacoplar `Layout`/`routing` en por-app** (nav de Chorus vs nav de osap-app), manteniendo el shell compartido.
4. **Crear `chorus-web` repo** con solo lo de Chorus + dependencias compartidas (i18n, api types, Auth/SupportGateway) como librería o copia versionada.
5. **Apuntar `chorus-web` a OSAP API por entorno** (no al backend interno) y a `osap-auth`.
6. **Apuntar `osap-app`** (lo que no es Chorus: admin, soporte, ajustes) para que consuma igual.
7. **Repartir `SupportGateway`** hacia `osap-support` esté allí; sigue siendo compartido por ambas apps.

Regla de bloqueo: si en algún paso `SupportGateway` o la UI obligan a una refactorización grande, **parar** y documentar la decisión (prioridad: pequeña frontera correcta > gran refactorización prematura).

---

## 5. Frontera Support (futura) — interfaz mínima

La interfaz `SupportGateway` actual es mínima (`getSummary`). Cuando exista `osap-support`, se sustituirá la implementación (`LocalSupportGateway` → `SupportApiClient`). La **API futura mínima** se documenta (no se implementa):

```
GET  /membership/me   → { status, level, ... }      (autenticado, Bearer sub)
POST /membership/checkout → url del proveedor       (futuro, sin implementar)
GET  /community/me / PUT /community/me              (perfil/consentimiento; futuro)
GET  /community/members                             (público consentido; futuro)
```

No se definen más endpoints para no acoplar a una implementación que aún no conocemos.

---

## 6. Riesgos detectados

| Riesgo | Impacto | Mitigación |
|---|---|---|
| `SupportPage` arrastra la SPA al extraer (usos de `useOidcLogin`) | separar es más trabajo | mantener la página; consumir Auth vía gateway/port al extraer |
| `ApiClient` monolítico | romper al separar | agrupar por dominio antes/después, sin reescribir |
| `routing`/`Layout` acoplados | shell difícil de bifurcar | desacoplar nav por app en el paso de extracción |
| `import.meta.env` ausente → URLs hardcodeadas | portabilidad | parametrizar por entorno en el paso 2 |
| Scope creep (gateway → backends) | ampliación no deseada | esta fase **solo frontend**; backend en fase posterior |

---

*Fin de la documentación de la Fase Técnica 1.*
