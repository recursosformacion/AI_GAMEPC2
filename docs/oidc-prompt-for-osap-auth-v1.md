# PROMPT PARA OSAP-AUTH — Soportar el login OIDC de osap-api

Entregar este documento al agente de **osap-auth**. Es autocontenido; el lado osap-api ya
está implementado (RP OIDC con `client_id=osap-api`).

---

## Rol

Trabajas sobre **osap-auth** (NO tocas osap-api). Debes exponer/implementar lo necesario
para que osap-api actúe como *relying party* OIDC (Authorization Code + PKCE) con
`client_id=osap-api`. No añades reglas de negocio nuevas.

## Contexto en osap-api (lo que osap-api ya hace)

- `GET /api/v1/auth/oidc/start` → genera PKCE/state/nonce y devuelve la URL de `authorize`.
- `GET /auth/oidc/callback` → valida `state`, canjea el `code` en el token endpoint y
  redirige a la SPA con `access_token`+`refresh_token`.
- `JwtAuthenticator` valida localmente los **access tokens de usuario** (`sub`, `aud=osap-api`,
  `token_use=user`) contra `jwks_uri`.
- Los metadatos del proveedor (authorization/token/jwks) se **descubren** desde el issuer
  vía `/.well-known/openid-configuration` (osap-api NO fija URLs).

---

# 1. Discovery OIDC (obligatorio)

Exponer en el issuer:
```
GET {issuer}/.well-known/openid-configuration
```
con al menos: `issuer`, `authorization_endpoint`, `token_endpoint`, `jwks_uri`,
`response_types_supported` (`code`), `code_challenge_methods_supported` (`S256`),
`grant_types_supported` (incluye `authorization_code`, `refresh_token`),
`id_token_signing_alg_values_supported`, `scopes_supported`.

> Sin este endpoint no hay login OIDC: osap-api descubre desde aquí las URLs de authorize y token.

# 2. Registrar el cliente

```
client_id: osap-api
grant_types: [authorization_code, refresh_token]
response_types: [code]
token_endpoint_auth_method: client_secret_post
```

- **`redirect_uri` NO es fijo ni pertenece a una aplicación**: lo envía el cliente (osap-api)
  en **cada** petición de authorize, tomado de su configuración. osap-auth debe **aceptar el
  `redirect_uri` proporcionado por el cliente**, validando **al menos el dominio** contra los
  orígenes permitidos del cliente (y sin exigir una única URL hardcodeada). Así osap-auth no
  queda atado a una única aplicación.
- **PKCE obligatorio** (`S256`); `code` de un solo uso; `nonce` validado.
- El **secreto del cliente** vive fuera (env/secret manager de osap-auth); se entrega a osap-api
  por un canal seguro. Nunca en una BD en claro ni en respuestas.

# 3. Token endpoint

`POST {token_endpoint}` (Content-Type `application/x-www-form-urlencoded`):

- `grant_type=authorization_code`, `code`, `code_verifier`, `redirect_uri`, `client_id`,
  `client_secret`.
- Responder: `access_token`, `refresh_token`, `token_type=Bearer`, `expires_in`, `scope`.
- `grant_type=refresh_token` con **rotación** (el refresh anterior se consume).

# 4. Tokens de usuario (lo que osap-api valida)

Los **access tokens** deben ser JWT firmados, expuestos en `jwks_uri`, con:
- `iss` = issuer
- `sub` = user_id
- `aud` = `osap-api`
- `token_use` = `user`
- `roles`, `email_verified` (presentación en la UI; no autorización)

Mínimos scopes; no emitir roles/tier adicionales.

# 5. Confirmar (valores finales, con dualidad dev/prod)

- `issuer`: **prod** `https://auth.openmusicrepository.com`; **dev** el que corresponda
  (`http://127.0.0.1:8200` si hay auth local, o el remoto).
- **Prefijo en prod `/auth-api`**: cómo afecta a `authorization_endpoint`, `token_endpoint`
  y al discovery (`/.well-known/openid-configuration`).
- `redirect_uri` definitivo (osap-api lo tiene configurable por entorno).
- `client_secret` de `client_id=osap-api` (para que osap-api lo ponga en su entorno).

# 6. Fuera de alcance / lo que NO hace osap-auth

- No almacenar configuración de osap-api en su BD (eso es de osap-api).
- No tocar votos, works, compositores ni estadísticas.
- No exponer `client_secret` en claro ni en respuestas.
- No desplegar producción sin aprobación.

# 7. Validación

- Prueba manual: `GET {issuer}/.well-known/openid-configuration` devuelve los endpoints;
  `authorize` → login → `code` → canje en el token endpoint → access token con
  `sub`/`token_use=user`/`aud=osap-api`.
- Flujo con PKCE desde un RP de prueba.

---

*Prompt de integración para osap-auth v1 (2026-08).*
