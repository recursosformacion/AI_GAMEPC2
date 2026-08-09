# osap-api — Identity & Authorization Preparation v1

**Estado:** PREPARACIÓN. **No implementado.**
**Base:** `authentication-integration-v1.md` (contrato congelado) y código de
`src/osap/api/platform_app.py`, `src/osap/api/platform.py`,
`src/osap/application/votes_service.py`, `src/osap/infrastructure/auth/`.

---

# 1. Estado actual

## Autenticación

- La API es FastAPI (`platform_app.py`). Los endpoints reciben
  `authorization: str | None = Header(default=None)`.
- En V3.1, la mayoría de endpoints hacen `del authorization` (auth **preparada pero
  desactivada**).
- **Excepción:** el sistema de votos (v1) ya exige autenticación en
  `POST /api/v1/works/{work_id}/vote` (401 si no hay token) mediante un autenticador
  inyectable (`JwtAuthenticator` / `StaticTokenAuthenticator` en
  `infrastructure/auth/token_authenticator.py`).

## Concepto de Principal

- **No existe** todavía un concepto de `Principal`. No hay `AnonymousPrincipal`,
  `UserPrincipal` ni `ServicePrincipal`.
- La identidad de usuario se reduce a `user_id` (UUID) obtenido del token.
- La identidad de servicio (para llamar a storage) aún no está modelada en osap-api.

## Endpoints

Ver `src/osap/api/platform_app.py`. Clasificación en §3.

---

# 2. Concepto de Principal (a preparar, no implementar)

Propuesta para la fase de implementación:

```
Principal
  ├─ AnonymousPrincipal   (type=anonymous, user_id=None,  service_id=None)
  ├─ UserPrincipal        (type=user,      user_id=UUID,  service_id=None, roles=[...])
  └─ ServicePrincipal     (type=service,   user_id=None,  service_id=client_id, scopes=[...])
```

Uso posterior:
- Dependencia FastAPI que resuelve el `Principal` desde el `Authorization` header.
- Cada endpoint declara el principal/rol/scope permitido.
- osap-api decide autorización y, cuando delega en storage, usa `ServicePrincipal` para
  obtener un service token (nunca reenvía el access token del usuario).

No se implementa todavía.

---

# 3. Matriz de operaciones (osap-api)

| Operación (path) | Principal | Rol | user_id | Anónimo | Delega en storage | Archivo/línea |
|---|---|---|---|---|---|---|
| `GET /api/v1/search-model`, `/intent` | ANY | — | no | sí | no | platform_app |
| `POST /api/v1/searches`, `GET /searches/{id}` | ANY | — | no | sí | sí | platform_app |
| `GET /api/v1/representations/{id}/download` | ANY | — | no | sí | sí | platform_app |
| `GET /api/v1/providers*` | ANY | — | no | sí | no | platform_app |
| `GET /api/v1/repository-sources*` | ANY | — | no | sí | no | platform_app |
| `GET /api/v1/sources*`, `/discover/sources` | ANY | — | no | sí | no | platform_app |
| `GET /api/v1/knowledge/*` | ANY | — | no | sí | no | platform_app |
| `GET /api/v1/system/*` | ANY | — | no | sí | no | platform_app |
| `POST /api/v1/jobs*` | (pendiente) | — | no | sí* | no | platform_app |
| `POST /api/v1/works/{work_id}/vote` | USER | `user` + `email_verified` | **sí** | no | sí | platform_app |
| `GET /api/v1/works/{id}/statistics` | ANY | — | no | sí | sí | platform_app |
| `GET /api/v1/composers/{id}/statistics` | ANY | — | no | sí | sí | platform_app |
| `GET /api/v1/admin/votes` | USER(admin) | `admin` | sí | no | sí | platform_app |

\* `jobs` hoy es público en código; clasificación pendiente.

---

# 4. Votos

Flujo acordado (ver documento transversal):
1. El usuario se autentica contra osap-auth.
2. osap-api recibe el JWT y resuelve `user_id`.
3. osap-api autoriza (rol `user` + `email_verified`).
4. osap-api llama a storage con identidad SERVICE, enviando `user_id` como dato de negocio.
5. storage registra el voto (regla 1/día/obra en su BD).

Cambios futuros (no implementar):
- `POST /api/v1/works/{work_id}/vote` deberá obtener un **service token** y delegar la
  persistencia en storage (hoy `votes_service.cast_vote` delega en un `IVoteStore` que es
  `StorageVoteStore`, pero la autenticación administrativa y el service token aún no están
  cableados de extremo a extremo).
- No mantener BD de votos propia.

---

# 5. Administración

- `GET /api/v1/admin/votes` debe exigir `role=admin`. Hoy solo exige autenticación
  (contradicción C3 del transversal).
- La autorización administrativa usará el sistema de autorización existente (claim `roles`);
  no se crea un sistema de roles nuevo.

---

# 6. Llamadas a Storage

- osap-api → osap-storage se hará con service token (`storage:read`; futuro `storage:write`
  para votos, `storage:admin` para admin).
- osap-api **nunca** reenvía el access token del usuario a storage.
- Hoy, `StorageWorkStore` y `StorageVoteStore` llaman a storage sin service token (a definir
  en la fase de implementación).

---

# 7. Cuestiones pendientes de osap-api

1. Introducir `Principal` (Anonymous/User/Service).
2. Cablear rol `admin` en `/api/v1/admin/votes`.
3. Obtener service token para llamar a storage.
4. Clasificar `/api/v1/jobs*`.
5. Confiar en `token_use` para distinguir user/service cuando osap-auth lo emita.

---

# 8. Cambios futuros necesarios

- Implementar `Principal` + dependencia FastAPI.
- Autorización por endpoint (votar, admin).
- Delegación de votos a storage con service token.
- Retirar la persistencia de votos propia si existe.

---

*Documento de preparación de identidad/autorización de osap-api v1 (2026-08) — no implementado.*
