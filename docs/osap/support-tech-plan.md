# OSAP — Plan técnico de implementación (apoyo común osap-app + Chorus)

> **Estado:** plan. No se implementa código en esta entrega (regla §15).
> Referencias: `docs/osap/support-ecosystem-architecture.md` (arquitectura), `docs/osap/support-phase1-support-page.md` (Fase 1), `docs/osap/support-membership-architecture.md` (análisis previo).
> Fecha: 2026-08-28.

---

## 1. Revisión de conclusiones anteriores (y señalamientos)

### Lo ya resuelto y en marcha
- **Identidad común** = `JWT.sub` de Auth. No hay usuarios propios en osap-app/Chorus. ✅ (sin cambiar)
- **Arquitectura recomendada** = servicio independiente **osap-membership** + perfil público desacoplado. ✅ (referencia)
- **Página `/support` ya implementada** (Fase 1, en `web/` de osap-api): ruta, nav, footer, i18n 5 idiomas, CTA con login vía Auth, estado autenticado. **Esto es la mayor parte del MVP.**
- **Retorno desde Auth**: el login es **popup + postMessage**; la página de origen (`/support`) no se pierde (§6).

### Contradicciones / puntos sin resolver
1. **Qué es "Chorus" vs "osap-app" en el repo.** Hoy ambas viven en la SPA `web/` de osap-api (el mismo `osap-app`). "Chorus" como aplicación separada (consumidora de OSAP, ADR-0001) **todavía no es un repo/frontend independiente**. → El MVP se hace en la SPA actual (`web/`), que sirve a osap-app y, al ser una sola, también cubre Chorus. **Decisión pendiente de ti** (ver §9).
2. **Agente/existencia de `/me` en osap-api.** No existe endpoint `/api/v1/me`; el estado autenticado es **solo cliente** (`useAuth`) leyendo `sub` del token. Suficiente para el MVP, pero hay que decidir si el backend necesita `/me` (recomiendo: solo si osap-app quiere mostrar nombre/email desde servidor; para el MVP no).
3. **Nivel naming / "osap-app" aparece en el footer como `app.name = OpenMusicRepository`.** No bloquea el MVP.

### Decisiones que requieren intervención humana (NO arbitrarias)
- **(D1)** ¿El MVP se despliega en la SPA actual de osap-api (`osap-app`), asumiendo que sirve también a Chorus? (Recomendado: sí, porque hoy Chorus es la misma SPA.)
- **(D2)** ¿Creamos `osap-membership` como repo/servicio desde ya (fase 4) o dejamos solo la abstracción (interfaz) en esta fase? (Recomendado: solo abstracción ahora.)
- **(D3)** ¿El "login" de `/support` usa OIDC popup (actual) o un redirect de página completa? (Recomendado: popup actual, evita perder estado.)
- **(D4)** Nivel de nombres y "Miembro fundador": se deciden en Fase de Membership, no ahora.

---

## 2. MVP real (definición)

**Objetivo del MVP** (escenario mínimo viable, sin pago):

```
Persona entra en Chorus/osap-app
   ↓  conoce el proyecto
   ↓  "Apoya OSAP"
   ↓  (si no tiene cuenta) Auth: registro/login
   ↓  vuelve identificada (sub)
   ↓  ve un estado "preparado para apoyar" (sin pago real)
```

**Criterio de aceptación del MVP**
1. La página de apoyo es accesible pública (`/support`) y explica el proyecto.
2. Un usuario no autenticado puede iniciar **registro/login mediante el flujo Auth existente** desde esa página.
3. Tras identificarse, **permanece en `/support`** (no pierde la página), y la UI cambia a estado autenticado.
4. En estado autenticado, aparece un CTA "Empezar a apoyar" que **no simula pago** (mensaje informativo / preparado).
5. Coherente desde osap-app y Chorus (misma página).
6. **Sin** pagos, webhooks, proveedores, niveles, comunidad pública, perfiles, red social.

