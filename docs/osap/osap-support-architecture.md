# OSAP Support — Arquitectura del servicio independiente de apoyo

> **Fase Técnica 2 · Diseño técnico. Sin código, sin repo, sin BD, sin pagos, sin emails.**
> Referencias: `docs/osap/support-architecture-separation.md`, `docs/osap/support-frontend-boundary-v1.md`,
> `docs/osap/support-ecosystem-architecture.md`. Stack de referencia: `osap-auth` (servicio independiente pequeño).
> Fecha: 2026-08-29

---

## 1. Objetivo

Definir la arquitectura de **OSAP Support**, el servicio del ecosistema que gestiona la relación de apoyo entre una **identidad OSAP** (Auth) y el **proyecto** (economía no sensible + comunicaciones), independiente de cualquier proveedor de pagos y de los datos sensibles del medio de pago.

Puede desplegarse de forma independiente (otra máquina en el futuro) sin acceder a BBDD ni a código de los demás servicios.

---

## 2. Responsabilidades

| Responsabilidad | Sí / No | Nota |
|---|---|---|
| Relación de apoyo (quién apoya y estado) | ✅ | núcleo del servicio |
| Membresías (recurrentes) | ✅ | estado, nivel, fechas |
| Donaciones puntuales | ✅ | registro de aportaciones puntuales |
| Integración del proveedor de pagos (abstraída) | ✅ | solo vía port `PaymentProvider` |
| Eventos de pago / webhooks | ✅ | idempotentes |
| Emails de la relación económica | ✅ | vía `EmailSender` (port) |
| Comunidad futura (perfil público / Social) | ⚠️ | interfaz preparada, no implementar aún |
| Identidad (login/registro/Google/GitHub) | ❌ | Auth |
| Datos sensibles de pago (tarjeta/CVV) | ❌ | proveedor de pagos |
| Plataforma musical | ❌ | OSAP API / storage |
| Red social | ❌ | Social futuro |

---

## 3. Entidades del dominio

Se proponen **cuatro conceptos**, tras analizar donación puntual vs recurrente:

- **SupportMember** — relación estable entre `Auth.user_id` y OSAP. Existencia ≠ pagar: es el "expediente" del usuario en Support.
- **Membership** — una relación **recurrente** (suscripción). Nace de una suscripción activa.
- **Donation** — una aportación **puntual** (sin periodicidad).
- **PaymentEvent** — evento idempotente que llega del proveedor (origen de cambios).
- **CommunicationEvent** — registro de email enviado/pendiente (para trazabilidad y recordatorios).

> Decisión de diseño: **Membership y Donation son conceptos distintos** (recurrente vs puntual) pero comparten una raíz: la relación `SupportMember` y el origen `PaymentEvent`. Una abstracción común `SupportContribution` **no** se forza en el dominio; se plasma vía la **máquina de estados** y los **eventos**. Si en el futuro se unifica (ej. la donación puntual también crea un status de "colaborador"), se refina sin romper.

Entidades (nominales, véase §4 para campos):

```
SupportMember (1) ──► (0..*) Membership
SupportMember (1) ──► (0..*) Donation
Membership/Donation ──► (1..*) PaymentEvent  (eventos que la originan/afectan)
PaymentEvent ──► (0..*) CommunicationEvent   (emails originados por el evento)
```

---

## 4. Modelo de datos (BBDD propia de osap-support)

> BBDD MySQL propia (`osap_support`). **No** usa BD de Auth/osap-app/Chorus/Social.

### 4.1 `support_members`
| Campo | Tipo | Notas |
|---|---|---|
| `user_id` | CHAR(36) PK | = `auth.user_id` / `JWT.sub` (UUID) |
| `status` | enum(member) | hoy solo existe si hay relación; pensado para evolución |
| `created_at` / `updated_at` | datetime | |
| `data_version` | int | para sincronización optimista |

Propósito: es la entidad estable que identifica "un usuario de OSAP con relación en Support". Clave: `user_id` (PK) → así **`/membership/me`** es la forma canónica y se evita exponer IDs ajenos.

