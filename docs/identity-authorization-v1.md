# OSAP — identity-authorization-v1 (consolidado)


## Parte: identity-authorization-preparation-v1.md

---

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



## Parte: implementation-prompt-identity-authorization-v1.md

---

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
9. Eliminar cualquier persistencia local de votos. La UI de **Compositores** tampoco debe
   acceder directamente a osap-storage: siempre debe pasar por osap-api.
10. Exponer consulta pública de **Compositores** (listado/detalle/obras) y la **fusión** para
    `role=admin`, usando los endpoints existentes de osap-storage.
11. Dejar `/api/v1/jobs*` **fuera** hasta decidir su clasificación.

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
- **Scopes mínimos para Compositores:**
  - Consulta de compositores → `storage:read`;
  - Mantenimiento administrativo de compositores → `storage:admin`;
  - Fusión de compositores → `storage:admin`.
  - `storage:admin` **no** se utiliza para las consultas normales.
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

## 10. Pantalla de Compositores y navegación de autenticación

La aplicación osap-api debe incluir la pantalla/sección **Compositores** y el acceso a
autenticación en la navegación principal.

### 10.1 Compositores — consulta

La pantalla de Compositores permite consultar el catálogo de compositores.

- La consulta/listado de compositores es accesible para usuarios no administradores.
- Un usuario autenticado sin `role=admin` puede ver los compositores, pero no puede realizar
  operaciones de mantenimiento.
- La autorización de mantenimiento NO depende de `tier`.

### 10.2 Compositores — administración

Cuando el principal sea un `UserPrincipal` con `role=admin`, la pantalla debe habilitar las
operaciones administrativas de compositores que soporte el contrato de osap-storage:

- crear/modificar compositores;
- mantenimiento de compositores;
- fusionar compositores.

La autorización administrativa debe comprobar explícitamente:

```text
principal.type == user
AND "admin" in principal.roles
```

No debe utilizarse `tier` para conceder permisos administrativos.

### 10.3 Usuario no administrador

Para un `UserPrincipal` sin `admin`:

```
Compositores
  └── Ver/listar/detalle
```

No debe mostrar ni permitir acciones de: Editar, Crear, Eliminar, Fusionar, Mantenimiento.

Además, aunque un usuario manipule la UI o invoque directamente el endpoint, osap-api debe
rechazar la operación administrativa con **403**. **La UI NO es el mecanismo de seguridad; la
autorización debe existir también en el backend.**

### 10.4 Usuario anónimo

- El comportamiento de consulta de Compositores debe mantenerse **público** si así lo
  establece el endpoint de lectura correspondiente.
- Un usuario anónimo no puede realizar ninguna operación administrativa.

### 10.5 Navegación de autenticación

- La aplicación debe mostrar un enlace/acción de **Login** cuando no exista un usuario
  autenticado.
- Cuando exista un `UserPrincipal` autenticado, la navegación debe reflejar el estado de
  sesión y proporcionar la acción correspondiente de **logout/salida** si esta forma parte del
  flujo actual de osap-api.
- El estado de autenticación de la UI debe proceder del mecanismo de autenticación existente;
  **no crear un sistema de sesión paralelo**.

### 10.6 Regla de visibilidad

- La navegación de Compositores puede ser visible para todos si la consulta es pública.
- Las acciones administrativas deben mostrarse únicamente para `UserPrincipal + role=admin`.
- Independientemente de que se oculten o no en la UI, **el backend debe aplicar la misma
  autorización**.

### 10.7 Integración con osap-storage

Las operaciones de **consulta** utilizan:

```
osap-api ── SERVICE JWT + storage:read ──► osap-storage
```

Las operaciones **administrativas** utilizan:

```
USER + role=admin
        │
        ▼
    osap-api
        │
        └── SERVICE JWT + storage:admin ──► osap-storage
```

- Nunca se envía el JWT del usuario a osap-storage.
- El `user_id` del usuario no se utiliza como sustituto de la identidad de servicio.

### 10.8 Inspección previa (no inventar endpoints)

**No inventar endpoints ni funcionalidades de compositores.** Antes de implementar la pantalla
y las acciones administrativas, inspeccionar el contrato/documentación y el código actual de
osap-api y osap-storage para identificar los endpoints existentes de **consulta**, de
**mantenimiento** y de **fusión** de compositores.

