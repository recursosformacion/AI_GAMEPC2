# osap-api — Prompt de implementación: identidad y autorización (v1)

**Estado:** PROMPT DE IMPLEMENTACIÓN (preparación). Al implementarlo, sigue el contrato
congelado `authentication-integration-v1.md` y el documento transversal
`_docs/identity-and-authorization-v1.md`. No modifica osap-auth ni osap-storage.

---

## Rol

Ingeniero sobre osap-api. Implementa el modelo de identidad y autorización en osap-api
según las decisiones transversales congeladas, manteniendo la frontera limpia:
osap-api **autoriza**; osap-auth **autentica**; osap-storage recibe solo llamadas de
servicio.

---

## Estado actual (osap-api)

- FastAPI (`src/osap/api/platform_app.py`). La mayoría de endpoints reciben
  `authorization: str | None = Header(default=None)` y hacen `del authorization` (auth
  preparada pero **sin enforcement**).
- El voto (`POST /api/v1/works/{work_id}/vote`) ya exige autenticación (401 si no hay token)
  mediante un autenticador inyectable (`JwtAuthenticator`/`StaticTokenAuthenticator` en
  `src/osap/infrastructure/auth/token_authenticator.py`).
- `votes_service.cast_vote` resuelve `user_id`, valida escala, resuelve `composer_id` vía
  `IWorkStore` y delega la persistencia en `IVoteStore` (`StorageVoteStore`).
- **No existe** un concepto de `Principal`.
- `GET /api/v1/admin/votes` solo exige autenticación, no rol `admin`.
- `POST /api/v1/jobs*` hoy es público.

---

## Antes de implementar (inspección)

**Inspecciona el flujo actual completo antes de modificar código:**

- `JwtAuthenticator` / `StaticTokenAuthenticator`;
- resolución de claims;
- dependencias FastAPI relacionadas con autenticación;
- `StorageWorkStore` / `StorageVoteStore` / `IVoteStore`;
- persistencia local de votos (debe comprobarse que no queda ninguna);
- cliente HTTP hacia osap-storage;
- configuración de service clients/scopes.

Si el estado real difiere del "Estado actual" descrito en este prompt, **no inventes una
solución ni modifiques silenciosamente la arquitectura**: indica primero la discrepancia y
adapta únicamente lo necesario para cumplir las decisiones congeladas. El prompt describe
código existente; no asumas que la descripción sigue siendo exacta.

---

## Objetivo

Introducir en osap-api:

1. `AnonymousPrincipal` / `UserPrincipal` / `ServicePrincipal`.
2. Resolución del principal desde el token usando `token_use` (con compatibilidad temporal).
3. Autorización explícita por operación.
4. `role=admin` real en `/api/v1/admin/votes`.
5. `email_verified` exigido para votar.
6. Distinción `tier ≠ role`, **sin** introducir `tier` como claim.
7. Usar **identidad de servicio** para llamar a osap-storage, obteniendo y gestionando el
   service token mediante `client_credentials`, con **scopes mínimos** según la operación.
8. `user_id` como **dato de negocio** al registrar el voto.
9. Eliminar cualquier persistencia local de votos.
10. Dejar `/api/v1/jobs*` **fuera** hasta decidir su clasificación.

---

## Principios

- **osap-auth autentica; osap-api autoriza.** osap-api responde "¿puedes realizar esta
  operación?".
- `user_id` (UUID opaco) es la única identidad de usuario.
- Distinguir USER vs SERVICE por **`token_use`**, no por heurísticas.
- `type=user` no cambia con `tier`/`role`. **`tier` no forma parte del Principal operativo ni
  de la autorización en esta fase.**
- osap-api **nunca** reenvía el access token del usuario a storage.
- El `user_id` enviado a storage es un **dato de negocio**, nunca una identidad técnica.

---

## 1. Principal

Introducir un concepto de `Principal` con tres formas:

```text
AnonymousPrincipal   type = anonymous,  user_id = null,  service_id = null
UserPrincipal        type = user,       user_id = UUID,  service_id = null,  roles = [...],  email_verified = bool
ServicePrincipal     type = service,    user_id = null,  service_id = client_id,  scopes = [...]
```

- El `UserPrincipal` expone `user_id`, `roles` y `email_verified`. **No** expone `tier`.
- No hay un cuarto "tipo" para tier/rol: `free`, `moderator`, `admin` no son tipos de
  principal.

## 2. Resolución del principal (autenticación)

- Leer `Authorization: Bearer <token>`.
- Validar firma/JWKS, `iss`, `aud`, `exp` (validación local, sin llamar a osap-auth por
  petición; detalles según `authentication-integration-v1.md`).
- Determinar el tipo por **`token_use`**:
  - `token_use == "user"` → `UserPrincipal` (`sub` → `user_id`, `roles`, `email_verified`).
  - `token_use == "service"` → `ServicePrincipal` (`sub`/`client_id` → `service_id`, `scope`).
- **Compatibilidad temporal (crítico):** la resolución de tokens **sin `token_use`** debe
  respetar **exactamente** la compatibilidad implementada en osap-auth. **No** se infiere
  user/service mediante nuevas heurísticas (ni presencia/ausencia de `roles`, `client_id`,
  `typ`, etc.). Si el mecanismo legado de osap-auth conserva `typ` u otro claim, se usa
  **únicamente conforme al contrato de transición de osap-auth**.
- **No duplicar ni reinterpretar la lógica de compatibilidad en osap-api.** Se reutiliza el
  mecanismo/contrato de autenticación existente en osap-api y se ajusta solo para reflejar la
  semántica ya implementada en osap-auth. No introducir una nueva función heurística basada en
  `roles`, `client_id`, `sub` o `typ`. Si el código actual usa `typ` como fallback durante la
  transición, ese fallback debe quedar **claramente aislado y documentado como compatibilidad
  temporal** — nunca como lógica normal de resolución.
- **Un token antiguo de servicio nunca debe interpretarse como usuario** por accidente: la
  compatibilidad se aplica solo al caso definido por osap-auth, no a adivinanzas.

## 3. Autorización por operación

- Un endpoint declara qué principal(es) admite.
- Resolver el `Principal` en una dependencia FastAPI.
- Si el endpoint exige usuario y el principal es anónimo/servicio → **401** o **403** según
  el caso (definir: ausencia de identidad → 401; identidad de tipo incorrecto → 403).

## 4. `role=admin` en `/api/v1/admin/votes`

- Exigir `UserPrincipal` con `"admin"` en `roles`.
- Sin rol `admin` → **403**. Sin token / anónimo → **401**.
- No basta con un `user_id` presente: se comprueba el rol.

## 5. `email_verified` para votar

- `POST /api/v1/works/{work_id}/vote` exige:
  - `UserPrincipal`;
  - `email_verified == true`;
  - rol `user` presente.
- Si no se cumple → **403** (regla definida por osap-api).

## 6. `tier ≠ role` (sin claim de tier)

- **En esta fase, `tier` no forma parte del Principal operativo ni de la autorización de
  osap-api.** No se consulta, no se resuelve y no se persiste como parte del flujo de
  autenticación. El concepto `tier` queda documentado únicamente para una fase posterior.
- **Los `roles` sí son necesarios ahora** (admin debe funcionar): viajan en el claim `roles`
  del token y se usan para autorizar.
- La administración depende **solo** de `role=admin`, nunca del `tier`.

## 7. Usar identidad de servicio para llamar a osap-storage (least privilege)

- Crear un **cliente de servicio** que obtenga y gestione el service token de osap-auth
  (`client_credentials` → `SERVICE JWT`) y lo use para llamar a osap-storage.
- **Precondición:** osap-auth ya admite y emite `storage:write` y `storage:admin` según su
  configuración de `service_clients`. osap-api **no** modifica esa configuración desde este
  prompt (no tocar osap-auth).
