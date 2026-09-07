# OSAP Support — Diseño de implementación: reconocimientos y contribuciones (ADR-015–017)

> **Fase de diseño de implementación.** Sin cambios de código ni BD todavía.
> Fecha: 2026-09-06
> Referencias: `docs/osap/support-decisions.md` (registro ADR; ADR-013…017 **FIJADAS** 2026-09-06),
> `docs/osap/osap-support-architecture.md` (arquitectura implementada del servicio),
> `osap-support/` (repo del servicio: estructura hexagonal `domain/application/infrastructure/api`).
> Alcance: diseño de `projects`, `recognitions` (+historial), `contributions`, reglas de
> derivación, endpoints (usuario / público consentido / admin / M2M) y contrato M2M con OMR.

---

## 1. Objetivo y restricciones

Implementar ADR-015 (modelo de reconocimientos), ADR-016 (vigencia de Supporter) y
ADR-017 (contribuciones y contrato OMR → Support) **sin tocar** el núcleo económico
existente:

- No se modifican `support_members`, `memberships`, `donations`, `payment_events`,
  `communication_events`, PayPal, webhooks, scheduler ni la máquina de estados (ADR-004,
  ADR-007).
- No se crea la abstracción unificada `support` / `SupportContribution` (ADR-004).
- Los productos económicos actuales (`supporter/contributor/voice/founder × monthly/yearly`)
  quedan **congelados**; este diseño no decide su revisión comercial (ADR-013).
- `user_id` sigue siendo `JWT.sub` (ADR-002); no hay identidad local. Los reconocimientos y
  contribuciones referencian `support_members.user_id`.
- La relación de apoyo es global al ecosistema; el ámbito `project` existe **solo** en
  reconocimientos y contribuciones (ADR-014).

---

## 2. Decisiones de diseño adoptadas (resumen)

| # | Decisión |
|---|---|
| D1 | Registro de proyectos `projects` con **proyecto canónico `ecosystem`**; `project_id` siempre poblado (sin NULL semántico, ADR-015). Se siembran `ecosystem` y `omr`. |
| D2 | Persistencia de reconocimientos con **dos tablas**: `recognitions` = estado vigente actual (proyección), `recognition_events` = historial inmutable (libro mayor). Espeja el patrón existente `payment_events` (libro) + `memberships`/`donations` (estado) y resuelve la estrategia de filas que ADR-016 deja abierta. |
| D3 | Supporter: reconocimiento **derivado** (nunca manual); regla C de ADR-016; ventana por defecto **365 días** como parámetro del servicio (ecosistema), configurable en `[recognitions]`. |
| D4 | CONTRIBUTOR: derivado por evidencia (criterio de umbral) **o** otorgado por administración sobre la misma evidencia. VOICE: otorgado por administración. FOUNDER: histórico por criterio congelado (migra desde `memberships.is_founder`). |
| D5 | Una contribución registrada **no genera reconocimiento por sí sola** (ADR-017): solo nace cuando la regla correspondiente se cumple. |
| D6 | El consentimiento público es **opt-in y revocable** y vive en el reconocimiento (`public`/`public_since`/`public_revoked_at`); solo el usuario lo cambia. |
| D7 | M2M con **service token** (`token_use=service`, audience `osap-support`, scope `support:ingest`), idempotente por `UNIQUE(source, source_reference)`. Los service tokens nunca se confunden con tokens de usuario (los JwksIdentityResolver actuales los rechazan). |

---

## 3. Entidades del dominio (nuevas)

Estilo del dominio existente (`domain/entities.py`): `@dataclass` + `Enum` de Python,
persistencia separada en `infrastructure/db/models.py`.

### 3.1 Project

```
Project
  id          int | None
  slug        str      # 'ecosystem' | 'omr' | ... (identificador canónico, whitelisted)
  name        str
  created_at  datetime
```

### 3.2 Recognition

