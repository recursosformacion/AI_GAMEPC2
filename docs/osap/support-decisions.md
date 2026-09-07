# OSAP Support — Decisiones arquitectónicas (ADR) y registro de variantes

> **Registro consolidado de decisiones de OSAP Support.** Nacido en la **fase documental**
> (2026-08-29, ADR-001…012); el servicio `osap-support` se implementó y se cerró para
> producción (2026-09-05) siguiendo esas decisiones. ADR-013…017 (2026-09-06) amplían el
> registro con el dominio de reconocimientos y contribuciones.
> Fuentes: `support-architecture-separation.md`, `support-frontend-boundary-v1.md`,
> `support-ecosystem-architecture.md`, `osap-support-architecture.md`, `support-phase1-support-page.md`,
> + inspección de la implementación actual (`web/src/support`, `web/src/pages/SupportPage.tsx`, `web/src/state/auth.ts`).
> Fecha: 2026-08-29 · Actualizado: 2026-09-06

---

# Cómo leer este documento

Toda decisión relevante queda clasificada en **tres estados**, que **no deben mezclarse**:

| Estado | Significado |
|---|---|
| **FIJADA** | Decisión aprobada. Es **contrato arquitectónico**. No reabrir sin nueva evidencia técnica documentada. |
| **DESCARTADA** | Alternativa analizada y **deliberadamente rechazada** con motivo. No volver a proponer como nueva sin explicar qué evidencia invalida el descarte. |
| **ABIERTA / FUTURA** | Todavía **no decidida**. No implementar ni convertir en decisión actual. |

> **Abierto no significa olvidado. Significa deliberadamente no decidido todavía.**

---

## Architectural Decision Record / ADR

### ADR-001 — Support como servicio independiente

**Decisión fijada:**

OSAP Support es **propietario de la relación de apoyo** entre una identidad OSAP y el proyecto. **No es propietario** de:

- Identidad, autenticación, credenciales.
- Datos sensibles del medio de pago.
- Plataforma musical.

Propietarios por ámbito:

| Ámbito | Propietario |
|---|---|
| Identidad | Auth |
| Datos sensibles del pago | Payment Provider |
| Plataforma musical | OSAP API / Chorus |
| Relación de apoyo, economía no sensible, eventos, comunicaciones económicas | Support |

**Por qué:** evita duplicar identidad/economía y permite a osap-app, Chorus y Social compartir una única relación de apoyo.
**Obliga a:** Support a exponer API; a no depender de BBDD/código ajenos; a referenciar identidad por `sub`.
**Evita:** membreías duplicadas, acoplamiento físico, rehacer con Social.
**Queda libre:** proveedor de pagos, proveedor de email, hosting, despliegue físico.

---

### ADR-002 — Identidad mediante Auth

**Decisión fijada:**

Support **no crea ni administra usuarios**. La identidad canónica es:

```text
JWT.sub == Auth.user_id
```

Support usa `user_id` como **referencia externa**. No habrá: tabla local de usuarios, contraseña local, login local ni identidad paralela.

**Por qué:** Auth es la autoridad única de identidad; evita divergencia y sincronización de cuentas.
**Obliga a:** validar JWT de Auth (JWKS) para derivar `sub`; usar `sub` como `user_id`; obtener email vía Auth de servicio cuando se necesite.
**Evita:** credenciales duplicadas, identidades divergentes, duplicación Google/GitHub/email.
**Queda libre:** mecanismo JWKS, implementación interna de `IdentityResolver`.

---

### ADR-003 — Base de datos propia

**Decisión fijada:**

Support tendrá una **BD propia**:

```text
osap_support
```

**No** accederá directamente a las BD de Auth, osap-api, osap-app, Chorus ni Social.

**Por qué:** independencia física y de portabilidad (poder desplegar Support en otra máquina).
**Obliga a:** definir tablas propias, migraciones propias, configuración de BD por entorno.
**Evita:** acoplamiento físico y migraciones entre servicios.
**Queda libre:** el motor (recomendado MySQL, consistente con el ecosistema).

---

### ADR-004 — Membership y Donation separados

**Decisión fijada:**

**No** crear inicialmente una abstracción genérica `SupportContribution`. Se mantienen como entidades **distintas**:

```text
Membership   → relación recurrente
Donation     → aportación puntual
```

Ambas dependen de `SupportMember` y `PaymentEvent`.

**Variante descartada:** `SupportContribution` unificado. **Motivo:** abstracción prematura mientras los comportamientos (periodicidad, renovación, expiración) siguen siendo diferentes.

