# OSAP — Separación de Chorus y diseño del servicio OSAP Support/Membership

> **Documento de propuesta arquitectónica. Sin cambios de código (regla principal respetada).**
> Referencias: `docs/osap/support-ecosystem-architecture.md`, `docs/osap/support-tech-plan.md`,
> `docs/osap/support-phase1-support-page.md`, `docs/chorus-vision.md`, `docs/osap/adr/0001-osap-chorus-independent.md`,
> `docs/_ingresos/idea.md`.
> Fecha: 2026-08-29

---

## A. Diagnóstico — por qué el proyecto está creciendo demasiado

**Evidencia (conteo en los repos, excluyendo `.venv`/`node_modules`/`dist`/`__pycache__`):**

| Área | Tamaño |
|---|---|
| `osap-api/src/osap` (backend Python: domain/ports/application/infrastructure/api/bootstrap/cli) | cientos de `.py` (100+ listados ya) |
| `osap-api/web/src` (SPA: pages/components/state/api/i18n/routing/layouts + tests) | ~110 `.ts/.tsx` |
| `osap-api/docs` (+ ~35 ADR) | 100+ `.md` |
| `osap-api/providers` | varios YAML |
| `osap-storage` / `osap-auth` | backends propios |

**Causas raíz:**
1. **Un único repo «osap-api» mezcla varios productos y capas**: backend de la plataforma (domain/ports/application/infrastructure), la API REST, el bootstrap (wiring/container/config), la SPA web (osap-app) y contenido conceptual de Chorus.
2. **Dos dominios conviven en el mismo frontend**: funcionalidad musical (catalog, composers, studio, knowledge, resolution, jobs, admin) y la emergente de apoyo (`/support`).
3. **Docs y ADRs numerosos** dentro del mismo árbol.
4. **VS Code indexa este conjunto completo**, superando su umbral de rendimiento.

**Conclusión:** no sobran "archivos sueltos"; sobran **productos y responsabilidades dentro de un mismo árbol**. Separar por capas/repos reducirá el índice por proyecto, facilitará el desarrollo, el mantenimiento y el despliegue, y permitirá trabajar en Chorus sin cargar todo el ecosistema.

---

## B. Separación de Chorus — qué es y qué debería salir

### B.1 Aclaración crítica (no ocultar)
Hoy **«Chorus» y «osap-app» son la misma SPA** (`web/`, servida por el VirtualHost `osap-app`). Según `chorus-vision.md` y ADR-0000/0001, **Chorus** es la aplicación musical de estudio coral que *consume* OSAP vía API, mientras **OSAP** es la plataforma reutilizable. En el estado actual del repo **no existe un frontend Chorus independiente**: Chorus se materializa como parte de la SPA/web y de la funcionalidad musical del backend.

Por tanto, la «separación de Chorus» exige **decidir qué es Chorus**:
- **Opción 1 (recomendada para tiempo):** Chorus = experiencia de usuario musical = la SPA `web/` actual. «Separar Chorus» = extraer la SPA a un repo `chorus-web`/`osap-app` que consuma la API de OSAP.
- **Opción 2:** Chorus = un **frontend nuevo futuro** que usará OSAP (aún no existe como repo; se crearía).
- **Opción 3 (paso intermedio recomendado):** mantener ambos en el monorepo por ahora, **reorganizando por capas**, y diseñar los repos objetivo para migrar después sin romper nada.

Recomendación para esta fase: **no mover todavía** la SPA entera (cambio grande y arriesgado); organizar el monorepo por capas y documentar los repos objetivo.

### B.2 Qué pertenece a cada parte (según el repo)

| Código | Pertenece a | Motivo |
|---|---|---|
| `src/osap/domain`, `ports`, `application`, `infrastructure`, `api`, `bootstrap` | **OSAP backend/API** | motor musical, catálogo, resolución, conocimiento |
| `src/osap/api/platform_app.py`, `platform.py` | **OSAP API** | API REST de la plataforma |
| `web/src` (frontend completo: música, studio, catalog, composers, knowledge, jobs, admin, `/support`) | mezclado → **osap-app / Chorus web** | frontend de usuario |
| `providers/` (YAML) | **OSAP backend** | fuentes del catálogo |
| `docs/_ingresos/*` | **OSAP Support** (estrategia de producto) | sostenibilidad |
| `osap-storage` | **OSAP backend** | catálogo/datos musicales |
| `osap-auth` (repo propio) | **Auth** | identidad |

