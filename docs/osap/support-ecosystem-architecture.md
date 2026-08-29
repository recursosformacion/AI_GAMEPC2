# OSAP — Sistema común de apoyo del ecosistema (osap-app + Chorus)

> **Documento de análisis y arquitectura. Sin cambios de código todavía.**
> Fecha: 2026-08-28
> Alcance: decidir dónde vive el apoyo/membresía que comparten **osap-app** y **Chorus**.

---

## 0. Aclaración de conceptos (naming)

Para no arrastrar ambigüedad, fijamos la terminología **tal y como está en el código y docs**:

| Término | Qué es | Dónde vive hoy |
|---|---|---|
| **OSAP** | Plataforma abierta y reutilizable (backends). | `osap-api`, `osap-storage`, `osap-auth` |
| **osap-app** | Aplicación de usuario (la SPA) servida sobre OSAP. | `web/` de osap-api, VirtualHost `osap-app` (`app.name = "OpenMusicRepository"`) |
| **Chorus** | Aplicación musical especializada que consume OSAP (visión ADR-0000/0001). En el repo actual, todo vive en osap-api (`web/`+ backend). | mismo repo osap-api (frontend + core) |
| **Auth** | Plataforma de identidad independiente. | `osap-auth` (repo propio) |

**Lectura clave:** según ADR-0001, **OSAP es la plataforma reutilizable y Chorus/osap-app son aplicaciones que la consumen**. A efectos de apoyo, osap-app y Chorus son **dos aplicaciones del mismo ecosistema** → comparten identidad (Auth) y, en el futuro, **un único apoyo/membresía**.

---

## 1. Arquitectura actual (osap-app + Chorus + Auth)

```
                 ┌─────────────────────────────────────────────┐
                 │                AUTH (osap-auth)             │
                 │  identidad · registro · login · sesiones     │
                 │  OIDC IdP · OAuth2 client_credentials        │
                 │  user.id (UUID) → JWT.sub · /me              │
                 └─────────────────────────────────────────────┘
                       ▲  user token        ▲ service token
                       │  (Bearer, sub)     │  (client_credentials)
        ┌──────────────┴─┐           ┌──────┴──────────┐
        │    osap-app    │           │  OSAP backend   │
        │    (SPA web)   │  HTTP     │  osap-api       │
        │  /catalog,     │◀─────────▶│  · core musical  │
        │  /composers,   │           │  · autoriza      │
        │  /discover,    │           │  · op_store (BD) │
        │  /support(...) │           │  osap-storage    │
        └────────────────┘           │  (catálogo)      │
                                     └──────────────────┘
```

**Cómo se identifica el usuario hoy (verificado en código):**
- JWT access token (Bearer) con claims: `iss, sub, aud, jti, roles, email_verified, scope, typ, token_use, iat, exp`. **Sin PII** (`email`/`name` prohibidos por `_FORBIDDEN_ACCESS_CLAIMS`).
- osap-api valida el token localmente contra el JWKS de Auth y produce `UserPrincipal(user_id=sub, roles, email_verified)` o `ServicePrincipal`.
- La SPA guarda access token en memoria + refresh en `localStorage` (rotación). Lee `sub/roles/email_verified` con `decodeUser`.
- Flujo de identificación: OIDC popup (`/api/v1/auth/oidc/start` → osap-auth authorize → callback → postMessage → `completeOidc`) + respaldo email/contraseña (`/auth/login`, `/auth/refresh`).
- **osap-app/Chorus NO tienen tabla de usuarios.** Su BD propia (`op_store` de osap-api) guarda solo `user_id` opaco (UUID) donde lo necesita (por ejemplo `votes.user_id`), nunca email/credenciales.

**BD:**
- osap-api: tablas operativas propias por Python (`op_store.py`, `resolution_store.py`), MySQL con fallback en memoria. Sin tabla de usuarios.
- osap-storage: catálogo/composers (BD propia).
- osap-auth: identidad (tablas de Auth, repo propio).
- osap-app: no tiene BD propia (es la SPA sobre osap-api).