**Por qué:** recurrente ≠ puntual; unificarlas fuerza modelos artificiales.
**Obliga a:** dos tablas/entidades (o una con tipo si los campos terminan convergiendo — se decidirá con datos reales).
**Evita:** semántica confusa y casos vacíos.
**Queda libre:** a futuro, unificar si la experiencia demuestra que convergen.

---

### ADR-005 — PaymentProvider como port

**Decisión fijada:**

Support **no queda acoplado** a un proveedor de pagos concreto. La integración se hace mediante el port:

```text
PaymentProvider
```

El proveedor concreto queda como **infraestructura intercambiable**.

**Deriva de:** ADR-001 + principio de no elegir proveedor todavía.
**Obliga a:** definir la interfaz `PaymentProvider` (checkout, webhook, resolver customer/subscription); nunca llamar a SDK del proveedor desde el dominio.
**Evita:** dependencia del proveedor, reescritura al cambiar.
**Queda libre:** proveedor concreto (Stripe/Patreon/Ko-fi/PayPal/GitHub Sponsors...), detalles del checkout.

---

### ADR-006 — EmailSender como port

**Decisión fijada:**

Support es propietario de las comunicaciones de la relación económica. Se usa el port:

```text
EmailSender
```

**No** se implementa todavía un proveedor real. El flujo es:

```text
PaymentEvent → CommunicationEvent → worker → EmailSender
```

**Nunca:** `webhook → email directo`.

**Por qué:** trazabilidad, reintentos, idempotencia y control (evita spam involuntario).
**Obliga a:** `CommunicationEvent` persistente (pending/sent/failed, attempts, origin_event_id), worker/scheduler.
**Evita:** emails sin control, duplicados, imposibilidad de auditar "por qué se envió".
**Queda libre:** proveedor de email, plantillas, timing.

---

### ADR-007 — Webhooks idempotentes

**Decisión fijada:**

La clave de idempotencia del proveedor es:

```text
(provider, provider_event_id)
```

con restricción:

```text
UNIQUE(provider, provider_event_id)
```

Los eventos se **registran antes** de aplicar efectos (INSERT + ON DUPLICATE KEY → `ignored_duplicate` + responder 2xx).

**Por qué:** el proveedor puede reintentar/duplicar; idempotencia evita doble cargo/estado y doble email.
**Obliga a:** tabla `payment_events` con la clave UNIQUE; procesamiento derivado del evento.
**Evita:** procesamiento doble, estados corruptos, envío doble de emails.
**Queda libre:** el formato exacto de `provider_event_id` (lo entrega el proveedor).

---

### ADR-008 — `.../me` como API de usuario

**Decisión fijada:**

Las aplicaciones normales **no** reciben ni modifican membresías mediante IDs de usuario en la URL. La API canónica es:

```text
GET  /api/v1/membership/me
```

No se crea inicialmente (para operaciones normales):

```text
GET /membership/{id}
PUT /membership/{id}
```

**Por qué:** deriva la identidad del token (`sub`); evita ID-oracle y autorización innecesaria.
**Obliga a:** endpoints `.../me` autenticados; endpoints admin con rol separado.
**Evita:** exponer/romper el ID de otro usuario; autorización por URL.
**Queda libre:** endpoints administrativos `/admin/*` (rol admin).

**Excepciones acotadas (sin derogación):** ADR-008 sigue siendo la **regla general** para las superficies de usuario. ADR-015/017 introducen **excepciones explícitas y acotadas**: (1) **lectura pública consentida** de reconocimientos de un tercero (solo registros con `public=true`, sin datos económicos) y (2) **comunicación M2M** service-to-service con service token (p. ej. contribuciones OMR → Support). Los endpoints `.../me` de usuario no cambian.

---

### ADR-009 — SupportGateway (frontera frontend)

**Decisión fijada:**

El frontend usa `SupportGateway` como frontera.

Actual:

```text
SupportPage → useSupport() → LocalSupportGateway
```

Futuro:

```text
SupportPage → useSupport() → SupportApiClient → osap-support
```

Objetivo: sustituir la implementación **sin reescribir la página**.

**Por qué:** la UI no debe depender del futuro servicio/proveedor.
**Obliga a:** mantener el contrato `SupportSummary`/`SupportGateway` estable (ya implementado); swap local→api.
**Evita:** reescribir páginas al integrar Support; acoplar UI al proveedor.
**Queda libre:** implementación de `SupportApiClient`, URL de Support, mapeo interno.

---

### ADR-010 — Chorus/osap-app sin extracción física todavía

**Decisión fijada:**

La separación física de Chorus y osap-app es **futura**. No se realiza la migración de la SPA. La extracción debe ser **incremental y reversible**.

**Por qué:** reducir el riesgo; la SPA ya separó lógicamente la frontera frontend.
**Obliga a:** mantener el monorepo por ahora; no mover archivos prematuramente; parametrizar URLs antes de extraer.
**Evita:** romper el sistema actual con una gran migración.
**Queda libre:** cuándo y cómo se hará la extracción física.

