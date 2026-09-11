# ADR-0036 – Security Audit: clasificación y mitigaciones

## Estado

Aceptado (2026-09-09). Carril independiente (no forma parte de F0–F5). Clasifica por
severidad los hallazgos de seguridad detectados en la revisión local (líneas NO
modificadas por las fases F0–F4) y registra las decisiones tomadas.

## Hallazgos y severidad

| # | Hallazgo | Ubicación | Severidad | Decisión |
|---|----------|-----------|-----------|----------|
| S1 | **SSRF en `preview_source`** (URL de usuario leída con `urlopen` sin validar) | `platform.py` `preview_source` | **Alta** | **Mitigado 2026-09-09**: guard `_validate_preview_url` (solo http/https; rechaza IPs privadas/loopback/link-local/reservadas/multicast y hostnames localhost/.local/.internal/.localhost o sin punto). Caveat documentado: los hostnames DNS no se resuelven (riesgo de rebinding residual). Tests en `test_preview_url_guard.py`. |
| S2 | **JWT `alg:none` en `dev_session`** | `platform.py` `dev_session` | Media (solo dev) | Mantener SOLO detrás de `OSAP_DEV_AUTH_BYPASS=1` (ya verificado en `dev_session`: `ForbiddenError` si el bypass no está activo). Prohibir en producción por configuración/despliegue. Sin cambio de código. |
| S3 | **Credenciales MySQL hardcodeadas como fallback** | `wiring.py` / `op_store.py` | Alta (en prod) | La configuración de producción DEBE inyectar credenciales vía entorno/secretos; el fallback por defecto se limita a entornos de desarrollo. Acción recomendada (despliegue): no inyectar credenciales por defecto en prod y eliminar el fallback cuando el entorno de prod no dependa de él. Sin cambio de código en esta iteración. |
| S4 | **Path OIDC sin validar desde env** (`OSAP_OIDC_STATE_FILE`) | `platform.py` OIDC | Media | Se acepta la configuración por entorno; mitigación recomendada en despliegue: apuntar `OSAP_OIDC_STATE_FILE` a un directorio dedicado y de permisos restringidos. Sin cambio de código en esta iteración. |
| S5 | **SSRF por `base_url` de proveedores y URLs de descarga** | wiring / adapters | Media | Aceptado con documentación: la configuración de proveedores es operativa (admin de confianza), no input de usuario final. Mitigación futura: validación https y listas de permitidos al persistir config de proveedor. Sin cambio de código en esta iteración. |
| S6 | **`JwtAuthenticator` sin verificación de firma** | `token_authenticator.py` | Alta (si se usara en prod) | Se verifica su uso: SOLO en el flujo de desarrollo (`dev_session`) dentro del bypass. Decisión: mantener como fixture de desarrollo; no usarlo para autenticación real. Refuerzo en el plan de auth de producción (V3.2+). |

## Principios

- No mezclar con F0–F5 (limpieza técnica): cada hallazgo tiene dueño y decisión explícita.
- S1 queda cerrado (mitigación + tests). S2/S6 dependen del despliegue (bypass dev). S3/S4/S5
  requieren decisiones de entorno/infraestructura y quedan registradas como acciones de
  despliegue, no como defectos de código pendientes de F5.