### B.3 Componentes compartidos (no duplicar)
- **i18n** (`translations.ts`): extraer a librería compartida si hay dos frontends.
- **`useAuth` / `AuthClient` / `useOidcLogin`**: identidad → consumen Auth.
- **`ApiClient` + `types`**: contrato API.
- **`SupportGateway` (interfaz)**: frontend → OSAP Support (lo comparten osap-app y Chorus).

### B.4 Dependencias ocultas (las relevantes)
1. El backend valida el JWKS de Auth (`token_authenticator`). Chorus separado seguirá dependiendo de **Auth**, no de osap-api.
2. `osap.api.platform` + `wiring` acoplan toda la plataforma (catalog, storage, auth, votes, knowledge). Es el "coágulo"; hay que consumirlo por API antes de separar el frontend.
3. Storage se accede vía OSAP con scope token; Chorus debe ir a través de la API de OSAP, no a storage directamente.
4. La SPA ya habla por HTTP a `/api/v1/...` vía `osap-app` → la separación es viable (frontera ya existe).
5. **No hay subsistema de email ni de pagos en ningún sitio** (verificado por grep en osap-api y osap-auth) → Support es greenfield.
6. **Auth ya emite OIDC/JWT y service tokens** → no hay que rehacer identidad.

---

## C. Arquitectura OSAP Support / Membership

```
                     AUTH (identidad)
                        │  sub (UUID) / JWT / /me
                        ▼
┌─────────────────────────────────────────────┐
│        OSAP SUPPORT / MEMBERSHIP            │
│  · relación de apoyo persona ↔ ecosistema   │
│  · membresías / donaciones / modalidad      │
│  · agrega al proveedor de pagos             │
│  · historial de eventos                     │
│  · email transaccional de pertenencia       │
└───────────────┬─────────────────────────────┘
                │  API (Bearer sub / service token)
   ┌────────────┴────────────┐
   ▼                         ▼
osap-app                  Chorus
   └───────────┬────────────┘
               ▼
          Social (futuro)
```

- **Es** la fuente de verdad de "¿quién apoya y en qué estado?" y de la comunicación de pertenencia.
- **No es** identidad (Auth), no cobra directamente (proveedor de pagos), no es red social.
- **Dónde vive:** como **servicio independiente** (repo + BD + API propias). En esta fase se **especifica** sin crearlo físicamente (no hay pago aún). Nombre recomendado: **OSAP Support (`osap-support`)**, más amplio que "membership".

---

## D. Datos — dónde vive cada tipo de información

| Información | Responsable |
|---|---|
| Identidad / login / Google / GitHub / sesión | **Auth** |
| Relación de apoyo (membresía, estado, nivel, modalidad, fechas) | **OSAP Support** |
| Pago real / tarjeta / datos sensibles | **Proveedor de pagos** |
| Emails de pertenencia | **Support** |
| Datos musicales | **OSAP / storage** |
| Funcionalidad de aplicación | **osap-app** |
| Comunidad futura | **Social** |

Regla: Support **no** almacena innecesariamente tarjeta/CVV/datos bancarios/credenciales de pago. Guarda `sub`, estado, nivel, modalidad, fechas, `customer_id`/`subscription_id` y, si conviene, etiqueta de importe/periodicidad. **Nunca** los datos sensibles del proveedor.

---

## E. Emails — quién los genera y quién los envía

**Estado actual:** no existe ningún subsistema de envío de email (verificado: nada de `smtp`/`smtplib`/`EmailMessage`/`sendmail` en osap-api ni osap-auth). La verificación de email de Auth **devuelve el token al cliente** (no se envía por SMTP).