---

### ADR-011 — Stack tecnológico

**Decisión fijada/recomendada:**

Mantener el stack del **servicio pequeño de referencia** (`osap-auth`):

```text
FastAPI · uvicorn · Pydantic v2 · pydantic-settings · MySQL · Alembic · PyJWT · httpx
pytest · pytest-asyncio · ruff · mypy
```

Python **≥ 3.12** recomendado (consistentemente con osap-api).

**Variante descartada:** introducir otro runtime/framework sin necesidad técnica. **Motivo:** no aporta ventaja y aumenta la fragmentación operativa.

**Por qué:** reutiliza el conocimiento del equipo; portabilidad y mantenimiento máximos.
**Obliga a:** reproducir la estructura hexagonal de osap-auth en osap-support.
**Evita:** fragmentación de stacks, coste de aprendizaje, mantenimiento extra.
**Queda libre:** detalles de librerías auxiliares dentro del mismo stack.

---

### ADR-012 — Estado de Membership ausente

**Decisión fijada:**

`GET /api/v1/membership/me`, para un usuario autenticado sin Membership, responde **`200 OK`** con el contrato vacío tipado:

```json
{
  "status": null,
  "level": null,
  "started_at": null,
  "next_renewal_at": null,
  "is_founder": false
}
```

**Motivo (Alternativa B):** el endpoint representa el **estado de apoyo del usuario autenticado**, no la existencia de un recurso independiente. La ausencia de Membership es un **estado válido del dominio**, no un error HTTP. Evita `404` como semántica de ausencia y evita que el cliente tenga que distinguir entre `null` como respuesta completa y un objeto de estado. `is_founder` será `false` cuando no exista Membership.

**Consecuencias:**
- No se crea automáticamente una fila `support_members` para todo usuario autenticado.
- `SupportMember` representa una **relación de apoyo**, no una segunda identidad ni un registro obligatorio por usuario de Auth.
- La ausencia de `SupportMember` y/o `Membership` se resuelve como ausencia de estado de apoyo → contrato vacío tipado.
- Contrato de respuesta del caso con Membership: `{ status, level, started_at, next_renewal_at, is_founder }` (arquitectura §14).

**Variante elegida:** V-022 — `200 OK` con estado vacío tipado. **FIJADA.**
**Variantes descartadas:** V-023 — `200 + null` (cliente debe distinguir null-completo vs objeto); V-024 — `404` (ausencia ≠ error de recurso).

---

### ADR-013 — Planes económicos, `user_tier` y reconocimientos son dimensiones distintas

**Estado: FIJADA.** (2026-09-06, tras la pasada de coherencia documental con ADR-001…012).

**Decisión fijada:**

Existen **tres dimensiones independientes** que nunca deben fusionarse ni ordenarse como una jerarquía única:

| Dimensión | Significado | Propietario |
|---|---|---|
| `user_tier` | clasificación/capacidad de la cuenta de Auth (free/basic/premium, …) | osap-auth |
| **Plan económico** | relación comercial con Support: producto con importe y periodicidad, anclado a un plan PayPal | osap-support |
| **Reconocimiento** | badge sobre la relación de una persona con un proyecto, con reglas de concesión propias | osap-support |

Los nombres `supporter`, `contributor`, `voice`, `founder` existen hoy en dos de esas dimensiones con significados distintos que **no se fusionan**:

| Dominio | Qué es | Dónde vive hoy |
|---|---|---|
| **Producto económico** | Suscripción/donación con importe y periodicidad, anclada a un plan PayPal | `memberships`/`donations`, `PaymentConfig.plan_*`, `docs/paypal.md` |
| **Reconocimiento** | badge con reglas de concesión propias | no existe todavía (entidad nueva, ADR-015) |

Que los nombres **coincidan visualmente** (`membership.plan = supporter_monthly`, `recognition.type = supporter`) no es un problema técnico, siempre que nunca se traten como la misma entidad.

**Por qué:** hoy "¿el usuario es supporter?" es ambiguo (¿tiene el plan?, ¿donó?, ¿tiene el badge?, ¿lo es ahora?, ¿lo fue?), y con `user_tier` de Auth podría aparecer además "premium". Fijar las tres dimensiones como independientes elimina la bomba semántica antes de añadir reconocimientos.