- Si algún endpoint no existe, o el contrato no permite determinarlo, **detenerse e informar de
  la discrepancia** antes de crear una API nueva.
- Aplicar la misma regla de inspección previa del prompt: si el estado real difiere del
  descrito, no inventar una solución ni modificar silenciosamente la arquitectura.
- Cada acción administrativa de la pantalla de Compositores debe corresponder a un endpoint
  existente y documentado de osap-storage.

## 11. Compositores — consulta pública y administración

La funcionalidad de Compositores forma parte de esta fase de osap-api.

La inspección de osap-storage ha confirmado que existen actualmente:

- `GET /api/admin/composers`
- `GET /api/admin/composers/{composer_id}`
- `GET /api/admin/composers/{composer_id}/works`
- `GET /api/admin/composers/candidates`
- `POST /api/admin/composers/{target}/merge`

Los endpoints GET existentes son suficientes para implementar la consulta pública **sin crear
nuevos endpoints en osap-storage**.

### 11.1 Consulta de compositores

Crear en osap-api:

- `GET /api/v1/composers?q=&limit=&offset=`
- `GET /api/v1/composers/{composer_id}`
- `GET /api/v1/composers/{composer_id}/works`

Mapeo:

```
osap-api
    │
    │ SERVICE JWT + storage:read
    ▼
osap-storage
    ├── GET /api/admin/composers
    ├── GET /api/admin/composers/{composer_id}
    └── GET /api/admin/composers/{composer_id}/works
```

Estas operaciones admiten `AnonymousPrincipal` y `UserPrincipal`. **No requieren autenticación
de usuario.** El `ServicePrincipal` se utiliza únicamente en la llamada interna de
osap-api → osap-storage.

Los DTOs de osap-api deben reproducir los shapes existentes de osap-storage **sin inventar
campos** (`id`, `name`, `status`, `aliases_count`, `works_count`; `aliases`, `merged_into`,
`merged_at`; `work_id`, `title`, `composer_id`).

### 11.2 Lista de compositores

El frontend debe proporcionar una pantalla/ruta de **Compositores** accesible desde la
navegación principal. La pantalla debe permitir:

- consultar el listado;
- utilizar búsqueda `q`;
- paginar mediante `limit`/`offset`;
- seleccionar un compositor para acceder a su detalle.

**No implementar en v1 creación ni edición de compositores.**

### 11.3 Detalle de compositor

La pantalla de detalle debe mostrar la información proporcionada por
`GET /api/v1/composers/{composer_id}` y, cuando corresponda, sus obras mediante
`GET /api/v1/composers/{composer_id}/works`. **No añadir información que no exista en el DTO
recibido.**

### 11.4 Administración de compositores

- Un usuario **no administrador** puede consultar compositores, pero no puede realizar
  mantenimiento ni fusiones.
- Un usuario con `role=admin` puede acceder a las acciones administrativas previstas en v1.
- **La única operación administrativa de compositores incluida en esta fase es la fusión.**

Crear:

```
POST /api/v1/admin/composers/{target}/merge
```

Mapeo:

```
USER + role=admin
        │
        │ SERVICE JWT + storage:admin
        ▼
osap-storage
POST /api/admin/composers/{target}/merge
```

Reglas:

- sin token → **401**;
- usuario autenticado sin `admin` → **403**;
- usuario con `role=admin` → puede ejecutar la operación;
- la llamada de osap-api a osap-storage utiliza identidad SERVICE;
- **nunca se reenvía el JWT del usuario a osap-storage**;
- **no se utiliza `user_id` como sustituto del service token**;
- la operación administrativa requiere `storage:admin`.

### 11.5 Separación de consulta y administración

Es importante que la UI no trate la pantalla completa como "solo admin". La navegación debe
funcionar así:

```
Compositores
├── Usuario anónimo
│   ├── listar
│   ├── buscar
│   └── consultar detalle/obras
├── Usuario autenticado normal
│   ├── listar
│   ├── buscar
│   └── consultar detalle/obras
└── Usuario autenticado + role=admin
    ├── listar
    ├── buscar
    ├── consultar detalle/obras
    └── acciones administrativas
        └── fusionar
```

No mostrar acciones de mantenimiento/fusión a usuarios sin `role=admin`.

