# OSAP-API — Integración de autenticación (v1)

**Estado:** CONGELADO v1.
**Depende de:** `osap-auth/docs/osap-auth-api-v1.0.md`.

---

# 1. Principio: Authentication vs Authorization

- **osap-auth autentica** ("¿quién eres?").
- **osap-api autoriza** ("¿qué puede hacer aquí?").

osap-api valida la identidad del usuario cuando lo necesita y decide, según su propia lógica,
qué operaciones permite. Los claims del JWT describen **identidad**, no autorización.

---

# 2. Validación de la identidad del usuario

- osap-api valida el access token **localmente** contra el **JWKS** de osap-auth
  (`/auth/.well-known/jwks.json`), cacheado.
- Verifica: firma, `iss = osap-auth`, `aud = osap-api`, `exp`, tolerancia de *clock skew*.
- Claims utilizables: `sub` (user UUID), `jti`, `roles`, `email_verified`.
- Detalle del perfil (si se requiere mostrar email/nombre): `GET /auth/me` bajo demanda.
  El email **nunca** se lee del token.

## Ejemplo de claims

```json
{
  "iss": "https://auth.osap",
  "sub": "uuid-del-usuario",
  "aud": "osap-api",
  "jti": "uuid-de-la-sesion",
  "roles": ["user"],
  "email_verified": true,
  "exp": 1723000900
}
```

---

# 3. Regla de votación (diseñada aquí, implementada por osap-api)

## Modelo del voto

```text
user_id     = UUID (de osap-auth, vía sub)
work_id     = identificador de la obra
vote        = valoración del usuario
voted_at    = timestamp de la votación
vote_day    = fecha UTC del voto
```

### Propiedad de datos

- Los votos pertenecen a **osap-api** y viven en su **BD propia** (`osap_api`), no en Auth.
- osap-api guarda **solo el `user_id` opaco** (UUID) en `votes.user_id`. Nunca guarda email,
  contraseña, sesiones ni ningún dato de identidad.
- osap-api **no consulta la BD de osap-auth**; la identidad se resuelve vía el access token
  (JWT) y, en su caso, `GET /auth/me`.

## Restricción

```text
UNIQUE(user_id, vote_day, work_id)
```

## Regla funcional (congelada)

> **Un usuario puede emitir un voto por obra al día.** Puede valorar **varias obras** en el
> mismo día. `vote_day` se calcula en **UTC** para evitar doble voto por diferencia de zona
> horaria.

Queda **explícito**: la regla es **1 voto por obra y día**, no "1 voto al día en total".
Esto permite que un usuario valore varias obras cada día.

## Requisitos de identidad para votar

- `email_verified == true`.
- Rol `user` (o superior).
- La autorización (¿puede este usuario votar esta obra?) la decide **osap-api**.

## Ciclo de vida del voto

- `vote_day` se deriva de `voted_at` en UTC (la aplicación no debe confiar en la zona horaria
  del cliente).
- El agregado (valoraciones de obras y de compositores) se recalcula por proceso nocturno
  (fuera del alcance de este documento, pero el modelo lo soporta).

---

# 4. Operaciones autenticadas vs públicas

- **Públicas** (no requieren osap-auth disponible): búsqueda/lectura de obras, ficha, recursos.
  La disponibilidad de osap-auth **no** debe bloquear el tráfico de lectura.
- **Autenticadas**: votar, perfil, cualquier operación que requiera identidad.
- osap-api solo exige y valida identidad en los endpoints que la necesitan.

---

# 5. Service-to-service (osap-api → osap-storage)

- osap-api obtiene un **token de servicio** (OAuth2 `client_credentials`, scope `storage:read`)
  y lo usa para llamar a osap-storage.
- **Nunca** reenvía el access token del usuario a osap-storage.
- Los tokens de servicio son cortos y se obtienen bajo demanda.

---

# 6. Manejo del evento `user.deleted`

- osap-api se suscribe a `user.deleted` de osap-auth.
- Al recibir `{ user_id, deleted_at }`:
  1. **Anonimiza** los votos del `user_id`: se elimina la relación con la identidad del
     usuario pero **se conserva el dato estadístico** (agregado).
  2. Recalcula los agregados afectados.
- Justificación: las valoraciones alimentan las estadísticas de obras/compositores; el derecho
  al olvido se cumple eliminando la relación con la persona, no destruyendo el dato agregado.

---

# 7. Authorization interna (quién puede qué)

Las decisiones de autorización viven en osap-api:

| Acción | Requisito (decide osap-api) |
|--------|------------------------------|
| Votar | `email_verified` + rol `user` + regla 1/obra/día |
| Ver sus votos / perfil | `sub` == identidad de la sesión |
| Administración | rol `admin` |

---

# 8. Errores y códigos esperados

| Código | Significado |
|--------|-------------|
| 401 | Token ausente, inválido o caducado |
| 403 | Identidad válida pero sin autorización |
| 429 | Rate limit (aplica también en osap-api) |
| 409 | Voto duplicado (ya votó esta obra hoy) |

---
*Documento de integración de autenticación para osap-api (v1, 2026-08).*