---

## 2. Arquitectura propuesta (sistema común de apoyo)

En vez de "Chorus → Membership" (el planteamiento previo), proponemos **un servicio de membresía del ecosistema**, compartido por osap-app y Chorus. Se barajaron también otras opciones (ver §3); esta es la más sencilla que satisface "no rehacer después".

```
                    AUTH (osap-auth)
                   identidad única
                        │  sub (UUID) / JWT / /me
                        ▼
        ┌──────────────────────────────────┐
        │   OSAP-MEMBERSHIP / OSAP-SUPPORT│
        │   (servicio del ecosistema)      │
        │   · membresía · consentimiento   │
        │   · fuente de verdad del apoyo   │
        │   · agrega al proveedor de pagos │
        └───────────────┬──────────────────┘
                        │  API (service token, sub)
          ┌─────────────┴─────────────┐
          ▼                           ▼
      osap-app                     Chorus
      (status de colaborador)     (status + comunidad)
          └─────────────┬─────────────┘
                        ▼
                 Social (futuro)
                 · perfiles · actividad
```

**Principio rector (la respuesta a la REGLA PRINCIPAL):**

> La arquitectura más sencilla que permite a osap-app y Chorus compartir una misma identidad,
> un mismo sistema de apoyo y dejar preparada Social es: **Auth = identidad** (ya resuelto) y
> **un único servicio de membresía del ecosistema** (`osap-membership`) como fuente de verdad
> del apoyo, con la comunidad/perfil público desacoplada (mismo servicio o adjunto) para que
> Social la herede. Las aplicaciones (osap-app, Chorus) solo **leen** el estado y exponen
> páginas de apoyo.

Se descarta duplicar membresía dentro de osap-app o Chorus porque ambas son aplicaciones de un mismo ecosistema: **una persona = una identidad = una relación de apoyo**.

---

## 3. Alternativas — dónde vive Membership

### Opción A — dentro de Chorus
- **Pros:** rápido de arrancar; Chorus ya tiene la futura página de apoyo.
- **Contras:** osap-app tendría que consumir un servicio "de Chorus" (inversión de dependencia rara: la plataforma dependería de la aplicación); acoplaría comunidad a datos musicales; Social tendría que integrarse con Chorus. Rompe el desacople ADR-0001.
- **Complejidad:** baja ahora, alta después. **Portabilidad:** media.

### Opción B — dentro de osap-app
- **Pros:** concentra la UX de apoyo en la app principal.
- **Contras:** osap-app es la SPA frontend; meter pagos ahí mezcla responsabilidades; Chorus (aplicación hermana) dependería de osap-app. Mismo inconveniente inverso que A.
- **Complejidad:** baja ahora, media después. **Portabilidad:** media-baja.

### Opción C — servicio independiente `osap-membership` / `osap-support`
- **Pros:** fuente única y neutral del apoyo para toda la familia (osap-app, Chorus, Social); BD/API/despliegue propios → máxima portabilidad (misma o distinta máquina, distinta tecnología); se puede trasladar sin tocar las apps; Social lo hereda limpio; el proveedor de pagos se abstrae dentro.
- **Contras:** más trabajo inicial (nuevo componente); hay que definir contrato API desde el principio.
- **Complejidad:** media-alta inicial, menor a largo plazo. **Portabilidad:** alta. **Consecuencias futuras:** mínimas rehacer.

### Opción D — iniciar dentro de un proyecto con interfaz de extracción posterior
- **Pros:** funciona ya; interfaz preparada para extraerlo.
- **Contras:** el riesgo es que "después" no llegue y quede acoplado; requiere disciplina para no tocar tablas directamente desde la app.
- **Complejidad:** media. **Portabilidad:** alta si se respeta la interfaz.