### 11.6 Login / logout y navegación

La aplicación debe incorporar el estado de autenticación en la navegación.

- Usuario no autenticado: `[Compositores] ... [Login]`
- Usuario autenticado: `[Compositores] ... [Logout]`
- Administrador: `[Compositores] ... [Admin / acciones administrativas] [Logout]`

- La UI **no** debe determinar que un usuario es administrador por su `tier`. La condición
  administrativa es exclusivamente `role=admin`.
- La integración de login/logout debe respetar el contrato existente de osap-auth. **No crear
  un mecanismo de autenticación paralelo en osap-api.**

### 11.7 Alcance fuera de v1

No implementar:

- creación de compositores;
- edición de compositores;
- eliminación de compositores;
- nuevos endpoints en osap-storage para esas operaciones;
- nuevos claims `tier`;
- autorización administrativa basada en `tier`.

**La fusión es la única operación de mantenimiento incluida en esta versión.**

## 12. `/api/v1/jobs*`

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
- Usuario anónimo puede acceder a la consulta pública de compositores.
- Usuario autenticado sin `admin` puede listar/ver compositores.
- Usuario autenticado sin `admin` recibe **403** al intentar una operación administrativa.
- Usuario con `role=admin` puede realizar mantenimiento de compositores.
- Usuario con `role=admin` puede solicitar una fusión de compositores.
- Un usuario `premium` sin `role=admin` **NO** obtiene permisos administrativos.
- Las operaciones de lectura utilizan `storage:read`.
- Las operaciones administrativas utilizan `storage:admin`.
- Nunca se envía el JWT del usuario a osap-storage.
- La UI muestra las acciones administrativas únicamente a un usuario con `role=admin`.
- Ocultar una acción administrativa en la UI no sustituye la comprobación backend.
- La navegación muestra **Login** cuando no hay usuario autenticado.
- La pantalla de Compositores **no debe inventar operaciones administrativas**: cada acción debe
  corresponder a un endpoint existente y documentado de osap-storage.

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



## Parte: identity-and-authorization-v1.md

---

# OSAP — Identity & Authorization v1 (coordinación)

**Estado:** DECISIONES CONGELADAS. **Implementación pendiente** (osap-api/osap-storage).
**Ámbito:** modelo transversal de identidad y autorización para `osap-auth`, `osap-api`, `osap-storage`.
**Regla:** no desplegar, no crear usuarios ficticios. Los scopes/claims de osap-auth se implementan
solo tras el prompt específico de osap-auth (ver `osap-auth/docs/implementation-prompt-token-use-scopes-v1.md`).

---

# 1. Decisiones congeladas (v1)

| Decisión | Resolución |
|---|---|
| Propietario de votos | **osap-storage** (RESOLVED) |
| Identidad de usuario | `user_id` UUID opaco (RESOLVED) |
| ANONYMOUS | Sí, sin usuario ficticio (RESOLVED) |
| Distinción USER/SERVICE | Claim explícito `token_use` (RESOLVED — decisión de contrato) |
| Tier vs Role | Separados: `type=user`→identidad; `user_tier`→nivel de servicio/cuenta; `role`→capacidad funcional/administrativa (RESOLVED — concepto; **sin** claims nuevos en osap-auth) |
| `storage:write` | Sí (RESOLVED) |
| `storage:admin` | Sí (RESOLVED) |
| Admin en osap-api | `role=admin` (RESOLVED) |
| Storage conoce usuarios | No (RESOLVED) |
| Storage acepta JWT de usuario | No (RESOLVED) |
| Votos | osap-api autentica/autoriza → osap-storage persiste (RESOLVED) |
| Estadísticas | osap-storage (RESOLVED) |
| Proceso nocturno | osap-storage / proceso interno (RESOLVED) |
| INTERNAL_PROCESS | Categoría conceptual, sin nuevo sistema de auth (RESOLVED) |
| `/api/v1/jobs*` | **PENDIENTE** — revisar antes de implementar |

**Corrección conceptual (aprobada):** la petición a Storage tiene **una identidad técnica**
(`SERVICE = osap-api`) y **además** un dato de negocio (`user_id` del votante). No son "dos
identidades simultáneas" en el sentido de que el servicio finja ser el usuario; son una
identidad de servicio + un dato de negocio.