```
RecognitionType     Enum  SUPPORTER | CONTRIBUTOR | VOICE | FOUNDER
RecognitionKind     Enum  HISTORICAL | DERIVED | GRANTED
RecognitionStatus   Enum  ACTIVE | INACTIVE        # vigente vs histórico (ADR-016)

Recognition
  id               int | None
  user_id          str                    # == JWT.sub (ADR-002)
  project_id       int                    # FK → projects; siempre poblado (canónico 'ecosystem')
  type             RecognitionType
  kind             RecognitionKind
  status           RecognitionStatus      # ACTIVE = vigente; INACTIVE = histórico (no se muestra)
  granted_at       datetime               # momento en que fue efectivo
  granted_by       str | None             # SOLO kind=GRANTED: admin {user_id} | system
  origin           str | None             # mecanismo si NO es concesión manual:
                                          #   rule:supporter.active_or_donated_12m
                                          #   rule:contributor.omr_evidence
                                          #   criterion:founder.window_<id>
  reason           str | None             # auditable
  active_until     datetime | None        # NULL = no caduca
  public           bool = False           # consentimiento expreso opt-in
  public_since     datetime | None
  public_revoked_at datetime | None
  updated_at       datetime
```

### 3.3 RecognitionEvent (historial inmutable)

```
RecognitionEventType Enum
  ACTIVATED | DEACTIVATED | GRANTED | REVOKED |
  CONSENT_GRANTED | CONSENT_REVOKED | UPDATED

RecognitionEvent
  id               int | None
  user_id          str
  project_id       int
  type             RecognitionType
  event_type       RecognitionEventType
  status_after     RecognitionStatus       # snapshot del estado resultante
  reason           str | None
  origin           str | None              # origen del evento (rule/criterion/contribution/admin)
  origin_ref       str | None              # referencia idempotente (id del payment_event,
                                           #   contribution source_reference, etc.)
  granted_by       str | None
  occurred_at      datetime
```

### 3.4 Contribution (referencias agregadas; ADR-017)

```
ContributionType  Enum  CONTENT | REVIEW | TRANSLATION | DEVELOPMENT |
                        DOCUMENTATION | COMMUNITY | PROMOTION | OTHER

Contribution
  id               int | None
  user_id          str
  project_id       int                 # proyecto en el que se contribuye (p. ej. 'omr')
  type             ContributionType
  summary          str                 # agregado human-readable ("revisión de 150 obras")
  amount           int | None          # delta aditivo de unidades homogéneas del bucket
                                       # (la semántica de la unidad la decide OMR; Support no la interpreta).
                                       # El detalle vive en OMR; aquí solo el agregado.
  source           str                 # sistema emisor (p. ej. "omr")
  source_reference str                 # id idempotente del origen ("omr/review-summary/…")
  created_at       datetime
  UNIQUE(source, source_reference)
```

---

## 4. Esquema BD y migración Alembic `0002`

Nueva migración en `osap-support/infrastructure/db/alembic/versions/0002_*.py`.
Convenciones existentes: `BIG_PK` (`BigInteger` con variante `Integer` en SQLite),
`DateTime` naive UTC, importes como enteros (V-021 no aplica aquí: no hay dinero),
`String` con `.value` de los enums.