### 4.2 `memberships`
| Campo | Tipo | Notas |
|---|---|---|
| `id` | bigint PK auto | id interno |
| `user_id` | CHAR(36) FK→support_members | |
| `status` | enum(pending, active, past_due, cancelled, expired) | máquina de estados §5 |
| `level` | enum(supporter, contributor, voice, founder) | niveles de apoyo (no económico) |
| `periodicity` | enum(monthly, yearly) | |
| `amount_minor` | int | importe en **mínimas unidades** (céntimos) |
| `currency` | char(3) | ISO 4217 |
| `provider` | str | etiqueta del proveedor (no lógica) |
| `customer_id` | str | id del cliente en el proveedor |
| `subscription_id` | str | id de suscripción en el proveedor |
| `started_at` / `renewed_at` / `next_renewal_at` / `cancelled_at` / `expires_at` | datetime nulo | |
| `email_contact` | str | email de contacto (ver §12) |
| `is_founder` | bool | conforme a criterio temporal (fase comunidad) |
| `created_at` / `updated_at` | datetime | |

Índices: `UNIQUE(subscription_id)` (idempotencia de proveedor), `INDEX(user_id)`, `INDEX(status)`, `INDEX(next_renewal_at)` (scheduler). Sensible: no — solo economía no sensible (importe/etiqueta). Nunca tarjeta/CVV.

### 4.3 `donations`
| Campo | Tipo | Notas |
|---|---|---|
| `id` | bigint PK auto | |
| `user_id` | CHAR(36) FK | |
| `amount_minor` | int | mínimas unidades |
| `currency` | char(3) | |
| `donated_at` | datetime | |
| `provider` / `charge_id` / `receipt_id` | str | referencia (no datos sensibles) |
| `email_receipt` | str | para el acuse |
| `created_at` | datetime | |

### 4.4 `payment_events`
| Campo | Tipo | Notas |
|---|---|---|
| `id` | bigint PK auto | |
| `provider` | str | |
| `provider_event_id` | str | **clave de idempotencia** ⇒ `UNIQUE(provider, provider_event_id)` |
| `event_type` | str | subscription.created, payment.succeeded, payment.failed, subscription.renewed, subscription.cancelled, subscription.expired, donation.succeeded ... |
| `user_id` | CHAR(36) | resuelto de customer_id→user_id |
| `payload_hash` | char(64) | hash del payload (auditoría) |
| `status` | enum(processed, ignored_duplicate, error) | resultado del procesamiento |
| `received_at` / `processed_at` | datetime | |
| `raw` | json | **retención corta** (ver §17/18) |

### 4.5 `communication_events`
| Campo | Tipo | Notas |
|---|---|---|
| `id` | bigint PK auto | |
| `user_id` | CHAR(36) | |
| `template` | str | clave de plantilla (welcome, thanks, renewal, payment_failed, cancel...) |
| `recipient_email` | str | el email de contacto |
| `status` | enum(pending, sent, failed) | |
| `attempts` | int | nº de intentos |
| `next_attempt_at` | datetime nulo | backoff |
| `origin_event_id` | FK→payment_events nulo | qué lo originó |
| `created_at` / `sent_at` / `last_error` | datetime / str | |

---

## 5. Máquina de estados de Membership

Diseñada a partir de los eventos reales (no asumida):

```
                [creación] subscription.created
                     │
                     ▼
                 pending ───────────────► payment.failed ──► (intentos) ──► (se queda o cancela vía proveedor)
                     │
        payment.succeeded
                     ▼
                 active ◄───────────────► past_due ◄── payment.failed (recurrente)
                     │                        │
        subscription.cancelled                │ (recupera si payment.succeeded)
                     │                        │
                     ▼                        ▼
                cancelled                  expired (no se recupera a tiempo)
```