- **Scopes mínimos según la operación:**
  - `storage:read` → lecturas normales de storage;
  - `storage:write` → escritura de votos / operaciones de escritura previstas;
  - `storage:admin` → **solamente** las llamadas administrativas que osap-api realice sobre
    endpoints administrativos de storage.
  - No se otorga `storage:admin` al cliente de servicio de osap-api por el simple hecho de que
    el scope exista.
- **Scopes por llamada (no un único token para todo):** el service token debe solicitar
  únicamente los scopes necesarios para la operación.
  - lectura → `scope=storage:read`;
  - voto → `scope=storage:write`;
  - operación administrativa → `scope=storage:admin`.
  - El cliente de servicio puede tener varios scopes permitidos por configuración, pero **cada
    token/llamada utiliza únicamente los scopes necesarios** para esa operación. No crear un
    único token permanente con `storage:read storage:write storage:admin` reutilizado para todo.
- **Si osap-api no realiza actualmente ninguna llamada administrativa a osap-storage, no
  configurar ni solicitar `storage:admin` en esta fase** (existencia del scope ≠ necesidad de
  concedérselo a osap-api).
- **Reglas de seguridad (blindan la distinción):**
  - Nunca se reenvía el access token del usuario a storage.
  - Nunca se usa `user_id` como sustituto del token de servicio.
  - Nunca se crea un `ServicePrincipal` a partir de un `UserPrincipal`.
  - El `user_id` viaja únicamente como **dato de negocio** cuando una operación lo necesita.

## 8. `user_id` como dato de negocio (voto)

- El voto se registra en storage como dato de negocio:

```
osap-api ──(SERVICE JWT)──► osap-storage
        payload: { user_id: <UUID>, work_id, vote }
```

- storage no valida el JWT del usuario; el `user_id` es solo la referencia del voto.

## 9. Eliminar persistencia local de votos

- osap-api **no** mantiene BD de votos propia. Confirmar que `IVoteStore` en producción es
  `StorageVoteStore` y que no queda ningún store SQLite/local de votos.

## 10. `/api/v1/jobs*`

- **No** tocar la clasificación de `POST /api/v1/jobs*` en esta fase. Dejarlo fuera y
  documentarlo como pendiente de decisión.

---

## Tests

- Un token `token_use=user` → `UserPrincipal`.
- Un token `token_use=service` → `ServicePrincipal`.
- Compatibilidad temporal: un token sin `token_use` se resuelve **conforme a osap-auth** (sin
  heurísticas nuevas); un token antiguo de servicio no se interpreta como usuario.
- Anónimo no puede votar (401); anónimo puede buscar (200).
- Votar exige `email_verified=true` y rol `user` (403 si no).
- `/api/v1/admin/votes` exige `role=admin` (401 sin token, 403 sin rol).
- El voto llega a storage con `user_id` como dato de negocio (payload del service token).
- El service token a storage usa el **scope mínimo**: `storage:read` para lecturas,
  `storage:write` para votos; `storage:admin` solo en llamadas administrativas (no por defecto).
- osap-api no persiste votos localmente.
- **Los tests de osap-api verifican el contrato de salida hacia storage mediante mock/fake del
  cliente de storage. No se modifica ni adapta osap-storage para hacer pasar los tests.**

---

## NO implementar

- No añadir claims de `tier` al token (ni en osap-auth ni en osap-api).
- No tocar osap-auth ni osap-storage.
- No cambiar el contrato congelado `authentication-integration-v1.md` salvo lo que requiera
  reflejar la resolución del principal.
- No desplegar ni migrar producción sin aprobación.
- No clasificar `/api/v1/jobs*`.

---

## Validación

Al terminar, en osap-api:
- ejecutar los tests existentes;
- `ruff`, `mypy`, `pytest` limpios;
- confirmar que no se ha alterado el comportamiento público (búsqueda, estadísticas, etc.).

---

*Prompt de implementación de osap-api v1 (2026-08) — identidad y autorización.*