**Obliga a:**
- No tocar ahora `support_members`, `memberships`, `donations`, planes PayPal, webhooks ni la máquina de estados (ADR-004 intacto).
- Crear reconocimientos como entidad independiente con su propia semántica (ADR-015).
- No mezclar `user_tier` (Auth) con planes económicos ni con reconocimientos en ningún contrato/UI agregada.
- Corregir la contradicción documental: `osap-support-architecture.md` §4.2 describía los niveles como "niveles de apoyo (no económico)" cuando son productos con importe → reescrito como producto económico cuyo nombre coincide con reconocimientos (**aplicado 2026-09-06**).

**Evita:** tratar badges como tiers económicos, tiers económicos como badges y cualquiera de ellos como `user_tier`; decisiones de negocio disfrazadas de accidentes de código.

**Queda libre (ABIERTA):** ADR-013 **no decide la revisión comercial** de los productos económicos actuales: no aprueba ni descarta los 8 planes (`supporter/contributor/voice/founder` × monthly/yearly, con sus importes, periodicidades y continuidad). Decide **únicamente** que esa revisión pertenece al dominio económico y que no debe confundirse con los reconocimientos. La semántica concreta de `user_tier` pertenece a osap-auth.

---

### ADR-014 — Una persona = una relación de apoyo al ecosistema (no por aplicación)

**Estado: FIJADA.** (2026-09-06, tras la pasada de coherencia documental).

**Decisión fijada:**

Se mantiene la decisión existente, ahora explícita:

> Una identidad OSAP tiene **una única relación de apoyo al ecosistema** (`support_members`), no una relación por aplicación/proyecto.

No se modela ahora:

```
María ── apoya OMR
María ── apoya Chorus        ← descartado en esta fase
```

**Por qué:** soportar relaciones de apoyo simultáneas por proyecto multiplica la complejidad de PayPal, planes, webhooks, renovaciones, identidad, UX y contabilidad, sin necesidad actual.

**El ámbito `project` se introduce solo donde tiene sentido semántico**, no en la economía:
- **Reconocimientos**: sí tienen `project_id` (OMR → Contributor; Chorus → Voice) — ADR-015.
- **Contribuciones**: sí tienen `project_id` — ADR-017.
- **Economía** (memberships/donations): sin `project` por ahora; la relación es al ecosistema.

**Obliga a:** no migrar `support_members` ni `memberships`/`donations` para añadir dimensión de proyecto en esta fase; los proyectos (y sus reconocimientos/reglas) se registran de forma whitelisted cuando se cree la entidad `projects` (fase 2).

**Evita:** la explosión de membresías simultáneas, mapeos plan→proyecto en webhooks y duplicación de circuitos de pago.

**Queda libre (FUTURA/ABIERTA):** abrir apoyos etiquetados por proyecto si algún día el negocio lo exige; registro canónico de proyectos del ecosistema.

---

### ADR-015 — Modelo de reconocimientos: histórico / derivado / otorgado + consentimiento

**Estado: FIJADA.** (2026-09-06, tras la pasada de coherencia documental).

**Decisión fijada:**

Se crea la entidad de dominio:

```
recognition
  id                PK
  user_id           FK → support_members.user_id (nunca una identidad local)
  project_id        ámbito del reconocimiento. FK → projects (whitelisted). Siempre poblado.
  type              SUPPORTER | CONTRIBUTOR | VOICE | FOUNDER
  kind              historical | derived | granted   (naturaleza)
  granted_at        momento en que el reconocimiento es efectivo
  granted_by        nullable. SOLO cuando kind=granted: admin {user_id} o system.
                    NULL en historical/derived: no hay concesión manual.
  origin            nullable. Mecanismo de producción cuando NO es concesión manual:
                      · derived   → referencia a la regla (ej. rule:supporter.active_or_donated_12m,
                                     rule:contributor.omr_evidence)
                      · historical→ referencia al criterio congelado (ej. criterion:founder.window_2026)
                      · granted   → NULL (el mecanismo es la concesión; vive en granted_by)
  reason            texto corto, auditable
  active_until      nullable → NULL = no caduca
  public            bool  = consentimiento expreso opt-in
  public_since      nullable
  public_revoked_at nullable
```

**`granted_by` es opcional y solo significa concesión manual para `kind=granted`.** Para FOUNDER y SUPPORTER la columna queda NULL y quien explica la existencia del reconocimiento es `origin` (criterio o regla). Así no hay una columna obligatoria que conceptualmente no corresponde a los reconocimientos derivados.

**Ámbito por proyecto y proyecto canónico de ecosistema.** El registro `projects` futuro incluirá un **proyecto canónico de ámbito `ecosystem`** (distingo de OMR, Chorus, etc.). Los reconocimientos que se derivan de la relación económica global — SUPPORTER (ADR-016) y el criterio histórico FOUNDER — usan ese proyecto canónico, porque su relación de origen no pertenece a OMR ni a Chorus. Esto mantiene `project_id` siempre poblado y el modelo uniforme, **sin NULL semántico** como sustituto de "global".