El MVP **ya está en gran parte implementado** (Fase 1). Este plan define qué falta para cerrarlo y añade la **abstracción** necesaria.

---

## 3. Qué implementar AHORA (lista concreta)

### Frontend (web/ de osap-api) — casi todo ya hecho en Fase 1
| Componente | Estado | Acción |
|---|---|---|
| `web/src/pages/SupportPage.tsx` | ✅ hecho | Verificar estados autenticado/no autenticado y CTA |
| Ruta `/support` (`routes.tsx`) | ✅ hecho | — |
| Nav + footer (`Layout.tsx`) | ✅ hecho | — |
| i18n `support.*` + `nav.support` (5 idiomas) | ✅ hecho | — |
| Login OIDC + fallback (reutiliza `useOidcLogin`/`useAuth`) | ✅ hecho | — |
| **Abstracción de apoyo (fronter)** | ❌ pendiente | Interfaz conceptual `SupportGateway` (ver §7) |

### Backend
- **Sin cambios obligatorios** para el MVP. Solo si se acepta (D2-bis) exponer `/api/v1/me` opcional. Recomiendo **no** tocar backend en esta fase.

### Base de datos
- **Sin cambios.** No crear `user_memberships` ni `user_public_profiles` (pendiente de Membership). **No crear tablas solo por previsión.**

### Auth
- **Sin cambios.** Se reutiliza todo lo existente (OIDC, `useAuth`, `AuthClient`).

---

## 4. Qué NO implementar todavía (lista explícita)

- Pagos / checkouts / webhooks.
- Ningún proveedor (Stripe, Patreon, Ko-fi, Gumroad, GitHub Sponsors, etc.).
- Tablas `memberships` / `public_profiles` en BD.
- Niveles económicos / "Miembro fundador" (decidir importes/criterios).
- Miembros públicos / listado de colaboradores.
- Perfiles sociales, avatares, biografías.
- Opiniones, seguidores, notificaciones, feed, mensajería, red social.
- Endpoints `/membership/*` y `/community/*` reales (solo documentados).
- Modificar Auth ni funcionalidades musicales.

---

## 5. Diseño del primer flujo de usuario

### Usuario no autenticado
- **Ve:** página `/support` pública (qué es OSAP, qué construimos, por qué apoyo, en qué se usa, qué significa, qué pasa después).
- **Pulsa:** "Iniciar sesión / crear cuenta" (`support.loginCta`).
- **Se redirige a:** flujo Auth existente — abrir el **popup OIDC** (`/api/v1/auth/oidc/start`); si OIDC no está configurado, cae al modal login/registro email-password.
- **Vuelve a Chorus/osap-app:** el popup cierra con `postMessage`; la ventana de `/support` recibe `completeOidc` y el usuario **se queda en `/support`** (sin perder ruta ni estado).

### Usuario autenticado
- **Ve:** `/support` con el estado autenticado (`user != null`, identificado por `sub`).
- **Puede:** pulsar "Empezar a apoyar Chorus/OSAP" (`support.startCta`).
- **Preparación Membership:** el botón, por ahora, muestra un mensaje informativo (nada simulado). La página deja claro que el apoyo se conectará en el futuro; la UI queda lista para que `SupportPage` llame a la futura API `membership`.

### Coherencia osap-app ↔ Chorus
- La misma página `/support` se sirve desde la SPA para ambos (hoy son la misma app). Si en el futuro Chorus es un frontend separado, reutiliza la **misma abstracción** y contrato de API.

---

## 6. Retorno desde Auth (análisis concreto)