```
projects
  id            BIG_PK PK auto
  slug          VARCHAR(32)  UNIQUE NOT NULL      # 'ecosystem', 'omr', ...
  name          VARCHAR(120) NOT NULL
  created_at    DATETIME NOT NULL

recognitions
  id            BIG_PK PK auto
  user_id       VARCHAR(36) NOT NULL  FK → support_members.user_id
  project_id    BIGINT NOT NULL       FK → projects.id
  type          VARCHAR(16) NOT NULL  # RecognitionType.value
  kind          VARCHAR(16) NOT NULL  # RecognitionKind.value
  status        VARCHAR(16) NOT NULL  # RecognitionStatus.value
  granted_at    DATETIME NOT NULL
  granted_by    VARCHAR(64) NULL
  origin        VARCHAR(120) NULL
  reason        VARCHAR(255) NULL
  active_until  DATETIME NULL
  public        BOOLEAN NOT NULL DEFAULT 0
  public_since  DATETIME NULL
  public_revoked_at DATETIME NULL
  created_at    DATETIME NOT NULL
  updated_at    DATETIME NOT NULL
  UNIQUE uq_recognition_current (user_id, project_id, type)
  INDEX ix_recognitions_project_status_public (project_id, status, public)
  INDEX ix_recognitions_user (user_id)

recognition_events
  id            BIG_PK PK auto
  user_id       VARCHAR(36) NOT NULL
  project_id    BIGINT NOT NULL       FK → projects.id
  type          VARCHAR(16) NOT NULL
  event_type    VARCHAR(32) NOT NULL
  status_after  VARCHAR(16) NOT NULL
  reason        VARCHAR(255) NULL
  origin        VARCHAR(120) NULL
  origin_ref    VARCHAR(255) NULL
  granted_by    VARCHAR(64) NULL
  occurred_at   DATETIME NOT NULL
  INDEX ix_recognition_events_user (user_id)
  INDEX ix_recognition_events_user_project (user_id, project_id)

contributions
  id            BIG_PK PK auto
  user_id       VARCHAR(36) NOT NULL  FK → support_members.user_id
  project_id    BIGINT NOT NULL       FK → projects.id
  type          VARCHAR(24) NOT NULL  # ContributionType.value
  summary       VARCHAR(255) NOT NULL
  amount        BIGINT NULL
  source        VARCHAR(64) NOT NULL
  source_reference VARCHAR(255) NOT NULL
  created_at    DATETIME NOT NULL
  UNIQUE uq_contribution_source (source, source_reference)
  INDEX ix_contributions_user_project (user_id, project_id)
```

**Seed en la migración (idempotente):**
- `projects`: `('ecosystem', 'OSAP Ecosystem')`, `('omr', 'Open Music Repository')`.
  Otros proyectos (p. ej. `chorus`) se añaden por migración/operación admin; nunca por el
  cliente (whitelisted).

**Backfill opcional (no en la propia migración, sí en el mismo release como job):**
- FOUNDER histórico para usuarios con `memberships.is_founder = true` vigente o pasada:
  `type=FOUNDER`, `kind=HISTORICAL`, `origin=criterion:founder.<ventana congelada>`,
  `status=ACTIVE`, `active_until=NULL`, `public=false`. Idempotente (upsert por
  `(user_id, project_id='ecosystem', type)`).

**Justificación de dos tablas (D2):** `recognition_events` permite responder "¿por qué y
cuándo se activó/desactivó/concedió/revocó este reconocimiento?" y conserva el **histórico**
de ADR-016 sin contaminar el estado vigente; `recognitions` es la proyección que leen las
APIs. Una única tabla mutable perdería la auditoría de las sucesivas activaciones/
desactivaciones de Supporter.

---

## 5. Reglas de derivación (motor de dominio)

Módulo nuevo `domain/recognitions_rules.py` (sin infraestructura; puerto del estilo
existente). Parámetros del servicio en la sección `[recognitions]` de la configuración
(`infrastructure/config.py`), **no** por proyecto (ADR-016):

| Parámetro | Default | Significado |
|---|---|---|
| `supporter_window_days` | `365` | ventana de donación para Supporter (ecosistema) |
| `contributor_threshold` | `150` | umbral de CONTRIBUTOR (suma del acumulado del bucket) |
| `contributor_types` | `[REVIEW, CONTENT, TRANSLATION, DEVELOPMENT, DOCUMENTATION]` | tipos del bucket que suman al acumulado |
| `founder_criterion_id` | `founder-2026` | identificador del criterio histórico de Founder (congelado) |

### 5.1 SUPPORTER (derivado — regla C, ADR-016)

> Vigente mientras exista **membresía activa** (`status = active`) **o** **donación
> completada** con `donated_at >= now - supporter_window_days`.

- **Gatillos:** (a) webhook de pago tras `donation.succeeded`, activación/renovación/
  cancelación/expiración de membresía → recomputar tras el efecto existente; (b) job diario
  (extensión del worker) que detecta vencimiento de ventana/cancelaciones y desactiva.