Naturaleza y concesión por tipo:

| type | Naturaleza | project_id | Cómo se produce |
|---|---|---|---|
| FOUNDER | histórica | canónico `ecosystem` | derivado del criterio temporal congelado; `origin = criterion:founder.*`; `active_until = NULL` |
| SUPPORTER | derivado | canónico `ecosystem` | regla de vigencia ADR-016; nunca manual; `origin = rule:supporter.*` |
| CONTRIBUTOR | derivado u otorgado | proyecto concreto (ej. OMR) | derivado por Support a partir de evidencia del proyecto, **o** concedido por administración según esa evidencia (ADR-017) |
| VOICE | otorgado | proyecto concreto (ej. Chorus) | concedido por administración (`kind=granted`, `granted_by`); no se deriva de evidencia |

**Consentimiento:** `public = true` significa *"el usuario ha autorizado expresamente que este reconocimiento aparezca en público"*, y es **revocable** (→ `public_revoked_at`, se oculta). Chorus y cualquier app solo leen reconocimientos consentidos y **nunca** datos económicos (importes, historial, método).

**Por qué:** "todo es un badge y alguien pulsa un botón" pierde la distinción esencial entre lo que se deriva de un criterio (Founder), lo que se deriva de una condición (Supporter) y lo que se otorga con evidencia o administración (Contributor/Voice). Y `public=true` sin consentimiento revocable no es privacidad.

**Obliga a:**
- Reconocimientos con ámbito de proyecto (con canónico `ecosystem`), producción auditable (`origin`/`granted_by`/`reason`), y reglas de derivación en Support (no en las apps).
- Superficies API nuevas que matizan ADR-008: `.../me` (usuario), lectura **pública consentida** (badges de un tercero con `public=true`) y **M2M** con service token para contextos internos. Ninguna devuelve datos económicos.
- Migración futura: tabla `recognitions` + registro `projects` (fase 2).

**Evita:** autobombo, badges inventados por apps, reconocimientos globales que arrastran la comunidad de OMR a Chorus, NULL con significado semántico, y exposición pública sin control del usuario.

**Queda libre (ABIERTA):** otros tipos de reconocimiento futuros por proyecto; si algún reconocimiento otorgado debe caducar (`active_until` poblado); criterio concreto del Founder; forma exacta del registro `projects`.

---

### ADR-016 — Vigencia de Supporter: regla derivada "C" (vigente vs histórico)

**Estado: FIJADA.** (2026-09-06, tras la pasada de coherencia documental).

**Decisión fijada:**

`SUPPORTER` es un reconocimiento **derivado** (ADR-015), nunca otorgado manualmente, con esta regla de negocio explícita:

> Supporter está **vigente** mientras exista **una membresía activa** **o** **una donación completada en los últimos 12 meses**.

La ventana (12 meses) es un **parámetro de negocio de Support/ecosistema**, no por proyecto. Dado que la relación económica es global al ecosistema (ADR-014), la regla de vigencia es **única** para el servicio; si en el futuro campañas o proyectos necesitan reglas distintas, eso será una decisión nueva (queda ABIERTA), no un ajuste local.

**Estados de la regla:**

- **Vigente** — se muestra como Supporter (en público solo si existe consentimiento, ADR-015).
- **Histórico** — deja de cumplir la condición; permanece en auditoría, pero **no aparece como badge vigente** ni en lecturas públicas.

La ADR fija la **regla de negocio**; **no** obliga todavía a una estrategia concreta de filas para las sucesivas activaciones/desactivaciones (fila mutable, pares vigente/histórico, tabla de estados…). Eso se decide en el diseño de la tabla/migración (fase 2).

**Variantes descartadas:**
- **A** (solo membresía activa): deja fuera a las donaciones puntuales, que hoy son un circuito real y cerrado.
- **B** (solo donación ≤12m): excluye la relación recurrente, que es el núcleo actual.
- "Donó alguna vez → Supporter para siempre": badge perpetuo sin relación, filtra información económica antigua y no refleja el estado real.

**Comportamiento resultante:**
- La derivación la computa Support (al completarse un pago, al renovar, al cancelar/expirar y al vencerse la ventana). Las apps nunca la calculan.
- Al dejar de cumplirse la condición, el reconocimiento pasa a **histórico** y se **oculta de lo público** automáticamente (si estaba consentido).

**Por qué:** una regla única y explícita elimina la ambigüedad de "¿es Supporter?" (ADR-013) y da reconocimiento también a quien apoya de forma puntual, sin convertirlo en un distintivo eterno.

**Obliga a:** definir la derivación como caso de uso (o job) en Support con las transiciones descritas; alinear la caducidad con la ocultación pública (ADR-015); parametrizar la ventana en la configuración del servicio.