**Mecanismo actual (verificado en código):**
- `useOidcLogin.start()` → `GET /api/v1/auth/oidc/start` → URL de authorize de osap-auth (PKCE S256, `scope=openid profile`) → abre **popup**.
- osap-auth redirige a `GET /auth/oidc/callback?code&state` (backend osap-api valida state, canjea code, PKCE) → redirige SPA a `spa_origin/oidc/callback#access_token&refresh_token` (**fragmento**).
- `AuthCallbackPage` lee el `#`, hace `postMessage` a `window.opener` y cierra; la página de origen (`/support`) recibe `osap-oidc` con tokens.

**Por qué es seguro y no pierde estado:**
- **No hay redirect de la página completa** → no se pierde la ruta `/support`.
- **No hay URL manipulable**: el `redirect_uri` del cliente está registrado en osap-auth; los tokens viajan en el **fragmento** (`#`), no en la query (no quedan en logs/historial/referrer).
- **No se crean sesiones duplicadas**: `completeOidc` guarda refresh en `localStorage` y access en memoria única (`useAuth`).
- Si se accede al callback sin opener → fallback a `/` (comportamiento ya existente, documentado).

**Conclusión:** usar el mecanismo actual; **no** redirigir la página completa para no perder el origen. (D3: recomiendo el popup.)

---

## 7. Abstracción común de apoyo (interfaz)

Aunque no exista el proveedor, definimos la **frontera** para que Chorus y osap-app no conozcan detalles futuros:

```
Chorus / osap-app  (UI)
   ↓  usa una interfaz
SupportGateway  (interfaz/Tipo TS; no depende de proveedor)
   ↓  (futuro)
MembershipClient  (llama a la API de osap-membership)
   ↓
proveedor de pagos (detrás de osap-membership)
```

**Diseño mínimo (Frontend, por ahora solo tipos/interfaz):**
```ts
// web/src/state/support.ts (o api/SupportGateway.ts)
export interface SupportSummary {
  status: "none" | "preparing";   // el MVP solo sabe "sin apoyo" / "preparado"
  authenticated: boolean;
  subscriberId?: string;           // = sub
}

export interface SupportGateway {
  getSummary(): Promise<SupportSummary>;          // MVP: local
  // future: checkout(): Promise<CheckoutUrl>;    // cuando exista Membership
  // future: setPublicProfile(...);               // fase comunidad
}
```

**Regla:** la UI de `/support` se escribe **contra la interfaz**, no contra el proveedor. En el MVP, `getSummary()` devuelve lo que ya conocemos del cliente (`useAuth`). Cuando exista osap-membership, se añade un `MembershipClient` sin tocar la página.

**¿Necesaria esta fase?** Sí, ligera: es la garantía de que no reharemos cuando llegue Membership/Social (principio). Es solo un par de tipos + un hook; no introduce dependencias ni backend.

---

## 8. Contenido funcional de la página de apoyo (v1)

La página `/support` **ya existe** y cubre este contenido. Se mantiene / ajusta:

1. **Qué es OSAP** → plataforma abierta de música y conocimiento musical.
2. **Qué estamos construyendo** → el ecosistema (osap-app + Chorus) y por qué.
3. **Por qué necesitamos apoyo** → infraestructura, servidores, desarrollo, mantenimiento, investigación, tiempo.
4. **Para qué se utilizará** → continuidad y evolución; recursos a mantenerlo abierto.
5. **Qué significa apoyar el proyecto** → apoyar la continuidad, **no** "pagar para desbloquear".
6. **Qué ocurrirá después** → iniciar sesión una vez; en el futuro elegir cómo contribuir.

**Reglas:** **no** inventar beneficios inexistentes; **no** mostrar niveles de apoyo (no definidos); no agresivo comercial.

---

## 9. Integración con Chorus (archivos a tocar)

Dado que hoy **osap-app y Chorus son la misma SPA** (`web/`), la integración es única. Archivos implicados:

| Archivo | Cambio |
|---|---|
| `web/src/pages/SupportPage.tsx` | Ajustar para usar `SupportGateway` (abstracción); verificar estados |
| `web/src/state/support.ts` (nuevo) | Interfaz `SupportGateway` + implementación MVP local |
| `web/src/routing/routes.tsx` | ya tiene `/support` (sin cambio) |
| `web/src/layouts/Layout.tsx` | ya tiene nav+footer (sin cambio) |
| `web/src/i18n/translations.ts` | ya tiene claves (sin cambio) |
| `web/src/components/useOidcLogin.ts` | reutilizado (sin cambio) |
| `web/src/state/auth.ts` | reutilizado (sin cambio) |

**No** se tocan funcionalidades musicales no relacionadas.

---

## 10. Integración con osap-app

- Misma página `/support` + misma abstracción `SupportGateway`.
- CTA coherente "Apoya OSAP" en ambas (hoy único frontend).
- **Sin duplicar lógica de Membership** (se centraliza en `SupportGateway` → futuro `MembershipClient`).

---

## 11. Modelo de API (mínimo, propuesto — no implementar)

Pendiente de osap-membership (fase 4), se documenta el contrato para que funcione aún en otra máquina:

| Endpoint | Consume | Provee | Auth | Devuelve |
|---|---|---|---|---|
| `GET /support` | navegador | frontend (osap-app/Chorus) | pública | contenido |
| `POST /auth/oidc/start` | SPA | osap-api → osap-auth | pública | authorize_url |
| `GET /me` (opcional) | apps | osap-api | user token | sub, name, email, roles |
| `GET /membership/me` | apps | osap-membership | user token | status, level, fechas |
| `POST /membership/checkout` | apps | osap-membership | user token | url + return_url |
| `POST /membership/webhook` | proveedor | osap-membership | firma proveedor | actualiza estado |
| `GET /community/members` | apps | osap-membership | pública/service | perfil público solo consentido |

- **Formato:** JSON + envelope de error uniforme (consistente con osap-api: `{ data }` / `{ code, message }`).
- **Errores:** `401` (token), `403` (sin permiso), `404`, `409` (conflicto), `502` (proveedor), `503`.
- **Versionado:** `/api/v1/...`.
- **Portabilidad:** la API de membership es alcanzable por URL de entorno; las apps solo cambian la URL, no la lógica.

---

## 12. Modelo de despliegue

**Ahora (una máquina):**
```
Servidor actual
├── Auth      (osap-auth)
├── osap-app  (osap-api web/dist + backend osap-api + osap-storage)
└── Chorus    (hoy la misma SPA; ver D1)
```

**Posterior (dos máquinas sin cambiar las apps):**
```
Servidor A
├── Auth, osap-app, Chorus

Servidor B
├── osap-membership
└── Social (futuro)
```

**Garantías:** `osap-membership` se diseña como servicio con BD/API/entorno propios; las apps consumen por URL de entorno (portabilidad). **No** hay que separar físicamente nada en esta fase.

---

## 13. Documentación

Se crea/actualiza:
- **`docs/osap/support-tech-plan.md`** (este documento): plan, MVP, flujo, API, despliegue, riesgos, decisiones.
- Referencias ya existentes: `support-ecosystem-architecture.md`, `support-phase1-support-page.md`, `support-membership-architecture.md`.
- La doc debe permitir a otro desarrollador: entender identidad (`sub`), flujo de login (popup/postMessage), la abstracción `SupportGateway`, y dónde vivirá Membership.

---

## 14. Plan de ejecución (tareas pequeñas)

### Tarea 1 — Abstracción `SupportGateway` (Frontend)
- **Archivos:** `web/src/state/support.ts` (nuevo), `web/src/pages/SupportPage.tsx`.
- **Cambios:** interfaz + hook que expone `getSummary()` leyendo `useAuth` (authenticated + sub).
- **Dependencias:** ninguna; `useAuth` ya existe.
- **Riesgo:** bajo.
- **Criterio:** `SupportPage` usa `SupportGateway` (no `useAuth` directo) y tsc pasa.