| Transición | Impulso (quién) | Evento | Dos veces | Fuera de orden |
|---|---|---|---|---|
| pending → active | webhook | payment.succeeded | idempotente (no-op si ya active) | se acepta (webhook tarde) |
| active → past_due | webhook | payment.failed (recurrente) | idempotente | se acepta |
| past_due → active | webhook | payment.succeeded | idempotente | se acepta |
| active/past_due → cancelled | webhook + scheduler | subscription.cancelled | idempotente (solo primera genera email) | se acepta; el scheduler confirma |
| active/past_due → expired | scheduler | vence `next_renewal_at` sin pago | idempotente | scheduler guarda `expired_at` |
| — → refund/etc. | webhook | otros payment_* | se registra, puede no cambiar estado | seguro |

**Principios:** cada transición es **idempotente** (key: `provider_event_id`); si un evento llega fuera de orden, se **registra siempre** y se aplica la transición **válida desde el estado actual** (si no aplica, queda como evento `processed` sin cambio de estado o `error` para inspección).

---

## 6. Eventos (y quién los provoca)

| Evento de dominio | Origen | Efecto |
|---|---|---|
| `membership.created` | proofechar `subscription.created` | crea `pending` |
| `membership.activated` | `payment.succeeded` | pending→active, set `started_at`/`next_renewal_at` |
| `membership.renewed` | `payment.succeeded` recurrente | active→active, actualiza `renewed_at`/`next_renewal_at` |
| `membership.past_due` | `payment.failed` | active→past_due |
| `membership.recovered` | `payment.succeeded` tras past_due | past_due→active |
| `membership.cancelled` | `subscription.cancelled` + scheduler | act→cancelled |
| `membership.expired` | scheduler (venció renovación) | act/past_due→expired |
| `donation.received` | `donation.succeeded` | registra donation + (opcional) recompensa/miembro |

Todos los cambios se **derivan de `payment_events`** (la auditoría se reconstruye desde ahí, §17). El scheduler solo dispara comprobaciones; **nunca** inventa estados.

---

## 7. Webhooks y flujo

```
Payment Provider
      │  POST /webhooks/payment  (con firma)
      ▼
Support
  1. validar firma/secreto        (rechazar si no firma)
  2. resolver provider_event_id    → ¿ya existe? → ignore_duplicate (200, no reprocesar)
  3. identificar event_type
  4. enriquecer con user_id        (customer_id → user_id)
  5. aplicar máquina de estados    (idempotente, transición desde estado actual)
  6. generar acciones               (crear CommunicationEvent / en cola)
  7. responder 2xx siempre          (el proveedor reintenta ante no-2xx; nosotros ya no reprocesamos)
```

**Idempotencia:** `UNIQUE(provider, provider_event_id)` en `payment_events`. Si el proveedor reenvía el mismo evento, se devuelve 200 y no se vuelve a aplicar la transición ni a reenviar el email.

---

## 8. Idempotencia (detalle)

- Clave primaria de idempotencia: `(provider, provider_event_id)`.
- El webhook se **registra primero** (`INSERT ... ON DUPLICATE KEY` → si duplicado, marcar `ignored_duplicate` y responder 200).
- Los emails y las mutaciones de estado se generan **una sola vez por `payment_event_id`** (FK `origin_event_id`).
- Para peticiones de la API (checkout) se usará `Idempotency-Key` por cliente cuando aplique.

---

## 9. Emails

> Support es responsable de las comunicaciones de la **relación económica**. Auth no emite estos emails.

Clasificación por fases (no todos desde el día 1):

**MVP (mínimo recomendado):**
- `welcome_supporter` (alta de relación/activación)
- `donation_confirmation` (acuse de donación puntual)

**Segunda fase:**
- `membership_confirmation` (suscripción activada)
- `renewal_notice` (próxima renovación)
- `payment_failed` (pago fallido / past_due)
- `membership_cancelled`

**Futuro / opcional:**
- `membership_expired`
- recordatorios de recuperación, encuestas, newsletter (fuera de Support)

Se diseñan como **plantillas independientes** de la lógica; nunca se incluyen textos económicos sensibles.

---

## 10. Sistema de emails

Flujo controlado (no `webhook → email` directo):