**Cuestión abierta (no se asume):** no se congela que `admin` sea un *tier*. Conceptualmente
`admin` es un `role`; un administrador podría ser `tier = free` con `roles = ["user","admin"]`.
En la práctica se le podrá asignar un tier por conveniencia, pero el modelo de seguridad no
depende del tier. Se documenta para decidir en la fase de implementación.

---

# 2. Objetivo

Preparar la coordinación entre osap-auth, osap-api y osap-storage para trabajar con tres
tipos de principal — **ANONYMOUS**, **USER**, **SERVICE** — y dejar preparada una cuarta
categoría conceptual **INTERNAL_PROCESS** (no implementable todavía como mecanismo de
autenticación). Esta fase no implementa cambios funcionales: solo analiza, documenta y deja
preparado el terreno para la siguiente fase.

---

# 3. Principios

- **osap-auth autentica; osap-api autoriza; osap-storage autoriza la llamada técnica por scopes.**
- osap-auth responde "¿quién eres?" y **no** decide qué puede hacer un usuario en osap-api.
- osap-api responde "¿puedes realizar esta operación?" y aplica roles/permisos de negocio.
- osap-storage **no es un sistema de usuarios**: no valida JWT de usuario, no conoce email,
  contraseñas, sesiones ni roles de usuario; recibe solo llamadas de servicios autorizados.
- La única identidad de usuario que viaja entre apps es **`user_id` (UUID opaco)**.

---

# 4. Principales

| Principal | Identidad | Uso |
|---|---|---|
| `anonymous` | `user_id = null`, `service_id = null` | solo operaciones `PUBLIC` |
| `user` | `user_id` (UUID opaco) | operaciones `PUBLIC` + `USER` (+ rol) |
| `service` | `service_id = client_id` | llamadas servicio a servicio por scopes |
| `internal_process` | (conceptual) | procesos batch/nocturnos locales |

Ninguno se representa con un usuario ficticio.

> **Tipo de principal ≠ nivel del usuario ≠ rol.** `type` (anonymous|user|service) es la
> identidad; `user_tier` es el nivel de cuenta; `role` es la capacidad funcional/
> administrativa. No se convierte `free`, `premium`, `moderator` ni `admin` en un tipo de
> principal.

## Conceptos de identidad de usuario

| Concepto | Definición | Propiedad |
|---|---|---|
| `user_id` | UUID opaco del usuario; única identidad que viaja entre apps | osap-auth |
| `user_tier` | nivel de servicio/categoría de la cuenta del usuario | osap-auth |
| `role` | función o capacidad especial (administrativa/moderación) | osap-auth |

**Invariante:** `user_tier` y `role` son conceptos distintos. El `tier` representa el nivel de
cuenta; el `role` representa capacidades funcionales o administrativas. Un usuario **siempre**
mantiene `type = user` independientemente de su tier o de sus roles. **Ser Premium nunca
implica ser administrador**: la administración se otorga por `role = admin`, no por un tier
elevado.

## `user_tier` (referencia conceptual)

| user_tier | Significado | ¿Cambia type? |
|---|---|---|
| `free` | Usuario sin prestaciones de pago | No, sigue siendo `user` |
| `basic` | Nivel de servicio intermedio | No, sigue siendo `user` |
| `premium` | Nivel superior de servicio | No, sigue siendo `user` |
| otros | Futuros niveles comerciales | No, sigue siendo `user` |

> **No se fija todavía** que sean exactamente `free` + `basic` + `premium`. Si posteriormente se
> deciden dos o tres niveles de pago, no hay que tocar el modelo transversal: el `type` no
> cambia y la autorización depende de `user_tier` + `role` solo cuando la operación lo requiera.

> **Nota de contrato:** esta sección describe el modelo conceptual transversal. **No** implica
> que todos estos campos viajen en todos los tokens ni que el contrato JWT de osap-auth cambie
> ahora. No se introducen nuevos claims en osap-auth en esta fase.

---

# 5. ANONYMOUS

Petición sin usuario autenticado:

```text
user_id   = null
service_id = null
```

Solo puede ejecutar operaciones clasificadas `PUBLIC`. No se crea un usuario ficticio para
representarlo. En osap-api se materializaría como `AnonymousPrincipal`.

---

# 6. USER