### Recomendación
**Opción C (servicio independiente `osap-membership`), pero con un matiz de la D:** modelarlo como servicio/API independiente **desde el principio** (contrato claro), aunque inicialmente pueda alojarse/desarrollarse junto al resto para arrancar más rápido. La interfaz es la clave: osap-app, Chorus y Social consumen la **API de membresía**, nunca tablas ajenas.

---

## 4. Recomendación concreta

**Crear un servicio `osap-membership` (llamémoslo "Apoyo OSAP"), independiente:**

- **Responsabilidad única:** membresía/apoyo del ecosistema + consentimiento de publicación + perfil de colaborador público.
- **Consume**: Auth (identidad) y el **proveedor de pagos** (externo, a elegir luego) como única fuente del pago.
- **Expone API** a osap-app, Chorus y Social.
- **No mezcla**: no autentica (Auth lo hace), no cobra directamente (proveedor lo hace), no es red social.

**Por qué:** es la única opción que ofrece una **única identidad, una única relación de apoyo y portabilidad total** para osap-app + Chorus + Social futuro, sin rehacer. La premisa del enunciado (osap-app y Chorus comparten apoyo) exige que la membresía esté **por encima** de ambas apps.

**Cuándo:** en esta fase NO se crea todavía (sin proveedor de pagos). Pero sí se documenta el contrato y se prepara la página de apoyo para que apunte al flujo correcto en el futuro.

---

## 5. Flujo de usuario (desde cualquier app)

```
Usuario entra en osap-app  ──o──  Usuario entra en Chorus
        │                                    │
        ▼                                    ▼
   "Apoya OSAP" (página de apoyo, pública)    │
        └──────────────┬─────────────────────┘
                       ▼
              AUTH: registro / login / recuperación
                       │  (Auth es la única identidad)
                       ▼
          JWT.sub = UUID único ──(misma identidad)──▶
                       ▼
       OSAP-MEMBERSHIP: "checkout" → proveedor de pagos
                       │  (pago: única fuente económica)
                       │  (webhook → membership guarda estado)
                       ▼
      osap-app: "Gracias por apoyar OSAP"
      Chorus:   "Colaborador de OSAP" (+ comunidad si consiente)
      Social:   (futuro) badge de colaborador
```

**Minimizar fricción:**
- La página de apoyo es pública y explica el proyecto **antes** de pedir login.
- El login se pide solo en el paso de identificación (botón "Quiero apoyar").
- Tras el pago, se redirige a **la app de origen** (`redirect_return`), conservando el contexto.
- El estado de apoyo se refresca con caché + webhook, sin bloquear la lectura pública.

---

## 6. Identidad — uso de `Auth.sub`

- **Identificador único:** `JWT.sub` = `user.id` de Auth (UUID).
- osap-app, Chorus, Membersip y Social referencian al usuario SOLO por `sub`.
- **Ninguna** de estas apps crea otra identidad.
- Si una app necesita email/nombre → `GET /auth/me` bajo demanda. Nunca del token.
- Los tokens de servicio (`client_credentials`) se usan para M2M (osap-membership → Auth; apps → membership). Nunca se reenvía el access token de usuario entre servicios.

**Relación identidad ↔ apoyo:** `membership.subscriber_id = Auth.sub`. El proveedor de pagos identifica al pagador mediante `sub` (client_reference_id / customer metadata). Auth **no** gestiona pagos ni pertenencia.

---

## 7. Modelo conceptual de datos (sin implementar)

La información vive **por servicio**, evitando migraciones futuras de Social:

```
Auth  (osap-auth)
   users      → id (UUID), email cifrado, name, roles, status, ...

OSAP-Membership  (servicio del ecosistema)
   memberships
       subscriber_id UUID PK   = sub
       membership_status enum(pending, active, past_due, cancelled, expired, none)
       membership_level enum(supporter, contributor, voice, founder, ...)   [ver §13]
       started_at / renewed_at / expires_at / updated_at
       provider          (etiqueta del proveedor de pagos)
       is_founder bool   (criterio temporal, ver §14)
   public_profiles
       subscriber_id UUID PK
       visibility enum(anonymous, public_name, custom_name)   DEFAULT anonymous
       public_name str | null
       public_bio  str | null
       avatar_url str | null      (originado por perfil/avatar, no por el pago)

Chorus (osap-api)
   musical data (scores, works, composers, providers...)

osap-app  (SPA)
   no BD propia (estado en cliente + osap-api backend)

Social (futuro)
   profiles (heredero de public_profiles), opinions, followers, activity
```

### ¿`membership` y `public_profile` en el mismo servicio?
**Recomendación:** el **estado de membresía** vive en **osap-membership** (íntimamente ligado al pago). El **perfil público/consentimiento** puede vivir en el mismo servicio (tabla `public_profiles`) **o** en un futuro "community/profile". Para no migrar cuando llegue Social:
- Mantener `public_profiles` **desacoplado de osap-app/Chorus** (pertenece al ecosistema, no a una app).
- Al llegar Social, `public_profiles` puede **moverse/evolucionar** hacia Social sin arrastrar datos de pago (nunca se mezclaron).
- Alternativa más limpia aún: definir `public_profiles` como parte del contrato de **osap-membership** ahora, y que Social lo **herede/lea** (o se convierta en su fuente inicial) sin migración estructural.

**Regla:** nunca guardar montos/método/recibos/bancos en `public_profiles` ni en ninguna tabla consumible por la comunidad. Eso solo vive en el proveedor de pagos y (agregado/etiquetado) en `memberships` como nivel.

---

## 8. API propuesta (conceptual, revisable)

| Endpoint | Qué es | Quién lo llama | Quién lo provee | Autenticación | Devuelve | Nunca devuelve |
|---|---|---|---|---|---|---|
| `GET /support` | página pública Apoya OSAP | navegador (osap-app o Chorus) | osap-app o Chorus (frontend) | pública | contenido de la página | --- |
| `POST /auth/oidc/start` | inicia login | SPA | osap-api → osap-auth | pública | authorize_url | --- |
| `GET /auth/me` | perfil del usuario | apps | Auth | user token | name, email, roles, status | contraseñas, PII no necesaria |
| `GET /membership/me` | estado del colaborador (usuario) | apps | **osap-membership** | user token (`sub`) | status, level, fechas, is_founder | montos, método, recibo, email |
| `POST /membership/checkout` | crea sesión de pago | apps | **osap-membership** | user token | url del proveedor (+ return_url) | --- |
| `GET/POST /membership/webhook` | evento del proveedor | proveedor de pagos | **osap-membership** | firma del proveedor | actualiza `memberships` | --- |
| `GET /community/me` | perfil público (consentimiento+datos) | apps | **osap-membership** | user token | visibility, public_name, bio, avatar | datos económicos |
| `PUT /community/me` | actualiza consentimiento/perfil | apps | **osap-membership** | user token | ok | --- |
| `GET /community/members` | lista de colaboradores públicos | apps | **osap-membership** | pública (o service token) | id/nombre público/nivel/avatar | email, id real si privat, datos de pago |

**Notas:** los endpoints de membresía usan el **access token de usuario** (`{Authorization: Bearer <JWT>}`) para derivar `sub`; los de M2M usan service token de `client_credentials`. `GET /community/members` solo devuelve perfil público de quienes consintieron (`visibility != anonymous`) y con pertenencia activa.

---

## 9. Perfil público — dónde vive y cómo se comparte