**Propuesta (evitar `Chorus→emails`, `osap-app→emails`, `Auth→emails económicos`):**
```
OSAP SUPPORT
   │  orquesta los emails de pertenencia
   ▼
Email Service (módulo dentro de Support o servicio independiente)
   ├── bienvenida
   ├── agradecimiento
   ├── confirmación de aportación
   ├── recordatorio de renovación
   ├── pago fallido
   └── cancelación
```

**Recomendación:** un **módulo de email dentro de Support** (interfaz `EmailSender`), no un servicio separado al inicio: son comunicaciones de pertenencia (responsabilidad de Support) y se puede extraer a colas/servicio cuando el volumen crezca. **Sin elegir proveedor de email todavía.** Auth no emite emails económicos.

---

## F. Pagos — quién gestiona el proveedor y los webhooks

- **Support** es el **único** que integra el proveedor: crea el `checkout`, recibe los **webhooks** (`subscription.created`, `payment.succeeded`, `payment.failed`, `subscription.renewed`, `subscription.cancelled`, `subscription.expired`, `customer.subscription.deleted`) y mapea `customer_id`/`subscription_id` al `sub`.
- **Chorus y osap-app** nunca hablan con el proveedor; solo consultan Support (`GET /membership/me`).
- **Auth** jamás interviene en pagos.
- **No elegir proveedor todavía** (Stripe / Patreon / Ko-fi / Gumroad / GitHub Sponsors). Se decide en Fase de pagos comparando webhooks, niveles, regionalidad y coste.

---

## G. API — cómo se comunican Auth, Support, osap-app y Chorus

### Relaciones
```
Auth ──(JWT / OIDC / /me)──▶ osap-app, Chorus, Support
Support ──(secreto / firma webhook)──▶ proveedor de pagos
osap-app / Chorus ──(Bearer sub)──▶ Support
osap-app / Chorus ──(Bearer sub / service)──▶ OSAP API (música)
```

### Endpoints Support (propuesta, no definitiva)
| Endpoint | Consume | Provee | Auth | Devuelve | Nunca devuelve |
|---|---|---|---|---|---|
| `GET /api/v1/support/status` | apps | Support | pública/Bearer | qué ofrecen / cómo apoyar | — |
| `GET /api/v1/membership/me` | apps | Support | Bearer `sub` | status, level, modalidad, fechas | montos, historial completo |
| `POST /api/v1/membership/checkout` | apps | Support | Bearer `sub` | url del proveedor + return_url | — |
| `POST /api/v1/membership/webhook` | proveedor | Support | firma del proveedor | actualiza estado | — |
| `GET /api/v1/community/me` | apps | Support | Bearer `sub` | perfil público (consentimiento) | datos económicos |
| `PUT /api/v1/community/me` | apps | Support | Bearer `sub` | ok | — |
| `GET /api/v1/community/members` | apps | Support | pública/service | perfil público solo consentido | email, id privado, datos de pago |

- **Formato/errores:** envelope `{ data }` / `{ code, message }` (consistente con osap-api); `401/403/404/409/502/503`.
- **Versionado:** `/api/v1/...`.
- **Portabilidad:** URL de Support por **entorno**; las apps solo cambian la URL, no la lógica.

**Qué puede consultar cada app:** todas pueden leer `status` y `membership/me` para mostrar "Gracias por apoyar OSAP" / "Colaborador de OSAP". Support no expone el historial completo de pagos a las apps (solo a su propio panel/admin). Social lee `status`+`level` y el perfil público consentido, nunca historial económico.

---

## H. Repositorios (propuesta)

Para reducir el tamaño indexado por proyecto y separar responsabilidades:

### Monorepo de capas (paso recomendado ahora)
```
AI_OSAP/
├── osap-auth/        · identidad (repo propio)
├── osap-api/         · OSAP backend + API (reducido: src backend + API, sin web cargada por separado)
│   └── web/          · osap-app SPA (a extraer → chorus-web/osap-app)
├── osap-storage/     · catálogo (repo propio)
└── osap-support/     · (nuevo) apoyo/membresía del ecosistema
```

