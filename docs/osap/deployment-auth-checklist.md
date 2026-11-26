# Checklist de despliegue de autenticacion

Antes de desplegar:

1. No publicar secretos en artefactos, logs o informes.
2. Verificar issuer, JWKS y claves RS256 coherentes.
3. Confirmar los clientes M2M y sus scopes.
4. Confirmar la audience de cada receptor.
5. Verificar el origen de handoff de Storage y Publicidad.
6. Verificar cookies Secure, HttpOnly y SameSite.
7. Verificar que Nginx conserva `POST /publicidad/auth/session`.
8. Comprobar que los servicios fallan al arrancar si falta seguridad en produccion.

Validacion posterior sin escrituras:

- GET a `/publicidad/auth/session` debe ser `405`.
- POST con Origin legitimo y token falso debe rechazar identidad invalida.
- POST con Origin ajeno debe ser `403`.
- POST Storage con token falso y Origin legitimo debe ser `401/403` segun el contrato.
- `/api/v1/system/health` debe indicar el modo efectivo.
