# Versionado OSAP

## Política: versión única coordinada

Todos los componentes de OSAP comparten **una sola versión** y se suben juntos:

- `osap-api` (backend + SPA)
- `osap-storage`
- `osap-auth`
- `osap-support`

No se versiona cada parte por separado. Así se evita tener que mantener una matriz de
dependencias (p. ej. «api 3.x requiere storage 2.1»): si todo va con el mismo número, una
versión de plataforma describe el conjunto completo y es desplegable como un todo.

### Reglas
1. **Un número para todo**: al preparar una entrega se actualiza la versión en:
   - `pyproject.toml` de los 4 repos (`version = "X.Y.Z"`),
   - `web/package.json` de la SPA (`"version"`).
2. **Tag de release en todos los repos**: se crea el mismo tag anotado (p. ej. `vX.Y.Z`) en
   `osap-api`, `osap-storage`, `osap-auth` y `osap-support`, y se empujan.
3. **Semántica** (semver, aplicada al conjunto):
   - **MAJOR**: cambios de modelo/esquema de datos o de contrato que rompen compatibilidad
     (p. ej. nuevo modelo de personas, identidad de recurso en el índice).
   - **MINOR**: funcionalidad nueva compatible.
   - **PATCH**: correcciones y ajustes sin cambio de contrato.
4. `osap-auth` y `osap-support` se etiquetan con el mismo número aunque no cambien, para
   dejar claro qué revisión del conjunto está en producción.

### Historial
- **4.2.0** — funnel de acceso y contribución: `funnel_events` append-only
  (`limit_reached`/`registered`/`membership_activated|lapsed`/`promotion_applied|reverted`),
  promoción donor materializada como `user_quota_overrides` por reconciliación M2M **pull**
  con osap-support (cada 15 min vía `osap-reconcile-membership.timer`), revocación
  administrativa que no resucita en el mismo periodo, y métricas derivadas. Corrección del
  cableado de `service_audience` en osap-support (`aud=osap-support` para tokens M2M).
  Colaboradores: las altas de usuario enlazan a la pantalla de registro de osap-auth.
- **4.1.0** — cuota de descargas OMR (planes 10/100/1000, excepción por usuario con
  vigencia, auditoría `download_usage`), gateo de `download_representation` y
  `/api/v1/omr/download`, cierre del bypass de storage (`/api/download` exige
  `storage:read`) y panel de administración de cuotas/estadísticas.
- **4.0.0** — entrega coordinada: modelo de datos nuevo de `osap-storage`
  (`persons`, voicings→ensembles; migraciones 006–008), identidad de recurso en el índice
  de `osap-api` (`source_rep_id`/`resource_id`, `person_id`), formatos CPDL ampliados y
  editor de relaciones de obra; despliegue de los 4 programas.
