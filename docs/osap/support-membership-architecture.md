# Chorus — Análisis de suscripciones, comunidad y sostenibilidad

> **Documento de análisis y arquitectura propuesta. Sin implementación todavía.**
> Fecha: 2026-08-28 · Alcance: ecosistema Chorus + Auth + (futuro) Suscripciones + (futuro) Social.

---

## 0. Punto de partida (lo que existe hoy, verificado en código)

### Chorus (osap-api + web)
- **Frontend SPA** en `web/` (React + Vite + Zustand + i18n en `en/es/ca/fr/de`). Rutas en `web/src/routing/routes.tsx`.
- **Navegación principal** (`Layout.tsx`): `/` (Home), `/studio`, `/discover`, `/catalog` (Fuentes), `/composers`, `/knowledge/...`, `/about`.
- `DiscoverPage` (`/discover`): muestra **proveedores NO conectados** (candidatos a fuente con descripción localizada). Prácticamente duplica el propósito de `/catalog`.
- `SourceCatalogPage` (`/catalog`, "Fuentes"): catálogo de fuentes conectadas + proveedores huérfanos, con descripciones localizadas.
- **No existe tabla de "usuarios" en la BD de Chorus/osap-api.**: la identidad del usuario llega solo vía token; no se duplican credenciales.
- Login/registro en la UI se delega a Auth (OIDC popup + a) respaldo email/contraseña b) vía osap-api → osap-auth).

### Auth (osap-auth) — plataforma de identidad INDEPENDIENTE
- **Identidad**: `user.id` UUID. Es el identificador estable que viaja entre aplicaciones en el claim JWT `sub`.
- **Access token claims**: `iss, sub, aud, jti, roles, email_verified, scope, typ, token_use, iat, exp, nonce?`. **No PII** en el token (`email`, `name`, contraseñas están explícitamente prohibidos → `_FORBIDDEN_ACCESS_CLAIMS`).
- **OIDC Identity Provider (IdP)**: `/.well-known/openid-configuration`, `/auth/authorize` (Authorization Code + PKCE), `/auth/authorize/complete`, scopes `openid profile email`. osap-api actúa como *relying party*.
- **OAuth2 `client_credentials`** para M2M (service tokens, `token_use: service`, scopes como `api:read`, `storage:read`, `storage:admin`, `auth:admin`).
- **`/me`** (usuario identificado) devuelve: `user_id, email, name, roles, email_verified, status, created_at`.
- Rutas: `auth` (login/refresh/register/verify), `oidc`, `oauth`, `jwks`, `password_reset`, `social`, `system`, `service_clients`, `service_tokens`, `admin_users`, `sessions`.
- **Modelo de usuario**: `id, email_lookup(HMAC), email_cipher(AEAD), password_hash, status, roles, key_version, name, email_verified_at` → Email cifrado y con lookup por HMAC.

### Integración Chorus ↔ Auth actual
- `web/src/state/auth.ts`: `access_token` en memoria + `refresh_token` en localStorage (rotación). `decodeUser` lee `sub`, `roles`, `email_verified`.
- `web/src/api/AuthClient.ts`: llama a `/auth/login` y `/auth/refresh` vía el mismo origen (proxy `osap-app` → `osap-auth`).
- `useOidcLogin.ts`: abre popup al `/api/v1/auth/oidc/start` de osap-api → redirige a osap-auth authorize → callback → tokens al popup → postMessage → `completeOidc`.
- osap-api valida el token y produce un `Principal` (`UserPrincipal(user_id, roles, email_verified)` o `ServicePrincipal`). Ver `token_authenticator.py`.
- osap-api usa service tokens (`client_credentials`) para hablar con osap-storage (`storage:read`, `storage:admin`) y con osap-auth (M2M).
- **Conclusión clave:** la pieza de identidad ya está resuelta y correcta. Auth es la autoridad única. Solo falta que Chorus "conozca" al usuario identificado por su `sub` (UUID), sin duplicar nada.