- **Transición:** recomputar → si condición verdadera y `recognitions` no está `ACTIVE`,
  activar (evento `ACTIVATED`, `origin=rule:supporter.active_or_donated_12m`); si condición
  falsa y estaba `ACTIVE`, desactivar (`DEACTIVATED`) y **ocultar de lo público**
  automáticamente (`public=false` no se toca como consentimiento: el badge deja de listarse
  porque `status=INACTIVE`; el consentimiento previo permanece registrado).
- `status=INACTIVE` = "histórico": permanece en `recognition_events`/tabla, no se muestra
  como badge vigente ni en lecturas públicas.
- **Nunca** se concede manualmente; los endpoints admin no aceptan SUPPORTER.

### 5.2 CONTRIBUTOR (derivado de evidencia u otorgado — ADR-017)

Dos vías, siempre sobre evidencia registrada en `contributions`:

- **Derivado (regla fijada en Fase 1):** la regla **agrega bajo demanda** (sobre la tabla
  `contributions`, sin contador físico) la suma de `amount` por `(user_id, project_id)` de
  los tipos del bucket `contributor_types` (configuración: `REVIEW`, `CONTENT`,
  `TRANSLATION`, `DEVELOPMENT`, `DOCUMENTATION`). Cada contribución aporta `amount` como
  **delta aditivo** (OMR nunca envía totales acumulados). Cuando la suma **alcanza el umbral
  `contributor_threshold`** (configuración, valor por defecto `150`), Support activa/otorga
  un único CONTRIBUTOR (sin niveles): `kind=DERIVED`,
  `origin=rule:contributor.omr_evidence`, `reason` = resumen de la contribución que
  completa el umbral.
  - COMMUNITY / PROMOTION / OTHER **no derivan** reconocimiento automáticamente (solo vía
    administración).
  - **No se persiste ningún acumulado**: `contributions` conserva el detalle de cada delta
    (fuente de evidencia auditable) y la regla re-agrega los tipos configurados. Support
    **nunca confía en un contador acumulado** que OMR pudiera enviar ya sumado; toda suma es
    computable desde los deltas idempotentes (`UNIQUE(source, source_reference)`).
  - Una contribución registrada **no implica** reconocimiento: solo deriva al cumplirse la
    regla (ADR-017, D5).
  - **Homogeneidad del `amount`:** `amount` representa unidades homogéneas dentro del
    bucket (no necesariamente "obras"). OMR determina qué cantidad de evidencia representa
    cada delta; Support **no interpreta** la semántica de la unidad. Ejemplo válido:
    `REVIEW+40`, `REVIEW+60`, `DOCUMENTATION+50` → acumulado 150.
- **Otorgado:** un admin concede CONTRIBUTOR (`kind=GRANTED`, `granted_by=admin {user_id}`)
  revisando la evidencia de OMR ya registrada.

### 5.3 VOICE (otorgado)

Solo administración (`kind=GRANTED`). No se deriva de evidencia musical.

### 5.4 FOUNDER (histórico)

Derivado del **criterio congelado** (`criterion:founder.<id>`), no discrecional. Se materializa
con el backfill del §4 (migra desde `memberships.is_founder`). `active_until=NULL`,
`public=false` hasta que el usuario consienta.

### 5.5 Regla general

Una contribución registrada **no implica** un reconocimiento (D5). El motor solo escribe en
`recognitions` + `recognition_events` cuando una regla se cumple o un admin actúa.

---

## 6. Endpoints

Prefijo existente `/api/v1`. Superficies (ADR-008 + excepciones ADR-015/017):

### 6.1 Usuario (Bearer user token; solo `.../me`, ADR-008)

| Endpoint | Qué hace | Devuelve |
|---|---|---|
| `GET /api/v1/recognitions/me?project=<slug>` | reconocimientos del propio usuario (todos los estados) | `[{type, kind, status, granted_at, active_until, public, origin}]` |
| `PUT /api/v1/recognitions/me/consent` `{project, type, public}` | cambiar consentimiento público (solo el propio usuario; sobre tipo existente) | estado actualizado |

Reglas: el `user_id` sale del token (nunca del body/URL); consentir exige que el
reconocimiento exista; revocar pone `public_revoked_at` y lo oculta de lecturas públicas.

