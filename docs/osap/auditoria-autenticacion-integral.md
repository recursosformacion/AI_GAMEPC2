# Auditoria integral de autenticacion

Fecha: 2026-11-26.

## Estado ejecutivo

- Storage: corregida la configuracion versionada de produccion y el arranque fail-closed exige `auth.admin_handoff_origins`.
- Publicidad: corregido el handoff con una ruta Nginx explicita; el servicio exige origen y POST. La sesion de produccion exige una unica configuracion sin fallback silencioso.
- Auth, Storage, Support y las integraciones M2M tienen contratos implementados y suites locales dirigidas.
- No se ha realizado un login administrativo real ni se han cambiado secretos; por tanto no se declara el funcionamiento real de produccion verificado.

## Causas raiz observadas

1. `config.production.yaml` de osap-storage no contenia `admin_handoff_origins`, aunque el receptor exige la lista. Se devolvia un 403 fail-closed.
2. La configuracion versionada de Storage podia arrancar sin el origen de handoff. Ahora el arranque de produccion lo exige.
3. Publicidad tenia el prefijo publico resuelto por una reescritura generica. Se anadio una ruta exacta para `/publicidad/auth/session`, conservando el POST y eliminando solo el prefijo `/publicidad`.
4. Publicidad podia depender de secretos de sesion por fallback al arranque. La configuracion de produccion exige `AI_PUBLICIDAD_SESSION_SECRET`.

## Cambios realizados

- [Storage config](/D:/Proyectos/AI_OSAP/osap-storage/infrastructure/config.py): clave obligatoria de produccion.
- [Storage production config](/D:/Proyectos/AI_OSAP/osap-storage/config.production.yaml): origen legitimo `https://app.openmusicrepository.com`.
- [Advertising config](/D:/Proyectos/AI_OSAP/ai_publicidad/infrastructure/config.py): fail-fast de sesion, origen y secretos.
- [Advertising route](/D:/Proyectos/AI_OSAP/ai_publicidad/api/routes/auth.py): token ausente/invalido devuelve 401.
- [OSAP Nginx](/D:/Proyectos/AI_OSAP/osap-api/deploy/app.openmusicrepository.com.conf): ruta POST exacta.

## Verificacion ejecutada

- Storage: 22 pruebas pasaron.
- Publicidad: 10 pruebas pasaron.
- Contratos OSAP de handoff: 5 pruebas pasaron.
- Produccion: se comprobó JWKS y endpoints publicos solo con trafico de lectura y credenciales falsas. Los resultados HTTP confirmaron que los controles siguen activos.
- Navegador local: la SPA de `http://osap-app` se cargo y el entorno respondio; no habia una sesion administrativa de prueba disponible.

## Pendientes

- Desplegar los ficheros versionados en los servicios correspondientes.
- Probar con un usuario administrador real y un service client provisionado.
- Confirmar en servidor los valores efectivos sin mostrar secretos:
  - `admin_handoff_origins`;
  - audience de Storage;
  - clientes M2M y sus scopes;
  - JWKS, issuer y claves rotadas;
  - `AI_PUBLICIDAD_SESSION_SECRET`;
  - Nginx activo y reiniciado.