Usuario autenticado por osap-auth. La identidad que viaja es exclusivamente `user_id` (UUID
opaco). Prohibido usar email, nombre, `username`, `email_lookup` u otra PII como identificador
entre servicios. El JWT de usuario contiene la identidad necesaria para que osap-api identifique
al usuario (`sub`, `jti`, `roles`, `email_verified`).

Principal de usuario (modelo conceptual):

```text
Principal:
    type       = user
    user_id    = <UUID>
    service_id = null
    tier       = free | basic | premium | ...
    roles      = ["user"]  (+ "moderator" | "admin" si procede)
```

Ejemplos:

| Principal | tier | roles |
|---|---|---|
| USER FREE | `free` | `["user"]` |
| USER BASIC | `basic` | `["user"]` |
| USER PREMIUM | `premium` | `["user"]` |
| MODERATOR | (tier que sea) | `["user","moderator"]` |
| ADMIN | (tier que sea, no necesariamente premium) | `["user","admin"]` |

Un Free y un usuario de nivel superior son **el mismo tipo de principal**: `USER`, identificado
por `user_id`. El `tier` no cambia el `type`. Un administrador podría incluso ser
`tier = free` con `roles = ["user","admin"]`; en la práctica se le asignará un tier por
conveniencia, pero el modelo de seguridad no depende de ello.

---

# 7. SERVICE

Identidad técnica (osap-api, procesos técnicos autorizados). Procede de osap-auth mediante
OAuth2 `client_credentials`. Se identifica por `service_id = client_id`. Los tokens de
servicio **no representan usuarios** y **no contienen identidad de usuario**.

---

# 8. INTERNAL_PROCESS

Categoría conceptual para procesos internos: recomputación nocturna de estadísticas, tareas de
mantenimiento, procesos batch. **No se implementa un mecanismo de autenticación específico
ahora.** En esta fase solo se documenta la categoría, se identifican los procesos actuales y
se indica qué habrá que decidir. **No** convertir `INTERNAL_PROCESS` en `USER`.

Procesos actuales (osap-storage, CLI local vía cron/systemd):
- `recompute-statistics`
- `backfill-composer-ids`
- `populate-composers`

Hoy no usan identidad de red (CLI local); se estudiará si necesitan identidad de servicio o
una categoría propia.

---

# 9. user_id

- UUID, opaco, estable, no reutilizable; única referencia de identidad de usuario entre apps.
- En osap-api: `votes.user_id`, estadísticas. En osap-storage: `votes.user_id` como **dato de
  negocio** (ver §14).
- Tras `user.deleted`: osap-api anonimiza el voto (`user_id=NULL`, `anonymized=1`) y conserva
  el agregado. Storage guarda solo el UUID opaco; nunca PII.

---

# 10. token_use

La distinción **USER vs SERVICE** debe hacerse **explícita** y no por heurísticas (presencia
o ausencia de `roles`/`client_id`).

**Decisión congelada:** claim `token_use` con valores `user` / `service`.

**El contrato actual de osap-auth NO soporta `token_use`.** Se implementa en osap-auth
solo vía el prompt específico (`osap-auth/docs/implementation-prompt-token-use-scopes-v1.md`),
sin introducir lógica de negocio de API/Storage.

Dónde se incorpora:
- Emisión en osap-auth al firmar user tokens (`token_use: "user"`) y service tokens
  (`token_use: "service"`).
- Documentos a modificar: `osap-auth/docs/osap-auth-api-v1.0.md` §10 y §11, y la validación
  de osap-api (`authentication-integration-v1.md`).
- Tests necesarios: emisión/validación de user y service tokens, rechazo cruzado, firma/JWKS.
- Impacto: claim aditivo; permite distinguir el tipo de token sin heurísticas.

---

# 11. Autenticación vs autorización

- **Authentication** (osap-auth): valida firma JWKS, `iss`, `aud`, `exp`, clock skew; resuelve
  `user_id` (user token) o `service_id` (service token).
- **Authorization** (osap-api): decide si el principal puede ejecutar la operación (roles,
  `email_verified`, reglas de negocio).
- **Authorization técnica** (osap-storage): solo comprueba el scope del token de servicio
  (`storage:read` hoy).

---

# 12. Matriz de autorización