### 6.2 Público consentido (sin token o con token; excepción ADR-015)

| Endpoint | Qué hace | Devuelve |
|---|---|---|
| `GET /api/v1/public/users/{user_id}/recognitions?project=<slug>` | badges públicos consentidos de un tercero | solo filas `status=ACTIVE` y `public=true`: `[{type, granted_at}]` — sin importes, sin historial, sin `origin`/`reason` sensibles |

`project` se valida contra el registro `projects` (whitelisted). Nunca devuelve datos
económicos.

### 6.3 Admin (Bearer user token con rol `support:admin`)

| Endpoint | Qué hace |
|---|---|
| `GET /api/v1/admin/recognitions?user_id&project&type&status` | consulta + historial (`recognition_events`) |
| `POST /api/v1/admin/recognitions` `{user_id, project, type, reason}` | otorgar (`kind=GRANTED`) CONTRIBUTOR/VOICE; rechaza SUPPORTER/FOUNDER |
| `POST /api/v1/admin/recognitions/{id}/revoke` `{reason}` | revocar (→ `status=INACTIVE` + evento `REVOKED`) |

- **Autorización:** los roles salen del claim `roles` del token de usuario (Auth). El
  resolver de identidad actual devuelve solo `user_id` y **rechaza** tokens que no son de
  usuario; se extiende con `resolve_principal() → (user_id, roles)` manteniendo
  `resolve_user_id()` intacto para compatibilidad. Endpoints admin exigen
  `support:admin` en `roles` (fail-closed).
- Todo grant/revoke escribe `reason` y `granted_by` (auditoría).

### 6.4 M2M — contribuciones (service token; excepción ADR-017)

| Endpoint | Qué hace |
|---|---|
| `POST /api/v1/m2m/contributions` | registrar contribución agregada emitida por OMR |

Autenticación: **service token** (OAuth2 `client_credentials` de Auth). Se valida
`token_use=service`, `aud=osap-support`, y el scope `support:ingest`. Los resolvers de
usuario existentes siguen rechazando service tokens; se añade un puerto separado
`ServiceAuthenticator` (ver §7). Devuelve `201 created` o `200 duplicate` (idempotencia).

---

## 7. Contrato M2M con OMR (detalle)

### 7.1 Autenticación

- `Authorization: Bearer <service token>` (client_credentials contra osap-auth).
- Validación en Support: `token_use == "service"`, `aud == osap-support` (config actual
  `identity.audience`), scope requerido `support:ingest`.
- Sin scope/audience válido → `401/403` (fail-closed, nunca degrada a fake en producción).
- Config: se reutiliza `identity.service_client_id/secret` (ya presentes) para documentar el
  par service→Support; Support **no emite** tokens, solo los valida.
- Dev/test: `StaticServiceAuthenticator` con `dev_service_token`.

### 7.2 Request

```http
POST /api/v1/m2m/contributions
Authorization: Bearer <service_token>
Content-Type: application/json

{
  "project": "omr",
  "user_id": "1527",                 // JWT.sub del usuario en OMR (Auth)
  "type": "REVIEW",
  "summary": "revisión de 150 obras",
  "amount": 150,
  "source_reference": "omr/review-summary/2026-09-01/1527"
}
```

### 7.3 Reglas

- `source` lo fija Support a partir del service principal (nunca del body): `omr`.
  `project` debe existir en `projects` (whitelist).
- `user_id` procede de la identidad ya verificada por OMR; Support **no** lo inventa ni lo
  comprueba contra Auth (no hay identidad local, ADR-002); si no existe `support_members`,
  se crea idempotentemente al ingerir (como hace ya el webhook con `_ensure_support_member`).
- Idempotencia: `UNIQUE(source, source_reference)` → segunda emisión `200 {status:
  duplicate}`, sin re-derivar.
- Tras el alta: registro en `contributions` + **evaluar regla CONTRIBUTOR** (§5.2) en la
  misma transacción.
- Respuestas: `201 {id, status: created}` · `200 {id, status: duplicate}` · `422` validación
  · `403` sin scope.