```
payment_event
      ↓
Support (reglas) → crea CommunicationEvent{status=pending, origin_event_id}
      ↓
EmailSender worker / scheduler
      ↓  cada communication_events.status=pending → enviar
      ↓
proveedor de email (port EmailSender)
```

`CommunicationEvent` ofrece: `status(pending/sent/failed)`, `attempts`, `next_attempt_at` (backoff), `template`, `recipient_email`, `origin_event_id`. **No se implementa el proveedor**; se define el port `EmailSender` (`send(to, template, data, event_ref) -> bool`) con implementación in-memory/test.

**Idempotencia de email:** un email solo se encola una vez por `(origin_event_id, template)` → `UNIQUE(user_id, template, origin_event_id)` en `communication_events`.

---

## 11. Recordatorios (scheduler) — diseño

Necesita un **proceso programado** (job/worker), separado del servicio web.

```
CRON / scheduler (p. ej. diario, UTC)
      ↓
Support job: "revisar renovaciones"
      ↓
SELECT memberships WHERE next_renewal_at <= now + Xd AND status IN (active,past_due)
      ↓
por cada una: ¿communication_events con template=renewal_notice para esta membresía/ventana?
      ≤ 1 → encolar email
      ya enviado → no repetir
      ↓
UPDATE next_renewal_at / expired_at según corresponda
```

- **Periodicidad:** diaria (o cada N horas); exactitud al día/mes es suficiente.
- **No duplicados:** se consulta `communication_events` (UNIQUE por template+ventana) y `payment_events` (estado); si se ejecuta dos veces, el segundo intento no encuentra novedad.
- **Si se ejecuta dos veces:** idempotente por las claves UNIQUE y por "estado transitorio" (solo transita si aplica).

Recordatorio de pago fallido: se generará un `payment_failed` email (segunda fase) y, opcionalmente, reintentos escalonados.

---

## 12. Datos personales — email de contacto

**Opción recomendada: B-hibrida con minimización.**
- Support **no** mantiene una copia completa del perfil Auth. Guarda **solo** el campo `email_contact`, obtenido de Auth **en el momento de activar la relación** (o vía webhook/evento de identidad al crear la membresía).
- Si Auth informa **cambio de email** (`user.updated` / al renovar), Support actualiza `email_contact`; si el usuario **elimina la cuenta** (evento `user.deleted` que ya existe en Auth), Support **anonimiza/elimina** (§18).
- Google/GitHub: Auth es la fuente del email; Support solo ve el email de contacto (puede ser el de la cuenta vinculada). **La relación queda ligada a `user_id`, nunca al proveedor social.**
- **Por qué:** disponible aun si Auth está caído para el envío; no duplica el perfil completo; se mantiene sincronizado vía eventos de identidad.

---

## 13. Auth (integración de identidad)

- Support **solo** acepta `JWT` → `sub` = `Auth.user_id`. **Nunca crea usuarios** ni identidad propia.
- Para obtener `email_contact`/`name` al activar la relación: llamada **service-to-service** a Auth (`GET /me`-equivalente con **service token** de Support, scope de lectura), no reutilizando credenciales de usuario.
- Autenticación de API de usuario: `Bearer <user access token>` → Support valida `sub` (vía JWKS de Auth) y usa `sub` como `user_id` en sus tablas.
- Cancelación/eliminación: se suscribe a `user.deleted` de Auth (§18).

---

## 14. API pública de Support (inicial, mínima)

Endpoints **suficientes** (no de más):

| Endpoint | Uso | Auth | Notas |
|---|---|---|---|
| `GET /api/v1/support/status` | qué ofrece OSAP / cómo apoyar (página `/support`) | pública | contenido de la página |
| `GET /api/v1/membership/me` | estado del usuario (`status, level, fechas, is_founder`) | Bearer `sub` | **canónico**; evitar `GET /membership/{id}` |
| `POST /api/v1/membership/checkout` | iniciar suscripción | Bearer `sub` | devuelve url del proveedor + return_url (futuro) |
| `POST /api/v1/donations/checkout` | donación puntual | Bearer `sub` | devuelve url + return_url (futuro) |
| `POST /api/v1/webhooks/payment` | proveedor de pagos | firma/secreto | idempotente (§7) |
| `GET /api/v1/admin/memberships` (futuro) | panel admin | rol `admin` | estado/historial |
| `GET/PUT /api/v1/community/me`, `GET /community/members` (futuro) | perfil público/consentimiento | Bearer / pública | §comunidad |