> Las columnas de usuario muestran los tiers previstos únicamente como **referencia de
> política**. La autorización real se expresa mediante la combinación de `user_tier` y `role`
> **solo cuando una operación tenga una regla dependiente de ellos**. Un usuario siempre es
> `type=user`.

### osap-api (endpoints de `src/osap/api/platform_app.py`)

| Operación | Anonymous | Free | Basic | Premium | Admin* | Rol | user_id | Delega |
|---|---|---|---|---|---|---|---|---|
| `GET /api/v1/search-model`, `/intent` | ✓ | ✓ | ✓ | ✓ | ✓ | — | no | no |
| `POST /api/v1/searches`, `GET /searches/{id}` | ✓ | ✓ | ✓ | ✓ | ✓ | — | no | sí → storage |
| `GET /api/v1/representations/{id}/download` | ✓ | ✓ | ✓ | ✓ | ✓ | — | no | sí → storage |
| `GET /api/v1/providers*`, `/repository-sources*`, `/sources*`, `/discover/sources` | ✓ | ✓ | ✓ | ✓ | ✓ | — | no | no |
| `GET /api/v1/knowledge/*`, `/system/*` | ✓ | ✓ | ✓ | ✓ | ✓ | — | no | no |
| `POST /api/v1/jobs*` | (pendiente) | ? | ? | ? | ? | — | no | no |
| `POST /api/v1/works/{work_id}/vote` | ✗ | ✓ | ✓ | ✓ | ✓ | `user` + `email_verified` | **sí** | sí → storage |
| `GET /api/v1/works/{id}/statistics`, `/composers/{id}/statistics` | ✓ | ✓ | ✓ | ✓ | ✓ | — | no | sí → storage |
| `GET /api/v1/admin/votes` | ✗ | ✗ | ✗ | ✗ | ✓ | `admin` | sí | sí → storage |

\* **Admin** se concede por `role=admin`, no por ser un tier elevado. Ser Premium nunca implica
administración.

### osap-storage

| Operación | Principal | Scope | user_id | Anónimo | Notas |
|---|---|---|---|---|---|
| Provider API: `GET /api/search`, `/lookup`, `/resource/{id}`, `/download/{id}`, `/version` | SERVICE | `storage:read` | no | no | llamada por osap-api |
| `POST /api/v1/works/{work_id}/votes` | SERVICE | `storage:read` (+futuro `storage:write`) | **sí (dato de negocio)** | no | el `user_id` va en el payload |
| `GET /api/v1/works/{id}/statistics`, `/composers/{id}/statistics` | SERVICE | `storage:read` | no | no | |
| `/api/admin/composers*` (listar, detalle, works, merge) | SERVICE | `storage:read` / futuro `storage:admin` | no | no | administrativo |
| `recompute-statistics`, `backfill-composer-ids`, `populate-composers` | INTERNAL_PROCESS | — | no | — | CLI local |

---

# 13. Scopes

Existentes (contrato osap-auth v1.0):
- `api:read`, `storage:read`, `auth:admin`, `user.deleted:subscribe`.

Aprobados (implementación en osap-auth vía prompt específico; en storage/osap-api en su fase):
- `storage:write` — votos (POST de voto) y operaciones de escritura de storage.
- `storage:admin` — administración de compositores, fusiones, operaciones administrativas.

`storage:read` **no se amplía** con escritura; se añaden scopes dedicados.

---

# 14. Llamadas entre servicios

> La llamada a Storage tiene **una identidad técnica** (`SERVICE`) y **un dato de negocio**
> (`user_id`) cuando procede. No son dos identidades simultáneas.

### Público
```
ANONYMOUS ──► osap-api ──(SERVICE, storage:read)──► osap-storage
```

### Autenticado
```
USER ──(user JWT)──► osap-api
                        │
                        │ autorización
                        ▼
                 SERVICE: osap-api   (SERVICE JWT)
                        │
                        │ user_id = UUID (dato de negocio)
                        ▼
                 osap-storage
```
Storage sabe qué servicio le habla y a qué usuario pertenece el voto, pero no necesita saber
nada más sobre ese usuario.

### Administrativo
```
USER + admin ──(user JWT)──► osap-api ──(SERVICE JWT + admin scope)──► osap-storage
```

### Interno
```
INTERNAL_PROCESS ──► osap-storage   (CLI local; no implementar sistema nuevo todavía)
```

