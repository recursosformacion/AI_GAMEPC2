# OSAP Support — Decisiones arquitectónicas (ADR) y registro de variantes

> **Registro consolidado de decisiones.** Fase documental. **Sin código, sin repo, sin BD, sin integraciones.**
> Fuentes: `support-architecture-separation.md`, `support-frontend-boundary-v1.md`,
> `support-ecosystem-architecture.md`, `osap-support-architecture.md`, `support-phase1-support-page.md`,
> + inspección de la implementación actual (`web/src/support`, `web/src/pages/SupportPage.tsx`, `web/src/state/auth.ts`).
> Fecha: 2026-08-29

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
- Recompensas por donación.
- Niveles definitivos de membresía (nombres/umbrales).
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