**Regla de seguridad:** en apps normales **solo** `.../me` (nunca por ID modificable en la URL). Endpoints admin llevan autorización de rol.

---

## 15. Seguridad

- **Públicos:** `support/status`, `community/members` (solo lo consentido). Sin datos privados.
- **Autenticados:** `*/me`, `checkout` → `Bearer user token` (solo tu `sub`). **Nunca** los datos de otro usuario.
- **Admin:** rol `admin` (decisiones de autorización en Support; no en Auth).
- **Webhook:** autenticación por **firma/secreto** del proveedor; verificación de esquema y de `provider_event_id`.
- **Idempotencia / replay:** `UNIQUE(provider, provider_event_id)` en BD + verificación de timestamps firmados; respuesta 2xx sin reproceso.
- **Rate limiting:** en endpoints autenticados y en webhooks (p. ej. límite por IP/clave).
- **Anti-ID-oracle:** solo `.../me` para el usuario; admin con scope/rol.
- **No logs sensibles:** no loguear tarjetas/cvv/emails salvo necesidad; el email de contacto se loguea a nivel de comunicación (necesario).

---

## 16. BBDD propia (resumen) y retención

| Tabla | Propósito | Sensible | Retención |
|---|---|---|---|
| `support_members` | expediente por usuario | no | mientras exista relación |
| `memberships` | suscripciones | no (economía no sensible) | +N años tras fin (obligación fiscal) |
| `donations` | aportaciones puntuales | no | igual |
| `payment_events` | audit/estado | `raw` es fugaz | `raw` __borra__ tras proceso; metadata se conserva anonimizada |
| `communication_events` | emails | email de contacto | conservar para trazabilidad; anonimizar al eliminar usuario |

No se usa BD de Auth/osap-app/Chorus/Social. Retención: mínima necesaria (datos de pago no sensibles + trazabilidad; raw de webhook de vida corta).

---

## 17. Auditoría

`payment_events` es el **libro mayor** de Support: reconstruye la evolución de cualquier `membership`/`donation` desde sus eventos (creación, pagos, fallos, renovaciones, cancelaciones). `communication_events` responde "por qué se envió este email" (origin_event_id + template). Regla: **todo cambio de estado y todo email se deriva de un evento registrado**, de modo que:
- "¿Por qué aparece activo?" → último `payment.succeeded` procesado.
- "¿Qué pasó con su pago?" → secuencia de `payment_events`.
- "¿Por qué se envió este email?" → `communication_events.origin_event_id`.

---

## 18. Privacidad y eliminación

Ante `user.deleted` de Auth:
- **Eliminar:** raw de `payment_events` (ya retenido corto), emails de comunicación personales (asunto/cuerpo), `email_contact`.
- **Anonimizar:** `memberships`/`donations` → quitar `user_id`/`email`, conservar agregados y referencias ciegas de proveedor (para reconciliación y cumplimiento) marcadas como "agregado".
- **Conservar (legal):** cifras agregadas y metadatos de impuestos, sin vínculo reidentificable.
- Diseño de **minimización**: Support solo guarda lo necesario (email_contact, economía no sensible); nunca tarjeta/CVV/credenciales.

---

## 19. Panel administrativo (futuro)

Necesidades de un admin de OSAP (respuestas):
- "¿Esta persona es colaboradora?" → `support_members` + `memberships.status`.
- "¿Qué pasó con su membresía?" → historial `payment_events` + `memberships`.
- "¿Falló su último pago?" → último `payment.failed`.
- "¿Se envió el email?" → `communication_events`.
- "¿Cuándo terminó?" → `cancelled_at`/`expires_at`.