---

# 15. Votos

Arquitectura acordada (flujo):
1. El usuario se autentica contra osap-auth.
2. osap-api recibe el JWT.
3. osap-api identifica al USER mediante `user_id`.
4. osap-api autoriza la operación.
5. osap-api llama a osap-storage utilizando identidad SERVICE.
6. osap-storage registra el voto asociado al `user_id` recibido como dato de negocio.

**Puntos clave (corrección conceptual aprobada):**
- La petición a Storage tiene **una** identidad técnica: `SERVICE = osap-api`. El `user_id` es
  un **dato de negocio** del payload del voto, no una identidad simultánea.
- Storage **no valida el JWT del usuario** ni necesita saber nada más de él; solo sabe qué
  servicio le habla y a qué usuario pertenece el voto.
- La regla *1 voto por obra y día UTC* es responsabilidad del modelo de datos/negocio de
  **storage** (UNIQUE en BD).

**No implementar todavía.** Puntos a modificar en la fase de implementación:
- osap-api: `POST /api/v1/works/{work_id}/vote` debe (a) validar el user JWT, (b) autorizar,
  (c) obtener service token, (d) llamar a storage con `user_id` como dato en el payload.
- osap-storage: exponer el scope de escritura correspondiente y mantener la regla de unicidad.

---

# 16. Administración

Endpoints a revisar: `/api/admin/*` (osap-api: `/api/v1/admin/votes`) y
`/api/admin/composers*` (osap-storage).

Modelo conceptual esperado:
```
USER + role=admin ──► osap-api ──(SERVICE + admin scope)──► osap-storage
```

- osap-api: `/api/v1/admin/votes` debe exigir `role=admin` (hoy solo exige autenticación).
- osap-storage: `/api/admin/composers*` es administrativo; hoy preparado pero sin enforcement
  (ver contradicción C3). Requerirá scope `storage:admin`.

No implementar todavía.

---

# 17. Procesos internos

- osap-storage: `recompute-statistics`, `backfill-composer-ids`, `populate-composers` (CLI,
  cron/systemd). No usan identidad de red.
- Se documenta la categoría `INTERNAL_PROCESS`; decisión posterior: identidad de servicio vs
  categoría propia. No implementar.

---

# 18. Errores

| Código | Uso |
|---|---|
| 401 | Token ausente/inválido/caducado, o principal requerido |
| 403 | Identidad válida pero sin permiso (rol/scope) |
| 404 | Recurso inexistente |
| 422 | Validación (p.ej. voto fuera de 1..5) |
| 409 | Conflicto (p.ej. voto duplicado por día) |

Solo si es compatible con los contratos existentes.

---

# 19. Cuestiones pendientes

**Resueltas (congeladas):**
1. `token_use` (user/service) → **RESOLVED**; implementación en osap-auth vía prompt específico.
2. Scopes `storage:write` y `storage:admin` → **RESOLVED** (definir operaciones exactas al
   implementar en storage).
3. `INTERNAL_PROCESS` → **RESOLVED** como categoría conceptual (sin sistema nuevo).
4. Rol `admin` en osap-api → **RESOLVED** (cablear comprobación de rol).
5. Principal en osap-api (`AnonymousPrincipal`/`UserPrincipal`/`ServicePrincipal`) → **RESOLVED**
   como concepto a implementar.
6. Propietario de votos → **RESOLVED** (storage).

**Pendientes de revisar antes de implementar:**
- **`/api/v1/jobs*`**: clasificar PUBLIC o USER/SERVICE.
- **Política de `user_tier`:**
  - el modelo distingue `tier` de `role`;
  - `type=user` no cambia con el tier;
  - inicialmente se contemplan, como mínimo, `free` y niveles superiores;
  - se podrán definir 2 o 3 niveles de pago/servicio adicionales **sin modificar el modelo de
    identidad**;
  - los nombres definitivos (`basic`, `premium`, etc.), límites y permisos de cada tier se
    decidirán **antes de implementar** las reglas que dependan de ellos;
  - `admin` **no es un tier de seguridad**: el privilegio administrativo procede
    exclusivamente de `role=admin`;
  - un usuario `free` puede, excepcionalmente, tener `role=admin`.

---

# 20. Impacto por aplicación