### Tarea 2 — Página `/support` (ya hecha; verificación)
- **Archivos:** `SupportPage.tsx` (ajustes), i18n.
- **Cambios:** asegurar estados autenticado/no autenticado y CTA sin simular pago.
- **Dependencias:** Tarea 1.
- **Riesgo:** bajo.
- **Criterio:** `/support` responde y muestra ambos estados; build OK.

### Tarea 3 — Integración Auth (verificar retorno)
- **Archivos:** reutiliza `useOidcLogin`/`useAuth`; test de flujo.
- **Cambios:** verificar que tras login en `/support` no se pierde la página (ya es así).
- **Dependencias:** Tarea 2.
- **Riesgo:** bajo.
- **Criterio:** login desde `/support` → vuelve a `/support` identificado.

### Tarea 4 — Estados autenticado/no autenticado (UI)
- **Archivos:** `SupportPage.tsx`, `state/support.ts`.
- **Cambios:** render condicional de CTA (login vs "empezar a apoyar").
- **Dependencias:** Tarea 1/2.
- **Riesgo:** bajo.
- **Criterio:** ambos estados visuales correctos (test de componente).

### Tarea 5 — Preparación Membership (interfaz, sin pago)
- **Archivos:** `state/support.ts` (ampliar tipos), docs.
- **Cambios:** definir firmas `checkout()`/`publicProfile()` como futuras; no implementar.
- **Dependencias:** Tarea 1.
- **Riesgo:** bajo.
- **Criterio:** doc actualizada; sin backend/BD/API nuevos.

### Tarea 6 (futura, NO ahora) — osap-membership real
- Creación del servicio, proveedor de pagos, webhooks, tablas, endpoints. **Fuera del MVP.**

**Orden de ejecución sugerido:** Tarea 1 → 2 → 3 → 4 → 5. (Si Tarea 1 se considera excesiva para el MVP, se puede hacer solo Tareas 2-4 y el `SupportGateway` más tarde; matiz en §15.)

---

## 15. Regla de trabajo — entregables antes de implementar

1. **MVP definido** ✅ (se ha acotado y ya casi completo).
2. **Arquitectura técnica** ✅ (ver `support-ecosystem-architecture.md` y este plan).
3. **Flujo de usuario** ✅ (§5 de este plan).
4. **Archivos a modificar** ✅ (§9, §10, Tarea 1-5).
5. **Modelo de API** ✅ (§11).
6. **Modelo de datos necesario:** ninguno en esta fase (no crear tablas).
7. **Plan de ejecución** ✅ (§14).
8. **Riesgos** ↓.
9. **Decisiones que necesito aprobar** ↓.

### Riesgos
| Riesgo | Mitigación |
|---|---|
| Crear tablas prematuramente | No crear BD en esta fase |
| Simular pagos / prometer beneficios | Prohibido en el MVP (mensaje informativo) |
| Duplicar identidad al llegar Social | Solo `sub`; `SupportGateway` desacoplado |
| Perder la página al login | Usar el popup/postMessage actual |
| Ampliar alcance | Lista explícita de "NO implementar" (§4); no añadir endpoints/BD |
| Fallo del agente auto-expandindo | Gate: cada tarea tiene criterio de finalización y depende de aprobación |

### Decisiones que necesito aprobar
- **D1** — ¿El MVP se implementa en la SPA actual de osap-api (`osap-app`), cubriendo también a Chorus? *(Recomendado: sí.)*
- **D2** — ¿Creamos la abstracción `SupportGateway` ahora (ligera) o la dejamos para cuando exista Membership? *(Recomendado: ligera ahora.)*
- **D3** — ¿Login por popup OIDC (recomendado) o redirección de página completa? *(Recomendado: popup.)*
- **D4** — Niveles / "Miembro fundador": se deciden en Fase de Membership (no ahora).

---

*Fin del plan técnico. Sin implementar código en esta entrega.*