Panel separado de la UI pública, protegido por rol `admin`, con endpoints `GET /admin/...`. No se implementa ahora.

---

## 20. Independencia física y despliegue

```
Servidor A:  Auth, OSAP API, osap-app
Servidor B:  osap-support            (futuro)
Servidor C/D: Chorus, Social         (futuro)
```
- **No** accede a BBDD ajenas; **no** importa Python de osap-api; **no** rutas internas; comunicación por **API**; configuración por **variables de entorno**.

Sin Docker en el ecosistema hoy → **portabilidad = venv + entorno + MySQL + migraciones** (consistente con osap-auth). Se puede añadir Docker a `osap-support` **si** decide moverse a deployment aislado sin tocar el resto, pero no es requisito.

---

## 21. Tecnología (recomendación)

**Recomendación: mismo stack que `osap-auth`** (el modelo ideal de "servicio pequeño e independiente"):
- FastAPI + uvicorn + pydantic v2 + pydantic-settings + PyMySQL/aiomysql + alembic.
- Estructura hexagonal `domain/application/infrastructure/api` (como osap-auth).
- Python ≥3.12 (consistente con osap-api) o ≥3.11 (como osap-auth). Recomiendo ≥3.12 para no fragmentar.
- Testing: pytest + pytest-asyncio; ruff (E,F,I,UP,B,ANN); mypy.
- Config: `pydantic-settings` + env + `osap-support.toml` (opcional).

**Por qué no stack independiente nuevo:** el equipo ya conoce este stack; los ports (PaymentProvider, EmailSender) hacen agnóstica la integración; portabilidad y mantenimiento son máximos sin innovar en infraestructura. No hay razón para introducir otro runtime ahora.

---

## 22. Estructura del repositorio (propuesta)

```
osap-support/
├── pyproject.toml            # hatchling, deps (fastapi, uvicorn, pydantic-settings, pymysql/aiomysql, alembic, PyJWT, httpx)
├── config.example.toml
├── domain/
│   ├── entities.py           # SupportMember, Membership, Donation, PaymentEvent, CommunicationEvent
│   ├── events.py             # tipos de evento de dominio
│   ├── state_machine.py      # máquina de estados de Membership
│   └── exceptions.py
├── application/
│   ├── use_cases/
│   │   ├── get_my_membership.py
│   │   ├── checkout_membership.py
│   │   ├── checkout_donation.py
│   │   ├── process_webhook.py        # idempotente
│   │   └── reminders.py               # scheduler
│   └── ports/
│       ├── membership_repository.py
│       ├── payment_provider.py       # PaymentProvider port
│       ├── email_sender.py            # EmailSender port
│       └── identity_resolver.py       # Auth interacción (email/sub, user.deleted)
├── infrastructure/
│   ├── db/
│   │   ├── mysql.py                   # repos MySQL (misma interfaz que ports)
│   │   ├── migrations/                # alembic
│   │   └── seed.py
│   ├── auth/identity_client.py        # wrapper Auth (service token, /me, user.deleted)
│   └── email/in_memory.py             # EmailSender in-memory (tests/dev)
├── api/
│   ├── main.py                        # FastAPI app
│   ├── routes/
│   │   ├── public.py                  # /support/status
│   │   ├── member.py                  # /membership/me, /donations/checkout
│   │   └── webhooks.py                # /webhooks/payment
│   └── security.py                    # JWT (JWKS Auth), firma webhook, rate limit
├── bootstrap/
│   ├── container.py
│   └── configuration.py               # pydantic-settings + env
├── jobs/
│   ├── run_reminders.py               # entrypoint del scheduler (cron)
│   └── run_dispatch_emails.py         # worker de CommunicationEvent
├── tests/
│   ├── domain/ application/ api/ infrastructure/
├── docs/
│   └── osap-support.md                # this doc / plan
```

Separación clara `domain / application / ports / infrastructure / api / bootstrap` como en osap-auth, manteniendo los **ports** (PaymentProvider, EmailSender, repos) para que el proveedor sea intercambiable.

---

## 23. Integración con SupportGateway (contrato frontend)

