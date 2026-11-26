# Contrato de autenticacion de OSAP

## Autoridad de identidad

`osap-auth` es la autoridad de identidad. Emite:

- sesiones y refresh tokens de usuario;
- access tokens JWT para navegador;
- tokens M2M mediante `client_credentials`.

## Identidad de usuario

- Firma: RS256.
- Issuer de access tokens: `https://auth.openmusicrepository.com`.
- Issuer OIDC de discovery: se obtiene de la configuracion OIDC de osap-auth.
- Audience: `osap-api`, salvo integraciones receptoras que declaren otra audiencia.
- JWKS publico versionado mediante `https://auth.openmusicrepository.com/auth-api/auth/.well-known/jwks.json`.
- Los roles y permisos administrativos se obtienen de Auth. Los servicios no deben mantener una replica independiente.
- Tokens expirados, mal firmados o con audience incorrecta son rechazados.

## Respuestas

- `401`: credencial ausente, invalida o expirada.
- `403`: identidad valida sin permiso, scope o origen autorizado.
- `404`: recurso inexistente.
- `405`: metodo no admitido.
- `503`: Auth/JWKS no disponible.

## Handoff

El handoff es un intercambio POST desde el navegador. Puede usar un token de usuario para identificar al administrador iniciador o un token de servicio para un panel que no delega identidad de usuario. Ambos usos deben mantenerse separados y nunca convertir un service token en identidad de usuario.
