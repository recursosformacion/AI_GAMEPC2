# OSAP — Registro de usuario (Web OSAP) — decisión v1

**Estado:** DECISIÓN ARQUITECTÓNICA (a congelar). **No implementado.**
**Base:** osap-auth es la autoridad de identidad. **No se crea** tabla de usuarios en osap-api,
registro paralelo, endpoint que escriba en storage, segundo sistema de credenciales, ni roles/
tier en el Web.
**Objeto:** cerrar cómo el Web OSAP registra usuarios vía osap-auth (inspección del contrato de
registro hecha).

---

# 1. Frontera

```
Web OSAP
   │
   │ email + password + datos de registro
   ▼
osap-api
   │
   │ llamada al endpoint público de osap-auth
   ▼
osap-auth
   │
   └── crea usuario
```

- **No** interviene un service client: es una operación de **usuario/identidad**, no entre
  servicios.
- osap-api **no** crea usuarios directamente en la BD de osap-auth.
- osap-auth sigue siendo la **autoridad de identidad**.

---

# 2. Contrato de registro de osap-auth (inspección)

## `POST /auth/register`

**Request:**
```json
{ "email": "usuario@example.com", "password": "mínimo 8", "name": "Opcional (max 120)" }
```

**Response 200:**
```json
{ "user_id": "<uuid o null>", "verification_token": "<dev> | null", "message": "Si el email es nuevo, se ha enviado un enlace de verificación." }
```

## Semántica

| Aspecto | Contrato |
|---|---|
| Email existente | **200 genérico** (`user_id=null`, mismo mensaje) — anti-enumeración; no revela si existe |
| Password | **mínimo 8** caracteres (`validate_password`) |
| Email | validado y normalizado (minúsculas; gmail sin puntos en local) |
| `email_verified` | **false** hasta verificar |
| Verificación | **requerida**: `POST /auth/verify-email` con token; en prod el token va por email; en dev se devuelve en la respuesta |
| Auto-login | **NO**: el registro devuelve `user_id`/mensaje, **no tokens**; hay que hacer **login** después |
| Rate limit | por IP (`register_per_minute`) |

---

# 3. Decisión congelada — Registro

- osap-api expone un **proxy público** `POST /api/v1/auth/register` que reenvía a osap-auth
  (sin service client, sin BD).
- El Web muestra un **formulario de registro** (email, password, name) → `POST /api/v1/auth/
  register`.
- Tras registrar (éxito o email existente, ambos 200 genérico):
  - El Web muestra "**verifica tu email**" (no inicia sesión).
  - En **dev**, si llega `verification_token`, el Web puede autoverificar o mostrar el paso de
    verificación.
- Después del registro, el flujo continúa con **Login** (osap-auth → tokens).

## Registro (no autenticado) → Login

```
NO autenticado
   ├── Login → osap-auth → tokens
   └── Registro → osap-auth → usuario (verificado) → luego Login
```

---

# 4. Fuera de v1

- CRUD/roles/tier en el Web.
- Segundo sistema de credenciales.
- Tabla de usuarios en osap-api.
- Registro que escriba en storage.

---

# 5. No implementar todavía

- No se implementa el registro aún.
- No se toca lo ya cerrado (login, voto, compositores, valoración, administración).

---

*Decisión de Registro v1 (2026-08) — pendiente de aprobación; no implementado.*