- **Vive en `osap-membership.public_profiles`** (ecosistema, no en una app).
- **Campos:** `visibility` (anonymous/public_name/custom_name, default anonymous), `public_name` (puede ser "Miguel G.", "M. García", "Amigo de OSAP"), `public_bio`, `avatar_url`.
- **Compartición:** osap-app, Chorus y Social leen el mismo perfil. `GET /community/members` es la lectura pública; `GET /community/me` la del propio usuario.
- **Regla de privacidad:** publicar es **opt-in**. Al cancelar/expirar la membresía, se **oculta automáticamente** de listados públicos. Nunca se publican montos, método, bancos, email, historial.
- **Avatar:** origen de perfil/avatar (puede delegarlo Social en el futuro), no del pago.

---

## 10. Futuro Social — integración sin rehacer

- **Identidad:** reutiliza Auth (`sub`). No crea usuarios.
- **Perfil:** Social **hereda/evoluciona** `public_profiles` (ya desacoplado en membership). No reinventa consentimiento.
- **Membresía:** Social lee `membership` (badge de colaborador) desde osap-membership; **nunca** crea otra membresía.
- **Cómo garantizarlo desde ahora:** (1) `public_profiles` desacoplado de osap-app/Chorus; (2) contrato API de membership estable; (3) ninguna app escribe en tablas de membership/community ajenas; (4) `osap-membership` es la fuente de verdad del apoyo y del consentimiento.
- **Resultado:** al llegar Social solo se añaden capacidades nuevas (seguidores, opiniones, actividad) sobre una base ya compartida.

---

## 11. Portabilidad

Para que osap-app+Chorus (Máquina A) y Membership+Social (Máquina B) puedan separarse:

- **osap-membership como componente independiente**: repo, BD y API propios.
- **Variables de entorno / configuración externa** para URLs de Auth, proveedor de pagos, issuer, etc.
- **Migraciones** propias del servicio de membership.
- **Docker** cuando sea conveniente (no obligatorio en esta fase; el proyecto no lo usa aún de forma vertebrada).
- **Sin dependencia de Vercel** ni infraestructura propietaria.
- **Contrato API estable** → las apps solo cambian de URL de membership, no de lógica.

```
Máquina A:  osap-app + Chorus (y Auth)
Máquina B:  osap-membership (+ Social futuro)
```

---

## 12. Plan por fases

```
Fase 1 — Arquitectura ............ este documento; contrato de identidad y API
Fase 2 — Página de apoyo ......... contenido público "Apoya OSAP" (osap-app y Chorus),
                                    con login vía Auth; sin pagos
Fase 3 — Integración Auth ........ asegurar que ambas apps identifican por sub (ya casi)
Fase 4 — Membership .............. crear osap-membership + integrar proveedor de pagos;
                                    tablas memberships; webhook; checkout; /membership/me
Fase 5 — Comunidad ............... public_profiles (consentimiento) + "Descubrir"/comunidad;
                                    GET /community/me y /community/members
Fase 6 — Social .................. heredar perfil público y membresía; añadir interacción
```

**Detalle de esta fase actual (Fase 1):** documentar arquitectura; **no crear tablas**; no elegir proveedor; no red social; no modificar Auth; no duplicar usuarios/membresías; no eliminar `/discover` (solo documentar su evolución). El trabajo de la Fase 2 (página de apoyo pública con login por Auth) ya está iniciado en osap-api (`/support`).

---

## 13. Niveles de apoyo (propuesta revisada — ecosistema, no Chorus)

No es un ranking económico; reconocemos **formas de compromiso** con el ecosistema. Denominaciones coherentes con "coro":

| Nivel | Nombre | Idea |
|---|---|---|
| ★ histórico | **Miembro fundador de OSAP** | sello temporal (§14) |
| N1 | **Amigo de OSAP** | apoyo puntual / esporádico |
| N2 | **Voz de OSAP** | aportación recurrente (mensual) |
| N3 | **Coro / Colaborador principal** | recurrente mayor / guía del proyecto |

**Recomendación:** niveles **musicales/coro** (no estrellas ascendentes): "Amigo", "Voz", "Coro" + **badge de fundador**. La UI muestra el **nombre del nivel/badge**, nunca montos. Los importes se deciden con el proveedor de pagos (fase 4).