- El **detalle** (las 247 obras, evidencia granular) vive en OMR; Support solo guarda el
  agregado y la referencia.

### 7.4 Lecturas OMR → Support (para composición de badges)

OMR lee reconocimientos por el canal **público consentido** (§6.2) o por `.../me` si el
usuario navega Support. No existe lectura M2M de reconocimientos no consentidos: el
consentimiento es la frontera (ADR-015). Si un caso interno de OMR exigiera badges para un
usuario que no ha consentido y *no* es el propio usuario, se abre decisión aparte.

### 7.5 Contrato de audiencia (FIJADA 2026-09-06)

**Decisión: audiencia por cliente + allowlist, sin debilitar la frontera.** osap-auth emite
tokens con el `aud` del consumidor y osap-support valida **exactamente** `aud =
osap-support` (un único valor), tanto para tokens de usuario como de servicio.

- **Service tokens (`client_credentials`):** `IssueServiceTokenUseCase` parametriza la
  audiencia por cliente. El client `omr-backend` declara `allowed_audiences =
  ["osap-support"]`; el token emitido lleva `aud=osap-support` + `scope support:ingest`.
  Default sin cambio cuando el client no pide audiencia explícita (osap-api/OIDC intactos).
- **User tokens (`/recognitions/me`, consent):** osap-auth login/refresh aceptan una
  `audience` opcional, validada contra la allowlist del cliente/contexto (solo
  `osap-support` cuando la petición procede de la superficie de Support). Default sin
  cambio (login/refresh siguen emitiendo la audiencia global).
- **Verificación:** osap-support `JwksIdentityResolver` (usuario) y `ServiceAuthenticator`
  (servicio) exigen `aud=osap-support` exacto. El patrón de allowlist es el ya existente
  del scope en `client_credentials` (intersección solicitado ∩ permitido). Implica un
  cambio acotado en osap-auth (emisión por cliente) + configuración en osap-support
  (`identity.audience=osap-support`, `[m2m]` allowlist client→proyectos).

---

## 8. Configuración

Nueva sección `[recognitions]` en `osap-support` (`infrastructure/config.py`, convención
`env OSAP_SUPPORT_RECOGNITIONS_* > osap.toml > defaults`):

```toml
[recognitions]
supporter_window_days = 365
contributor_threshold = 150
contributor_types = ["REVIEW", "CONTENT", "TRANSLATION", "DEVELOPMENT", "DOCUMENTATION"]
founder_criterion_id = "founder-2026"
```

Parámetros **de ecosistema** (ADR-016): una sola regla de vigencia para el servicio.

---

## 9. Mapa a archivos del repo `osap-support` (implementación futura)

```
domain/
  entities.py                     # + Project, Recognition(+enums), RecognitionEvent,
                                  #   Contribution(+enums)
  recognitions_rules.py           # + motor de derivación (Supporter/Contributor/Founder)
  ports/identity.py               # + ServiceAuthenticator (service token, scope)
  ports/repositories.py           # + ProjectRepository, RecognitionRepository,
                                  #   RecognitionEventRepository, ContributionRepository
  ports/unit_of_work.py           # (sin cambios)
application/use_cases/
  record_contribution.py          # M2M ingest + derivación CONTRIBUTOR (idempotente)
  get_my_recognitions.py
  set_recognition_consent.py
  admin_grant_recognition.py
  admin_revoke_recognition.py
  recompute_supporter.py          # regla C (gatillo webhook/job)
api/
  routes/recognitions.py          # /me (GET, PUT consent)
  routes/public_recognitions.py   # /public/users/{id}/recognitions
  routes/admin_recognitions.py    # /admin/recognitions...
  routes/m2m_contributions.py     # /m2m/contributions
  main.py                         # wiring de nuevos routers/repos/ports
infrastructure/
  config.py                       # + RecognitionConfig ([recognitions])
  db/models.py                    # + 4 modelos
  db/alembic/versions/0002_*.py   # migración + seed projects + backfill founder (job)
  db/repositories/{project,recognition,recognition_event,contribution}_repository.py
  identity/service_authenticator.py / jwks + static
  worker.py                       # + job diario de recomputación Supporter (--once soportado)
```