- **osap-auth**: (si se aprueba) emitir `token_use`; scopes de servicio. Contrato interno
  independiente de osap-api/osap-storage.
- **osap-api**: introducir Principal; autorización por endpoint (votar, admin); dejar de
  persistir votos (delegar a storage vía service token).
- **osap-storage**: scopes `storage:write`/`storage:admin`; enforcement administrativo;
  confirmar ausencia de validación de usuario.

---

# 21. Plan de implementación posterior

Orden acordado:
1. **Congelar decisiones** (este documento, RESOLVED). ✅ hecho.
2. **osap-auth**: `token_use` (user/service) + scopes de servicio
   (prompt: `osap-auth/docs/implementation-prompt-token-use-scopes-v1.md`), sin lógica de
   negocio de API/Storage. **No** introduce `tier`/`role` en el JWT en esta fase.
3. **osap-api**: implementar `Principal` (Anonymous/User/Service) con `tier` y `roles`
   separados, autorización por operación (votar exige user; admin exige rol `admin`), eliminar
   el `del authorization` sin enforcement.
4. **Conectar API → Storage**: cliente de servicio real (`client_credentials` → SERVICE JWT) y
   usarlo para llamar a storage; votos con `user_id` como dato de negocio.
5. **osap-storage**: `storage:write`, `storage:admin`, enforcement de scopes, proteger
   `/api/admin/composers*` y la escritura de votos; mantener públicas las operaciones de
   lectura.
6. Revisar `INTERNAL_PROCESS` (categoría) y la política de `tier` (nombres de niveles) sin
   implementar sistema nuevo.

Cada paso se ejecuta en su fase de implementación; esta fase congela decisiones y prepara los
prompts.

---

# Contradicciones encontradas

> Estado de resolución: C1, C2, C3, C4 → **RESOLVED** (decisión congelada). Implementación
> pendiente.

## C1 — Propietario de los votos

- **Fichero:** `osap-api/docs/authentication-integration-v1.md` §3 vs `osap-storage/docs/voting-statistics-v1.md`.
- **Situación:** el doc de osap-api describe el modelo del voto "en su BD propia `osap_api`";
  el de osap-storage declara que **storage es el propietario** de `votes`, `work_statistics`,
  `composer_statistics` y del proceso nocturno. Además, la decisión de arquitectura recibida
  indica "los votos se guardan en storage".
- **Resolución (RESOLVED):** storage es el propietario persistente de votos y estadísticas;
  osap-api autentica/autoriza y delega la persistencia vía service token.
- **Impacto:** osap-api no mantiene BD de votos propia; el esquema vive en storage.

## C2 — Distinción USER vs SERVICE

- **Fichero:** `osap-auth/docs/osap-auth-api-v1.0.md` (§10, §11).
- **Situación:** el contrato no define un claim normativo para distinguir user token de service
  token; hoy se distinguirían por heurística (presencia de `roles`/`sub` vs `client_id`).
- **Resolución (RESOLVED):** claim `token_use` (`user`/`service`); implementación en osap-auth
  vía prompt específico.
- **Impacto:** validación centralizada del tipo de token en todos los servicios.

## C3 — Administración de osap-api sin rol

- **Fichero:** `osap-api/src/osap/api/platform_app.py` (`/api/v1/admin/votes`).
- **Situación:** el endpoint admin solo comprueba autenticación, no el rol `admin`. El contrato
  (`authentication-integration-v1.md` §7) exige rol `admin`.
- **Resolución (RESOLVED):** exigir `role=admin` (decide osap-api) al cablear la autorización.
- **Impacto:** no rompe el contrato; queda pendiente el enforcement en osap-api.

## C4 — Administración de compositores sin enforcement

- **Fichero:** `osap-storage/docs/composer-administration-v1.md` (§Autorización) y
  `service-auth-v1.md`.
- **Situación:** `/api/admin/composers*` es administrativo pero "el punto de integración queda
  preparado" sin enforcement; service-auth solo define `storage:read`.
- **Resolución (RESOLVED):** scope `storage:admin` y protección de esa sección en la fase de
  implementación de storage.
- **Impacto:** requiere implementar el scope `storage:admin` y el enforcement.

---

*Documento de coordinación v1 (2026-08) — decisiones congeladas; implementación pendiente.*



