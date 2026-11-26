# Contrato de handoff administrativo

## Reglas comunes

- Metodo: `POST`.
- El navegador envia el token en el cuerpo `application/x-www-form-urlencoded`.
- El receptor valida `Origin` contra una lista explicita.
- Origen legitimo: `https://app.openmusicrepository.com`.
- Prohibido enviar el token en URL, Referer, historial o logs.
- Cookie: `HttpOnly`, `Secure`, `SameSite=Lax` y caducidad corta.
- Destino: relativo local o redireccion expresamente permitida.
- Sin Origin o origen desconocido: `403`.

## Storage

- URL publica: `https://storage.openmusicrepository.com/admin/session`.
- Identidad: service token con `storage:admin`.
- Cookie: `osap_storage_admin`.
- Configuracion obligatoria en produccion: `auth.admin_handoff_origins`.

## Publicidad

- URL publica: `https://app.openmusicrepository.com/publicidad/auth/session`.
- Identidad: access token de usuario validado por Auth; solo rol `admin`.
- Cookie: `ai_publicidad_session`, caducidad maxima cinco minutos.
- Panel: `https://app.openmusicrepository.com/publicidad/p`.
- Nginx reescribe solo el prefijo `/publicidad/` antes de entregar la solicitud al servicio.

## Support

- URL: `/support-api/api/v1/admin/web/session`.
- Identidad: service token con `support:admin`.