Tests: por dominio (reglas), use cases, repos (SQLite con `PRAGMA foreign_keys=ON`),
rutas HTTP, y webhook→derivación (regresión: donación puntual activa Supporter; expiración
lo desactiva).

---

## 10. Parámetros de Fase 1 (cerrados 2026-09-06)

Se cerraron en Fase 1 **sin abrir ADR nuevas** (son valores de configuración o formatos, no
fronteras arquitectónicas):

| Punto abierto | Decisión |
|---|---|
| Umbral de CONTRIBUTOR | **150**, configuración `contributor_threshold`; acumulado sobre el bucket. |
| ¿Uno o varios umbrales? | **Umbral único** sobre el bucket `contributor_types`. Una futura matriz por tipo sería solo configuración, sin migración. |
| Criterio temporal FOUNDER | `founder_criterion_id` congelado (`founder-2026`); backfill determinista desde `is_founder` (ver §4 y comprobación de backfill). La ventana real se fija contra el lanzamiento público del apoyo cuando ocurra; `is_founder` es su materialización. |
| Política de acumulación | **Deltas aditivos**, sin contador físico: `contributions` conserva cada delta y la regla agrega bajo demanda los tipos configurados. Support nunca confía en un total acumulado enviado por OMR. |
| Cliente M2M OMR + Auth | OAuth2 `client_credentials`, scopes `["support:ingest"]`, audience `osap-support`; Support valida `token_use=service`/`aud`/scope y mapea `client_id` → `source` y proyectos permitidos (fail-closed). Pendiente de operación: crear el client `omr-backend` en osap-auth. |
| Formato del evento | Envelope `schema_version: 1` (fijado en §7). `source` se deriva del client autenticado; nunca viaja en el body. |

Pendientes de implementación/operación (no de diseño): crear el client `omr-backend` en
osap-auth, definir el emisor OMR (cadencia/agregación, trabajo en el repo OMR) y fijar la
fecha de lanzamiento público del apoyo cuando ocurra.

---

## 11. Cierre operativo de 4D (2026-09-06)

Estado: **4D cerrado. osap-support terminado** en cuanto a superficie + persistencia de
reconocimientos/contribuciones. El trabajo OMR → Support pasa a ser **integración del
ecosistema** (emisor M2M en OMR), no desarrollo pendiente de Support.

Ejecutado:
- **osap-auth**: scope `support:ingest` añadido al registro `VALID_SCOPES`; CLI
  `create-client` acepta `--audiences`; migración `0008_add_service_client_audiences`
  aplicada a la BD local de desarrollo. Alta del client M2M **`omr-backend`**
  (`client_id=714e4e6e-41ea-4f78-90b0-8c01da7db0e6`, `scopes=["support:ingest"]`,
  `allowed_audiences=["osap-support"]`). El secreto solo se muestra en el alta (dev); en
  producción se regenera al dar de alta el client real.
- **osap-support**: secciones `[recognitions]` (defaults de Fase 1) y `[m2m]` (allowlist
  `omr-backend → source=omr, projects=[omr]`) configuradas en el `osap.toml` de desarrollo.
  Backfill de Founder ejecutado (`scripts/backfill_founder.py`, criterio `founder-2026`,
  idempotente) → `created=0` en la BD dev (sin membresías founder aún).
- **Suite**: 164 passed en osap-support; ruff/mypy limpios.

Pendientes SOLO de operación (host de producción / lanzamiento público):
1. `osap.production.toml` de osap-support: replicar `[recognitions]`, `[m2m]` con el
   `client_id` real de `omr-backend` en producción y `identity.audience=osap-support`.
2. Ejecutar el backfill de Founder tras el lanzamiento real (o cuando haya `is_founder`).
3. Definir el emisor M2M en OMR (cadencia/agregación de REVIEW/CONTENT/TRANSLATION/
   DEVELOPMENT/DOCUMENTATION) — integración del ecosistema, no de Support.
4. Fijar la fecha de ventana real del lanzamiento público del apoyo.