### Repos objetivo (tras validar)
1. `osap-auth` (existente)
2. `osap-api` (backend plataforma + API; sin web)
3. `osap-storage` (existente)
4. `osap-app` / `chorus-web` (la SPA; frontend usuario)
5. `osap-support` (nuevo servicio de apoyo + email + agregación de pagos)
6. `osap-social` (futuro)

Beneficio: VS Code indexa un proyecto por vez (menor tamaño), se trabaja en Chorus sin cargar todo, mantenimiento y despliegue por capas, Support portable a otra máquina.

---

## I. Migración — plan para separar sin romper nada

Principio: **no mover código hasta validar** esta propuesta; cuando se apruebe, migrar de forma incremental y no destructiva:

1. **Congelar la arquitectura** (este doc). No crear Support ni extraer web todavía.
2. **Aislar la SPA** (`web/`) como app autocontenida dentro de osap-api; asegurar que `osap-app` sigue sirviendo `dist`. Separa frontend de backend sin romper el despliegue.
3. **Definir `SupportGateway` (frontend)** como interfaz para que osap-app y Chorus no dependan del proveedor.
4. **Cuando exista pago**, crear **`osap-support`** (repos + BD + API + email) sin tocar Auth ni las apps; apuntar `SupportGateway` a su API.
5. **Despegar la SPA a repo independiente** cuando el frontend ya no tenga acoplamiento por rutas internas (consuma API por URL de entorno).
6. **Crear `chorus`** (si se decide frontend separado) reutilizando SPA/librerías compartidas (i18n, auth, SupportGateway).
7. **Docker/entorno:** variables de entorno para URLs (Auth, OSAP API, Support) y, luego, Docker para Support.

Garantía: en cada paso algo queda desplegable y reversible; Auth, osap-app, APIs y BD se preservan.

---

## J. Fases — qué implementar primero

```
Fase 1 · Arquitectura .......... este documento + validación (sin código)
Fase 2 · Apoyo (frontend) ...... página pública "Support OSAP"; login vía Auth; estados
                                  autenticado/no autenticado; SupportGateway (interfaz)
Fase 3 · Identidad/reuso ....... asegurar que osap-app y Chorus se identifican por sub
Fase 4 · OSAP Support .......... crear el servicio: memberships + API + contrato (sin elegir proveedor)
Fase 5 · Pagos ................. integrar un proveedor + webhooks → Support actualiza estado;
                                  emails de pertenencia
Fase 6 · Comunidad ............. public_profiles (consentimiento) + "Descubrir"/comunidad
Fase 7 · Social ................ heredar identidad, perfil y membresía; añadir interacción
```

**Estado:** la Fase 2 ya está parcialmente hecha (página `/support` con login por Auth en la SPA de osap-api).

---

## Fuente de verdad (tabla final)

| Información | Responsable |
|---|---|
| Identidad / Login / Google / GitHub / sesión | Auth |
| Membresía / Estado económico (no sensible) | OSAP Support |
| Pago real / tarjeta / datos sensibles | Payment Provider |
| Emails de pertenencia | Support |
| Datos musicales | OSAP / storage |
| Datos propios de aplicación | osap-app |
| Comunidad futura | Social |

Esta tabla se **mantiene de la propuesta previa** porque el análisis técnico la confirma (no se hallaron razones técnicas para moverla).

---

## Decisiones que requieren tu intervención

1. **Qué es "Chorus" ahora:** ¿la SPA actual (`web/`), un frontend nuevo futuro, o se mantiene como parte del monorepo por ahora? *(Recomiendo: mantener por ahora; extraer después.)*
2. **Nombre del servicio de apoyo:** `osap-support` vs `osap-membership`. *(Recomiendo `osap-support`.)*
3. **Email:** ¿módulo dentro de Support (recomendado) o servicio independiente? *(Recomiendo módulo primero.)*
4. **Monorepo vs repos separados ahora:** *(Recomiendo: no mover aún; validar la arquitectura.)*

---

*Fin de la propuesta. Sin cambios de código.*
