# Chorus — Fase 1 · Apoyo a Chorus y preparación de comunidad

> Referencia arquitectónica: `docs/osap/support-membership-architecture.md`
> Documento de esta fase: decisiones tomadas, página `/support`, evolución de `/discover`.

---

## 1. Qué se ha implementado en esta fase (Fase 1)

### 1.1 Página pública `/support`
- Nueva ruta `/support` en `web/src/routing/routes.tsx`.
- Nuevo componente `web/src/pages/SupportPage.tsx`:
  - Explica qué es Chorus, por qué necesita apoyo (infra, servidores, desarrollo, mantenimiento, investigación, tiempo) y qué significa apoyar (apoyar la **continuidad**, no "pagar para desbloquear contenido").
  - CTA **"Iniciar sesión / crear cuenta"** para usuarios no autenticados → reutiliza el flujo de identidad existente de Auth (OIDC popup + respaldo email/contraseña).
  - CTA **"Empezar a apoyar Chorus"** para usuarios autenticados → pantalla informativa, **sin simular pagos**.
- Enlace en la navegación principal (`MAIN_NAV` en `Layout.tsx`) y en el pie de página.

### 1.2 Internacionalización
- Nuevas claves `support.*` y `nav.support` en los **5 idiomas** (`en`, `es`, `ca`, `fr`, `de`) de `web/src/i18n/translations.ts`.
- Todos los textos se muestran vía `t()`; no hay cadenas sueltas en el componente.

### 1.3 Identidad
- **No se crea ningún sistema de usuarios.** El usuario autenticado sigue identificándose por **`JWT.sub`** (UUID de Auth), leído únicamente desde la sesión existente (`useAuth`).
- No se modificó Auth (osap-auth) ni su arquitectura.

### 1.4 Backend / BD
- **Sin cambios** en esta fase. No se crean tablas `user_memberships` ni `user_public_profiles` todavía (ver §2).

---

## 2. Decisiones de modelo de datos

Aunque el documento de arquitectura propusiera `user_memberships` y `user_public_profiles`, **se decide NO crearlas en esta fase**. Motivos:

1. **`user_memberships`** es una *cache* del estado de pago cuyo pleno sentido existe solo cuando haya un proveedor de Membership con webhooks/eventos. Crearla ahora sería una tabla muerta sin fuentes de datos, que habría que migrar al elegir proveedor. La **fuente de verdad del pago es el proveedor**, no Chorus.
2. **`user_public_profiles`** (consentimiento + nombre público) solo cobra sentido cuando exista pertenencia que publicar. Aunque es más ligera, se prefiere esperar para no adelantar complejidad y para que la UI de consentimiento se construya junto a la primera pertenencia real.

**Contrato de diseño (para cuando se creen):**
```
user_memberships          -- caché derivada del proveedor de pagos
  subscriber_id UUID PK     (= sub / Auth user.id)
  membership_status enum(pending, active, past_due, cancelled, expired, none)
  membership_level enum(founder, patron, supporter, contributor)   -- definido al elegir niveles
  started_at / renewed_at / expires_at / updated_at datetime
  provider str

user_public_profiles       -- consentimiento + perfil público
  subscriber_id UUID PK
  visibility enum(anonymous, public_name, custom_name)   -- DEFAULT anonymous (opt-in)
  public_name str | null
  public_bio str | null
```
Se creará una **migración** en su momento. En Chorus la BD se gestiona por Python en `src/osap/infrastructure/state/op_store.py` (o módulo nuevo de pertenencia).

**Reglas de privacidad (aplicables desde el diseño):**
- Default `anonymous`. Publicar es **opt-in** explícito.
- Nunca se publican: cantidad, método de pago, datos bancarios, email, historial de pagos.
- El perfil público se oculta automáticamente si la pertenencia deja de estar activa.

---

## 3. Evolución de "Descubrir" (`/discover`)

**Situación actual:** `/discover` muestra proveedores NO conectados (candidatos a fuente) y duplica parcialmente `/catalog` (Fuentes).

**Decisión de esta fase:** **NO se transforma todavía** para no romper `/catalog` ni funcionalidad existente. Se documenta la hoja de ruta.

**Hoja de ruta (posterior a Membership):**
1. Trasladar el listado de "proveedores a conectar" a `/catalog` (o archivarlo), dejando `/discover` libre.
2. Transformar `/discover` en **"Personas que hacen posible Chorus"**:
   - Tarjeta por colaborador público (solo `visibility != anonymous`): nombre público, nivel/badge, bio opcional, enlace a perfil futuro.
   - Nunca datos económicos ni de pago.
   - Orden por antigüedad de apoyo (fundadores primero), no por importe.
3. Fuente de datos: tabla `user_public_profiles` (+ nivel de `user_memberships`). Neutral y consumible por Social.

---

## 4. Arquitectura preparada (Auth → Chorus → Membership → Comunidad → Social)

```
AUTH  (identidad)  ── sub (UUID) ──▶  CHORUS  ──▶  MEMBERSHIP (pagos) ── webhook ─▶  Chorus cache
   ▲                                      │                                        │
   └────────────────── JWT / OIDC ◀────────┘            public consent ──▶  "Descubrir"
                                             (futuro)           Social (perfiles, interacción)
```

- **Auth**: identidad, registro/login/sesión, roles. Fuente de `sub`. **No se toca.**
- **Chorus**: música + explica el proyecto + (futuro) estado de pertenencia + comunidad pública opt-in.
- **Membership (proveedor de pagos)**: fuente de verdad del pago. Aún no elegido. La interfaz está preparada (página `/support`) pero no integrada.
- **Social (futuro)**: reutilizará `sub` y el perfil público; Chorus no es la red social.
- **Identificador común**: `sub` (UUID). Nunca se crean usuarios paralelos.

---

## 5. Portabilidad

- No se introdujo ninguna dependencia ni infraestructura propietaria (ni Vercel, ni Docker "por introducir").
- Los cambios son: un componente React, una ruta, enlaces de navegación y claves i18n. Sin dependencias nuevas.
- La futura integración de Membership se resolverá con variables de entorno / configuración externa y migraciones documentadas.

---

## 6. Entregables de esta fase

| Entregable | Estado |
|---|---|
| Página pública `/support` funcionando y traducida | ✅ |
| Integración Auth (login/registro no autenticado) | ✅ (reutiliza flujo existente) |
| Usuario autenticado reconocido por `JWT.sub` | ✅ (sin crear otro usuario) |
| Arquitectura preparada documentada | ✅ (§4 de este doc + `support-membership-architecture.md`) |
| Propuesta de modelo de datos (qué ahora / qué esperar) | ✅ (§2) |
| Propuesta de evolución de `/discover` | ✅ (§3) |
| Documentación | ✅ (este doc) |

---

*Fin de la Fase 1.*