Las estrellas (⭐/⭐⭐/⭐⭐⭐) se descartan porque sugieren jerarquía económica.

---

## 14. Miembro fundador de OSAP

- **Criterio objetivo (temporal):** ser colaborador con pertenencia activa (puntual o recurrente) **dentro de una ventana temporal fija** (p. ej. primeros N meses desde el arranque público del apoyo, o hasta un hito documentado). El criterio se **publica y congela** antes de abrir la ventana.
- **No depende del importe** → no es un ranking económico.
- **Evitar conflictos:** la ventana se fija por adelantado; una vez cerrada, "fundador" no se extiende retroactivamente. Queda como sello histórico (`is_founder=true`), no como nivel ascendente.
- Se guarda con `started_at` para mantener el orden histórico.

---

## 15. Base de datos — ubicación conceptual (sin crear)

| Dato | Vive en | Nota |
|---|---|---|
| `user` (identidad) | osap-auth | fuente de identidad |
| `membership` | osap-membership | fuente del apoyo (cache del pago) |
| `public_profile` | osap-membership (desacoplado) | consentimiento + perfil público, heredable por Social |
| `musical_data` | Chorus / osap-storage | |
| `app_data` (osap-app) | osap-api op_store | votos, estado de la app (solo `user_id` opaco) |

`membership` y `public_profile` se documentan como parte del **servicio de membresía del ecosistema**, para que Social no obligue a migrarlos. No se crean tablas en esta fase.

---

## 16. APIs (ya en §8)

Responsabilidades y endpoints resumidas en §8. Puntos clave: Auth no expone pagos; membership es quien une `sub` con el estado de apoyo; los endpoints públicos nunca devuelven datos económicos.

---

## 17. Proveedor de pagos

**No se selecciona.** La arquitectura aísla el proveedor detrás de `osap-membership` (checkout + webhook). Se decidirá en Fase 4 comparando Stripe / Patreon / Ko-fi / Gumroad / GitHub Sponsors según: periodos, niveles, recibe de miembro fundador, Webhooks, retiros regionales (pensando en región del proyecto) y coste. Abstracción independiente del proveedor ya desde el diseño.

---

## 18. Portabilidad (resumen)
Vista en §11. Componente `osap-membership` → repo/BD/API/despliegue independientes, configurable por entorno, Docker opcional, sin Vercel.

---

## 19. Futuro Social (resumen)
Vista en §10. Reutiliza Auth, `public_profiles` y `membership`; no crea otra membresía ni otra identidad.

---

## 20. Qué NO hacer todavía
- No integrar pagos ni elegir proveedor.
- No crear red social, seguidores, opiniones.
- No crear sistema de usuarios nuevo.
- No modificar Auth sin necesidad.
- No duplicar usuarios ni membresías.
- No modificar agresivamente Chorus.
- No eliminar `/discover` sin estudiar consecuencias (evolución documentada, no implementada).

---

## 21. Conclusiones

1. **Architectura actual:** Auth = identidad; OSAP = plataforma; osap-app y Chorus = apps hermanas del ecosistema; sin usuarios propios.
2. **Propuesta:** servicio independiente **osap-membership** como fuente de verdad del apoyo y del perfil público, compartido por osap-app, Chorus y Social.
3. **Recomendación:** Opción C con matiz de D (independiente desde el diseño, extraíble desde el inicio).
4. **Identidad:** una persona = un `sub`; nunca se duplican identidades/membresías.
5. **Datos:** `membership` + `public_profile` desacoplados de las apps, para que Social los herede sin migrar.
6. **Portabilidad:** membership como componente independiente, configurable por entorno.
7. **Próximo paso real (Fase 2 ya en curso):** página de apoyo pública con login por Auth, que apuntará a membership cuando exista.

---

*Fin del análisis. Sin cambios de código realizados en esta tarea.*