**Evita:** Supporter perpetuo por una donación antigua; badge que miente sobre el estado actual; interpretaciones distintas según la app o el proyecto.

**Queda libre (ABIERTA):** ajustar la duración de la ventana; política de "Supporter histórico" interno para la wall de supporters; reglas por proyecto/campaña en el futuro (decisión separada); estrategia de persistencia de vigente/histórico.

---

### ADR-017 — Contrato de contribuciones y composición (OMR → Support → Chorus)

**Estado: FIJADA.** (2026-09-06, tras la pasada de coherencia documental).

**Decisión fijada:**

**A. Las contribuciones son agregados con origen, nunca autodeclaraciones**

`osap-support` **no** almacena el detalle ("María corrigió 247 obras"). Almacena referencias de contribución emitidas por el sistema fuente:

```
contribution
  user_id
  project_id
  type            CONTENT | REVIEW | TRANSLATION | DEVELOPMENT |
                  DOCUMENTATION | COMMUNITY | PROMOTION | OTHER
  summary         agregado corto, human-readable (ej. "revisión de 247 obras")
  source          sistema que emite la contribución (ej. "omr")
  source_reference  id idempotente del origen (ej. omr/review-summary/1234)
  created_at
  UNIQUE(source, source_reference)
```

**B. El usuario nunca declara su propia contribución**

No se permite "He revisado 2.000 partituras". El flujo es:

```
OMR detecta actividad → emite evento/contribución (M2M, idempotente)
    → osap-support registra la referencia + evalúa reconocimiento
```

La evidencia la genera el sistema correspondiente; el usuario, como mucho, solicita colaborar.

**C. Una contribución registrada no implica necesariamente un reconocimiento**

`contribution` y `recognition` son cosas distintas: puede existir una contribución registrada **sin** que alcance el criterio de CONTRIBUTOR. No toda actividad se convierte en un badge; el reconocimiento solo nace cuando la regla/criterio definido en Support se cumple. La contribución sin reconocimiento sigue siendo dato útil de Support (historial de actividad reconocida por el sistema), pero no produce badge por sí sola.

Semántica de los reconocimientos derivados de contribución:

- **CONTRIBUTOR** puede producirse de dos formas, siempre sobre evidencia del proyecto (OMR):
  - **derivado** automáticamente por Support cuando la evidencia acumulada alcanza el criterio de la regla (`kind=derived`, `origin = rule:contributor.omr_evidence`), o
  - **otorgado** por administración que revisa y confirma esa misma evidencia (`kind=granted`, `granted_by = admin {user_id}`).
- **VOICE** es propiamente otorgado por administración; no se deriva de evidencia musical.

**D. Fuentes de verdad por dominio**

| Dato | Fuente de verdad |
|---|---|
| Identidad (`user_id`, nombre, avatar) | osap-auth |
| Actividad musical (obras aportadas, revisiones, evidencia) | OMR |
| Apoyos, reconocimientos públicos, contribuciones-ref | osap-support |
| Perfil comunitario compuesto | osap-chorus (compone, no duplica) |

Chorus construye el perfil compuesto leyendo a Auth, OMR y Support, y **no** se convierte en dueño de ninguno de esos datos ni en una base de datos paralela del ecosistema.

**Por qué:** duplicar el detalle en Support crea deriva y superficie RGPD; permitir autodeclaraciones abre la puerta al autobombo y la manipulación; la composición por Chorus evita una cuarta copia de usuarios/donaciones/badges; y forzar que cada contribución sea un reconocimiento degradaría los badges.

**Obliga a:**
- Contrato M2M idempotente (service token) OMR→Support con `UNIQUE(source, source_reference)`.
- Matizar ADR-008: además de `.../me`, existirán superficies **pública consentida** y **M2M** para reconocimientos/contribuciones; los endpoints de usuario siguen sin exponer IDs ajenos por URL.
- No guardar en Support: las 247 obras, el detalle de actividad ni datos económicos en entidades consumibles por la comunidad.
- Reglas de derivación de CONTRIBUTOR en Support (criterio sobre evidencia), alineadas con ADR-015.

**Evita:** el ecosistema con cuatro "usuarios" duplicados (Auth/OMR/Support/Chorus), drift de contadores, manipulación de contribuciones por autodeclaración y la inflación de badges (cada actividad → badge).

**Queda libre (ABIERTA):** tipos de contribución adicionales, cadencia/eventos exactos que OMR emite, criterio numérico de la regla de CONTRIBUTOR, plantillas de resumen por proyecto, y el formato concreto del evento OMR→Support cuando se implemente la fase 4.

---

## Tabla global de variantes