---

## A. Arquitectura propuesta

Cada sistema es dueño de una única responsabilidad y hablan por HTTP + JWT (claves firmadas), desacoplados y desplegables por separado.

```
┌───────────────────────────────────────────────────────────────┐
│  AUTH  (identidad)                                            │
│  · registro, login, recuperación, email, roles, sesiones      │
│  · OIDC IdP · OAuth2 client_credentials (M2M)                 │
│  · Fuente de verdad de: id (UUID), name, email, roles, status │
└───────────────────────────────────────────────────────────────┘
        │  user token (Bearer sub=UUID)      ▲ service token (membership)
        ▼                                     │
┌───────────────────────────────────────────────────────────────┐
│  CHORUS  (aplicación musical + comunidad local)               │
│  · catálogo/búsqueda de música                                 │
│  · Página "Apoya Chorus" (contenido, no pago)                 │
│  · Estado de pertenencia para el usuario (leído del proveedor)│
│  · "Descubrir" → primera capa social (personas que apoyan)    │
│  · BD propia: solo datos del perfil de pertenencia PÚBLICO    │
└───────────────────────────────────────────────────────────────┘
        │  service token (membership service)
        ▼
┌───────────────────────────────────────────────────────────────┐
│  MEMBERSHIP / DONACIONES  (proveedor de pagos, EXTERNO)       │
│  · pago, periodicidad, método, recibos, cancelaciones         │
│  · Fuente de verdad de: membership_status, nivel, fechas      │
└───────────────────────────────────────────────────────────────┘
        │  (futuro)
        ▼
┌───────────────────────────────────────────────────────────────┐
│  SOCIAL  (plataforma social futura)                           │
│  · perfiles, opiniones, seguidores, actividad, interacción    │
│  · Usa el MISMO Auth (sub) · el MISMO perfil público          │
└───────────────────────────────────────────────────────────────┘
```

**Reglas de oro:**
1. **Auth → identidad.** Nunca duplicar contraseñas/credenciales ni tabla de usuarios en Chorus.
2. **Membership/proveedor de pagos → fuente de verdad del pago y del estado de suscripción.**
3. **Chorus → solo lo estrictamente necesario** para su UI: estado de pertenencia (léelo, cópialo cacheado) y perfil público (lo que el usuario consintió publicar).
4. **Social futuro → reutiliza Auth (sub) y el perfil público; Chorus NO es la red social.**
5. Cada servicio es un repo/despliegue independiente (misma máquina, distintas máquinas, tecnologías distintas).

---

## B. Flujo de usuario

Flujo recomendado (tras valorar alternativas, ver §"Alternativas de flujo analizadas"):

```
1. USUARIO llega a CHORUS (pública, sin login)
        │
2. Página "Apoya Chorus"  (CHORUS: explica qué es, por qué, qué aporta)
        │  clic "Quiero apoyar"
        ▼
3. AUTH: login/registro/recuperación  (Auth es el único encargado)
        │  → access token (sub = UUID) en la SPA de Chorus
        ▼
4. CHORUS pide al MEMBERSHIP un "pre-checkout link/portal" (M2M, con el sub)
        │  → redirige al proveedor (Stripe/Patreon/Gumroad/...) en una pestaña/vista
        ▼
5. MEMBERSHIP: el usuario paga (envío, periodicidad, método, recibo)
        │  → el proveedor registra la suscripción (single source of truth)
        ▼
6. CHORUS recibe "webhook/evento de pertenencia" (o consulta el estado)
        │  → guarda CACHE de estado (status, nivel, fechas) + consentimiento de publicación
        ▼
7. CHORUS muestra al usuario su estado de pertenencia y le pregunta si quiere
   aparecer públicamente (opción), recorriendo A/B/C de privacidad
        ▼
8. CHORUS "Descubrir" lista a las personas que consintieron ser públicas
```