La sustitución `LocalSupportGateway → SupportApiClient` **no modifica páginas** si el contrato es el mismo:

```ts
// web/src/support/supportGateway.ts  (ya definido)
export interface SupportSummary {
  status: "anonymous" | "preparing";
  authenticated: boolean;
  subscriberId?: string;
}
export interface SupportGateway { getSummary(): Promise<SupportSummary>; }
```

Para el futuro, el contrato mínimo que `osap-support` debe cumplir (el `status` pasará de `preparing` a un estado real):
```
GET /api/v1/support/status        → contenido pág. (público)
GET /api/v1/membership/me         → { status, level, started_at, next_renewal_at, is_founder } (Bearer sub)
POST /api/v1/membership/checkout  → { url, return_url }            (futuro)
POST /api/v1/donations/checkout   → { url, return_url }            (futuro)
```
`SupportApiClient` implementa `SupportGateway` llamando a estos endpoints (o a un `status` resumido) y mapea a `SupportSummary`. Las páginas (`/support`) no cambian.

---

## 24/25. Chorus y osap-app

- No se modifican.
- Cuando exista Chorus/osap-app separados, ambos consumirán `SupportGateway → SupportApiClient → osap-support`. **Sin duplicar** lógica de Support: la comparten vía la misma frontera `support/*` (extraíble a librería compartida).

---

## 26. Entregables — cubiertos en este documento
1 Objetivo §1 · 2 Responsabilidades §2 · 3 Entidades §3 · 4 Modelo de datos §4 · 5 Máquina de estados §5 · 6 Eventos §6 · 7 Webhooks §7 · 8 Idempotencia §8 · 9 Emails §9 · 10 Sistema de emails §10 · 11 Scheduler §11 · 12 Email de contacto §12 · 13 Auth §13 · 14 API §14 · 15 Seguridad §15 · 16 BD §16 · 17 Auditoría §17 · 18 Privacidad §18 · 19 Admin §19 · 20 Dependencias/Despliegue §20 · 21 Tecnología §21 (en §21 del doc) · 22 Estructura repo §22 · 23 Integración SupportGateway §23 · 24/25 apps §24/25 · 26 plan §27 abajo.

---

## 27. Plan de implementación (futuro, tras aprobación)
```
Fase 1 — esqueleto del servicio (pyproject, bootstrap, config, estructura hexagonal)   [fase siguiente]
Fase 2 — dominio + máquina de estados + tests unitarios
Fase 3 — repos MySQL + migraciones alembic
Fase 4 — ports PaymentProvider (no impl) + EmailSender (in-memory) + identity_client (Auth)
Fase 5 — API pública mínima (/status, /me, checkout marcados como no activos)
Fase 6 — webhooks idempotentes (proof-of-concept con proveedor ficticio)
Fase 7 — sistema de emails + scheduler de recordatorios
Fase 8 — admón + comunidad (perfil público) + integración final con SupportApiClient
```

---

## DECISIÓN CLAVE — Definición de OSAP Support

> **OSAP Support es el propietario de la relación de apoyo entre una identidad OSAP y el proyecto, pero no es propietario de la identidad ni de los datos sensibles del medio de pago.**

Esta definición **es correcta** tras el análisis y se adopta. Matices a documentar:
- **No es propietario de la identidad** → Auth; Support solo referencia `user_id` (sub).
- **No es propietario de los datos sensibles del medio de pago** → el proveedor los custodia; Support opera con referencias (customer_id/subscription_id) y economía **no sensible** (importe en mínimas unidades, etiquetas).
- **Sí es propietario** de: la relación de apoyo (estado/nivel/fechas), el historial de eventos (auditoría), las comunicaciones de la relación económica y (futuro) el consentimiento de perfil público.

Alternativas descartadas: considerar Support "solo pagos" (demasiado estrecho: ignora emails y comunidad) o "extensiones de Auth" (rompería la separación identidad/economía). La definición aprobada se mantiene.

---

*Fin del documento de arquitectura de OSAP Support. Sin código, sin repo, sin BD.*