| ID | Decisión | Variante | Estado | Motivo |
|---|---|---|---|---|
| V-001 | Identidad | Usuarios locales en Support | DESCARTADA | rompe separación Auth/Support |
| V-002 | Identidad | JWT.sub de Auth | **FIJADA** | identidad única |
| V-003 | BD | Compartir BD de Auth | DESCARTADA | acoplamiento físico |
| V-004 | BD | BD propia | **FIJADA** | independencia |
| V-005 | Pagos | Integración directa proveedor | DESCARTADA | acoplamiento |
| V-006 | Pagos | PaymentProvider port | **FIJADA** | proveedor intercambiable |
| V-007 | Donaciones | Unificar con Membership | DESCARTADA | semántica diferente |
| V-008 | Donaciones | Entidad Donation independiente | **FIJADA** | recurrente ≠ puntual |
| V-009 | Email | Webhook → email directo | DESCARTADA | falta de control/reintentos |
| V-010 | Email | CommunicationEvent + worker | **FIJADA** | trazabilidad/idempotencia |
| V-011 | Frontend | SupportPage → API directa | DESCARTADA | acopla UI |
| V-012 | Frontend | SupportGateway | **FIJADA** | frontera estable |
| V-013 | API usuario | `/membership/{id}` | DESCARTADA | ID-oracle / autorización innecesaria |
| V-014 | API usuario | `/membership/me` | **FIJADA** | identidad derivada del token |
| V-015 | Arquitectura | Support dentro de Auth | DESCARTADA | mezcla identidad y economía |
| V-016 | Arquitectura | Servicio independiente | **FIJADA** | separación de responsabilidades |
| V-017 | Entidades | Abstracción `SupportContribution` | DESCARTADA | abstracción prematura |
| V-018 | Entidades | Membership + Donation separados | **FIJADA** | comportamientos distintos |
| V-019 | Email | Servicio de email externo separado | **ABIERTA** | puede extraerse cuando el volumen crezca |
| V-020 | Dinero | Float (10.50) | DESCARTADA | riesgo de precisión |
| V-021 | Dinero | Mínimas unidades (int micro/centavos) | **FIJADA** | sin floats, cálculo exacto |
| V-022 | API usuario | `200 OK` + estado vacío tipado sin membership | **FIJADA** | ausencia = estado válido del dominio (ADR-012) |
| V-023 | API usuario | `200 + null` sin membership | DESCARTADA | cliente debe distinguir null-completo vs objeto (ADR-012) |
| V-024 | API usuario | `404` sin membership | DESCARTADA | ausencia ≠ error de recurso (ADR-012) |

> V-020/V-021 se derivan del documento de arquitectura (`amount` en mínimas unidades, currency ISO 4217).
> V-022/V-023/V-024 se derivan de ADR-012 (estado de Membership ausente).

---

## Matriz de alcance

| Área | Auth | Support | OSAP API | Chorus | osap-app | Proveedor externo |
|---|---|---|---|---|---|---|
| Identidad | **propietario** | consume | consume | consume | consume | — |
| Login | **propietario** | — | — | consume | consume | Google/GitHub |
| Membership | — | **propietario** | — | consume | consume | Payment Provider |
| Donation | — | **propietario** | — | consume | consume | Payment Provider |
| Tarjeta/CVV | — | — | — | — | — | **propietario** |
| Emails económicos | — | **propietario** | — | — | — | Email Provider |
| Música | — | — | **propietario** | propietario UI | — | — |
| Soporte (página apoyo) | — | **propietario** | — | consume | consume | — |
| Comunidad (perfil público) | — | (futuro) propietario | — | consume | consume | — |
| Red social | — | — | — | — | — | (Social futuro) |

---

## Contratos que deben considerarse estables

> Estos contratos son **más importantes que los detalles internos** de implementación. No cambiarlos innecesariamente.

| Contrato | Valor |
|---|---|
| Identidad | `JWT.sub` → `Auth.user_id` |
| Frontend | `SupportGateway` (interfaz `getSummary`, `SupportSummary`) |
| Pagos | `PaymentProvider` (port) |
| Email | `EmailSender` (port) |
| Usuario | `GET /api/v1/membership/me` |
| Webhook | `(provider, provider_event_id)` (idempotencia) |

---

## Decisiones deliberadamente abiertas

**Abierto no significa olvidado. Significa deliberadamente no decidido todavía.**

- Proveedor de pagos concreto.
- Proveedor de email concreto.
- Proveedor de hosting.
- Docker vs venv.
- Frecuencia exacta del scheduler.
- Política definitiva de retención fiscal.
- Comunidad/social (perfil público, "Descubrir").
- Recompensas por donación (relacionado con la vigencia de Supporter, ADR-016).
- **Revisión comercial de los productos económicos actuales** (nombres/umbrales/continuidad). ADR-013 **no la decide**: solo fija que pertenece al dominio económico y no debe confundirse con los reconocimientos.
- Diseño final del checkout.
- Panel administrativo.
- Implementación definitiva de `SupportApiClient`.
- Servicio de email externo separado (vs módulo interno).