**Punto clave de diseño:** el paso 6 es dónde Chorus *aplica* el consentimiento y decide qué publicar. No se muestra nada sin consentimiento explícito.

### Alternativas de flujo analizadas

| Variante | Pros | Contras | Veredicto |
|---|---|---|---|
| **Redirección completa a Auth primero** (gate tras "Quiero apoyar") | Responsabilidades claras; Auth decide registro/login | Dos saltos de origen; fricción si el usuario solo explora | Parcial: mantener la página pública y exigir login **solo en el paso 3** |
| Chorus cobra directamente (integrar el proveedor en Chorus) | Menos saltos | Mezcla pagos en Chorus; viola "sin responsabilidades mezcladas"; rehacer cuando llegue Membership | ❌ Descartado |
| Chorus crea su propia tabla de users | Simple | Duplica identidad; rompe "un usuario único"; migración dolorosa | ❌ Descartado |
| El proveedor de pagos es la única fuente y Chorus no cachea | Cero duplicación | Cada render consulta al proveedor; fricción y riesgo de dependencia del pagador | ❌ No; usar cache + webhook |

---

## C. Modelo de datos

### Qué SÍ almacena Chorus (BD propia de Chorus)
Solo lo necesario para la UI y la comunidad. **Sin información de pago.**

```
user_memberships        -- cache de estado (una fila por user sub)
  subscriber_id   UUID  -- = sub del JWT (id de Auth), stable
  membership_status  enum(pending, active, past_due, cancelled, expired, none)
  membership_level    enum(founder, patron, supporter, contributor)  -- ver §F
  started_at  datetime | null
  renewed_at  datetime | null
  expires_at  datetime | null
  updated_at  datetime | null      -- última vez que el proveedor informó
  provider     str | null          -- "stripe" | "patreon" | "gumroad" | ... (solo etiqueta)

user_public_profiles   -- consentimiento + perfil público (Chorus)
  subscriber_id   UUID  PK  = sub
  visibility   enum(anonymous, public_name, custom_name)
  public_name  str | null         -- "Miguel G.", "M. García", "Amigo de Chorus"
  public_bio   str | null         -- pequeña descripción (opcional, solo si visibility != anonymous)
```

- **Caché**: `user_memberships` es un *cache* derivado del proveedor de pagos (vía webhook + refresco). No es la fuente de verdad del pago. Nunca guardamos montos, método de pago, recibos ni datos bancarios.
- **Perfil público**: solo lo que el usuario consintió. El `public_name`/`public_bio` viven en Chorus (o en el futuro Social), decidido en §D/H.

### Qué NO almacena Chorus
- Contraseñas, hashes de contraseña, tokens de Auth (solo el access token en memoria de la SPA).
- Email (salvo que decidamos cachearlo; mejor NO: lo da Auth `/me`).
- Montos, moneda, método de pago, tarjeta/bancos, recibos, dirección, IP de pago.
- El estado detallado de la suscripción del proveedor (nivel, próximas renovaciones) — solo lo mínimo expuesto a la UI.

### Taxonomía de campos propuesta por el enunciado
Se adopta la de la columna "subscriber_id / user_id" con `membership_*`. Conviene **bautizar el identificador como `subscriber_id` o `user_sub`** para dejar claro que es el `sub` de Auth, no un id propio.

---

## D. Identidad (cómo se relacionan Auth, Chorus, Suscripciones y Social futuro)

**Identificador común = `sub` (UUID) emitido por Auth.** Todo el ecosistema lo usa.

```
AUTH  →  user.id (UUID)  →  JWT.sub  →  Chorus, Membership, Social leen "sub"
```