---

## Consecuencias de las decisiones (en formato Decisión→Por qué→Obliga→Evita→Libre)

### Consecuencia 1 — Support usa `JWT.sub` como referencia de identidad (ADR-002)
- **Por qué:** Auth es la autoridad única de identidad.
- **Obliga:** validar JWT de Auth; usar `sub` como `user_id`; no crear usuarios locales.
- **Evita:** sincronización de cuentas; credenciales duplicadas; identidad divergente.
- **Queda libre:** proveedor de JWT; mecanismo JWKS; implementación interna de `IdentityResolver`.

### Consecuencia 2 — Support con BD propia (ADR-003)
- **Por qué:** independencia física/portabilidad.
- **Obliga:** tablas y migraciones propias; config de BD por entorno.
- **Evita:** acoplamiento físico; migraciones entre servicios.
- **Queda libre:** motor (recomendado MySQL), esquema detallado de tablas.

### Consecuencia 3 — PaymentProvider y EmailSender como ports (ADR-005/006)
- **Redes:** dominio aislado de proveedores externos.
- **Obliga:** definir ports; comunicación vía eventos/colas.
- **Evita:** dependencia de proveedor; reescritura al cambiar.
- **Queda libre:** proveedores concretos.

### Consecuencia 4 — `.../me` en la API (ADR-008)
- **Por qué:** identidad derivada del token.
- **Obliga:** endpoints `.../me`; admin separado con rol.
- **Evita:** ID-oracle; autorización por URL.
- **Queda libre:** endpoints administrativos futuros.

---

## Regla contra el scope creep

> Si durante la implementación aparece una necesidad que obliga a **romper una decisión FIJADA** o **ampliar significativamente una frontera**, no resolverla mediante una refactorización improvisada.
>
> Primero:
> 1. documentar el conflicto;
> 2. identificar qué decisión afecta;
> 3. presentar variantes;
> 4. explicar consecuencias;
> 5. solicitar una nueva decisión arquitectónica.
>
> Prioridad:
> **frontera pequeña y correcta > gran refactorización prematura.**

---

## Inconsistencias detectadas

> No se ha silenciado ningún cambio: se documentan las discrepancias y la decisión actualmente considerada válida.

| Documento | Sección | Conflicto | Decisión válida hoy | Requiere aprobación |
|---|---|---|---|---|
| `support-phase1-support-page.md` | Página `/support` | Documenta `/support` usando `useAuth` directo | `support-frontend-boundary-v1.md` (más reciente) documenta `useSupport()`/`SupportGateway`; la implementación usa el gateway | No (es doc previo a la frontera) |
| `support-frontend-boundary-v1.md` | API futura | Usa `/membership/me` sin prefijo en un punto | Prefijo canónico: `/api/v1/membership/me` | No (prefijo estándar) |
| i18n `support.startCta` / `support.title` | web | Texto dice "Chorus" ("Apoyar Chorus") vs ecosistema "OSAP" | La página es de Chorus hoy; el nombre de marca del ecosistema puede ajustarse en una decisión futura de naming | **Sí** (naming de marca) |

---

## Historial de decisiones

2026-08-29
- SupportGateway fijado como frontera frontend.
- Support definido como propietario de la relación de apoyo.
- Auth permanece propietario de identidad.
- Support no almacena datos sensibles de pago.
- Membership y Donation permanecen separados.
- PaymentProvider y EmailSender se mantienen como ports.
- Webhooks idempotentes por `(provider, provider_event_id)`.
- API de usuario canónica `GET /api/v1/membership/me`.
- Servicio independiente futuro; sin implementación en esta fase.
- Stack recomendado: el de osap-auth (FastAPI + MySQL + Alembic + pytest-asycnio + ruff + mypy), Python ≥3.12.

> No se inventan fechas ni decisiones anteriores a esta revisión.

---

## Restricción final de esta fase

Decisión FIJADA de proceso: esta fase es **documental**. No implementar fases 1–8 del plan de `osap-support`. No crear repo, BD, código, endpoints, pagos ni emails. No modificar Auth, Chorus ni osap-app. El objetivo es dejar **arquitectura + variantes + decisiones fijadas + decisiones abiertas + razones** para que las siguientes fases se ejecuten sin reinterpretar continuamente la arquitectura.

---

*Fin del registro de decisiones de OSAP Support. Sin cambios de código ni infraestructura.*