- **Dónde vive el perfil "básico de identidad"**: en Auth (`/me`: name, email, roles, status). No se duplica.
- **Dónde vive el perfil "de comunidad/público"** (nombre público, bio, avatar): consensuamos: puede vivir en **Chorus ahora** (tabla `user_public_profiles`) y **migrar/convivir con Social** cuando exista. Diseñamos la tabla para que Social la lea.
- **Dónde vive la información de membresía**: en el **proveedor de pagos** (fuente de verdad) + **cache en Chorus**.
- **Dónde vive el consentimiento de publicación**: en **Chorus** (tabla `user_public_profiles.visibility`), íntimamente ligado a la membresía activa. Es dato de producto/privacidad de Chorus.
- **Fuente de verdad**:
  - de identidad → Auth
  - de pago/suscripción → proveedor de pagos
  - de qué se muestra públicamente sobre un colaborador → Chorus (consentimiento)
- **Cómo sincroniza la membresía → Chorus**: webhooks/eventos del proveedor + sondeo de refresco (p. ej. al cargar la página de pertenencia o con cadencia diaria) + `user.deleted:subscribe` que ya existe en Auth para borrar filas si el usuario deja el ecosistema.

**Compromiso anti-"tres usuarios":** ningún componente crea usuarios nuevos. Todos referencian por `sub`. Chorus nunca inserta en Auth. Auth nunca conoce de suscripciones. El proveedor de pagos identifica al pagador por `sub` (client_reference_id o customer metadata).

---

## E. Diseño de "Descubrir" — primera capa comunitaria

**Transformar `/discover`** de "proveedores a conectar" a **"Personas que hacen posible Chorus"**.

> La lista de "proveedores a conectar" (que duplicaba Fuentes) se **retira/archiva**: o bien se fusiona dentro de `/catalog` (Fuentes) o se elimina. No tiene valor comunitario y duplica `/catalog`.

### Contenido propuesto de `/discover`
- Título: **"Descubrir — Personas que hacen posible Chorus"** (según idioma).
- Tarjeta por colaborador público (solo `visibility != anonymous`):
  - **Nombre público** (según opción elegida: nombre, alias, "Amigo de Chorus").
  - **Avatar** (si existe; lo cederá Social en el futuro, o Auth/avatar externo — pendiente §H).
  - **Nivel/categoría** (badge visual no económico, §F).
  - **Breve descripción** (bio opcional, solo si la puso).
  - **Enlace a perfil** si existe (en el futuro → Social).
- Orden: no es un ranking económico. Se puede ordenar por antigüedad de apoyo (fundadores primero), para destacar a los "miembros fundadores" como historia, sin insinuar que quien más da es más importante.
- **Nunca** se muestra: cantidad, método de pago, ni nada financiero.

### Compatibilidad con Social futuro
- La tabla `user_public_profiles` se diseña para ser EL perfil público también consumible por Social.
- `/discover` es una *lectura* de esa tabla; cuando llegue Social, el listado podrá delegarse o enriquecerse sin rehacer el consentimiento.

---

## F. Niveles de apoyo

No se quiere un ranking económico. Varias alternativas de **categorías de contribución** (no de logro monetario):

**Propuesta 1 — Estrellas (del enunciado):** ⭐ Colaborador · ⭐⭐ Impulsor · ⭐⭐⭐ Mecenas.
- Conveía jerarquía ascendente. Riesgo: sugiere "quien más da, más vale".

**Propuesta 2 — Instrumental/musical (recomendada):**
- **Fila del coro** (nuevo en el coro) · **Segunda voz** (armoniza) · **Director/a** (guía el proyecto).
- Transmite roles en un conjunto musical: todos son necesarios, ninguno superior. Encaja con la filosofía.

**Propuesta 3 — Etapas culturales / comunidad:**
- **Alborada** · **Luz de escenario** · **Coro entero** · (o "Amigo", "Coprotagonista", "Autor/a").
- Poético pero menos claro.

**Propuesta 4 — Iconos/instrumentos sin nombre jerárquico:**
- 🎶 · 🎼 · 🎻 · 🎺 (cada nivel un icono distinto, sin orden implícito).
- Visual, neutral, pero sin significado de "más implicación".

### Recomendación
**Niveles musicales + un distintivo único de fundador.** Concretamente:

| Nivel | Nombre (propuesta) | Idea | Uso |
|---|---|---|---|
| — | **Miembro fundador** | distintivo histórico (temporal), ver §"Fundadores" | solo primeros apoyos |
| N1 | **Amigo de Chorus** | donación puntual / apoyo esporádico | any |
| N2 | **Voz del coro** | aportación mensual recurrente | subscribe monthly |
| N3 | **Director/a de Chorus** | aportación mensual/anual superior, rol de guía | subscribe |

Se muestra como **badge de comunidad** (nombre + color/icono), nunca como "cantidad". El criterio objetivo asigna nivel por el *tipo de compromiso* (puntual vs recurrente) y por el umbral interno del proveedor, pero la UI solo muestra el **badge**, no montos.

---

## G. Privacidad

Exactamente qué se puede hacer público y qué jamás:

### Opciones (Chiastica, claro)
- **A — No aparecer** (`visibility = anonymous`): nada público. Fila de membresía existe pero no se lista.
- **B — Con su nombre** (`public_name` = su nombre/alias natural).
- **C — Con un nombre elegido** (`public_name` = "Miguel G.", "M. García", "Amigo de Chorus"...).

### Reglas
- El **default es siempre A (privado)**. Se publica solo tras consentimiento explícito, y solo mientras la pertenencia esté activa (si cancela/ex_pira, se oculta automáticamente).
- El usuario puede cambiar de A/B/C en cualquier momento.
- **Nunca público:** cantidad aportada, moneda, método de pago, tarjeta/bancos, recibos, dirección, email, IP, historial de pagos, notas internas.
- `public_bio` solo se muestra si no es anónimo.
- Los listados públicos (`/discover`) solo leen `user_public_profiles` y el **badge** de nivel (de `user_memberships`), nunca datos de pago.

---

## H. Integración futura con Social (evitar rehacer)

Principios para que lo construido **ahora** sea pieza natural del ecosistema:

1. **Identidad única**: todo refiere por `sub`. Cuando Social exista, sus perfiles usarán el mismo `sub` y podrán leer `user_public_profiles`.
2. **El perfil público se "aloja" conceptualmente en un lugar neutral**: hoy lo implementamos en Chorus, pero lo modelamos como **perfil de comunidad desacoplado** (tabla propia, API separada opcional). Social podrá leerlo o asumirlo como su fuente inicial sin rehacer el consentimiento.
3. **El consentimiento de publicación vive en una tabla dedicada** (`user_public_profiles.visibility`) → Social la respeta igual.
4. **La membresía es de Membership, no de Chorus ni de Social.** Ambos la consumen por `sub`. Nunca dos tablas de membresía.
5. **API estable de Chorus para comunidad** (`community/*`): si Chorus expone "lista de colaboradores públicos" como endpoint neutral, Social podrá delegar en él o duplicarlo.
6. **Nada propietario**: no dependemos de Vercel; todo en env/BD/API documentadas, portable (cf. §14 del enunciado).

**Resultado:** cuando llegue Social, `sub` conecta, el perfil público se hereda, el consentimiento se respeta y la membresía no se duplica. Solo se añaden las capacidades nuevas (seguidores, opiniones, actividad) sobre esa base.

---

## I. Plan de implementación

**Fases (cada una con entregable desplegable y reversible):**

### Fase 1 — Arquitectura (fundación)
- Documento de contrato de identidad entre Chorus/Membership/Social (este doc → ampliar a `docs/osap/support-membership.md`).
- Crear tabla `user_memberships` + `user_public_profiles` (migración en la BD de osap-api/Chorus).
- Definir el *puerto/interface* de proveedor de pertenencia (CSPI) en Chorus (abstracción para Membership), con implementación falsa/in-memory primero (dev).

### Fase 2 — Página de apoyo
- Nueva ruta `/support` (o `/about/support`). Contenido no agresivo:
  - Qué es Chorus; por qué necesita apoyo (infra, servidores, desarrollo, mantenimiento, investigación, tiempo); filosofía "apoyar la continuidad" (no "pagar para desbloquear").
  - Enlaces: "Iniciar sesión / crear cuenta" (→ Auth) y, si identificado, botón "Empezar a apoyar" (→ Membership).
- i18n en los 5 idiomas.

### Fase 3 — Integración Auth (identidad en Chorus)
- Reforzar que Chorus lee la identidad SOLO del token (`sub`) y de `/me` (name) cuando lo necesite.
- Endpoint de Chorus `POST /api/v1/auth/oidc/start` ya existe; asegurar que la página de apoyo usa el login OIDC/Auth sin embargo en Chorus no crea usuarios.
- Backend: exponer `GET /api/v1/me` (devuelve `sub`, roles, etc. desde el token; sin PII extra).

### Fase 4 — Integración pagos (Membership)
- Elegir proveedor (Stripe / Patreon / Gumroad / Ko-fi / GitHub Sponsors) — decisión posterior.
- Conectar webhook de pertenencia → Chorus actualiza `user_memberships` (cache) y (si el usuario consintió) `user_public_profiles`.
- Tanto el pre-checkout link → redirige a Membership, y el "portal de gestión" (cancela, cambia método) vuelve a Membership.
- **Chorus nunca toca el pago directamente.**

### Fase 5 — Miembros públicos ("Descubrir" transformado)
- Migrar `/discover` a vista comunitaria (personas que apoyan).
- Flujo de consentimiento A/B/C + bio + avatar opcional.
- Badges de nivel (§F) y distintivo de fundador (§"Fundadores", para los que entren en la ventana fundacional).

### Fase 6 — Preparación para Social
- Endpoint `GET /api/v1/community/members` neutral.
- Documentar el contrato de perfil público para que Social lo consuma.
- Revisar que `user_public_profiles` sea suficiente o extraerla a un "Perfil/PerfilSocial" cuando exista.

---

## Anexos

### Fundadores (foco del enunciado)
- **Definición objetiva**: "Miembro fundador" = personas con una pertenencia activa (puntual o recurrente) **dentro de una ventana temporal fija** (p. ej. primeros N meses desde el arranque público o hasta llegar a un hito, documentado). El criterio es **fecha objetiva de comienzo de apoyo**, no importe.
- **Evitar problemas**: la ventana y el criterio se fijan y publican en su momento; una vez cerrada, no se abren extendiendo "fundador" retroactivamente. Es un sello histórico (no un nivel económico ascendente).
- Se guarda `membership_level = founder` con `started_at`; la UI lo muestra como badge de historia ("Miembro fundador de Chorus"), no como jerarquía.

### Responsabilidades por sistema (resumen "quién hace qué")
| Acción | Auth | Chorus | Membership | Social (futuro) |
|---|---|---|---|---|
| Registro / login / recuperación | ✅ | — | — | — |
| Identidad / perfil básico | ✅ | — | — | — |
| Explicar proyecto y valor de apoyo | — | ✅ | — | — |
| Iniciar suscripción | — | ✅ (botón) | — | — |
| Pago, periodicidad, método, recibos, cancelación | — | — | ✅ | — |
| Estado de pertenencia (lectura UI) | — | ✅ (cache) | ✅ (verdad) | — |
| Consentimiento de publicación | — | ✅ | — | — |
| Perfil público / "Descubrir" | — | ✅ | — | ✅ (heredera) |
| Red social (perfiles, opiniones, seguidores) | — | — | — | ✅ |

---

*Fin del análisis. Sin cambios de código todavía.*
