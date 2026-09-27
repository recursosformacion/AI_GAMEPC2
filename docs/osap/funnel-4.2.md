# Fase 4.2 — Funnel de acceso y contribución (contrato)

Punto de partida: **v4.1.0 en producción** (`osap-api efa2074`, `osap-storage a19cf1e`,
`osap-auth c66c311`, `osap-support 36e4508`). Este documento define **el contrato y los
estados/eventos** del funnel sobre lo que **ya existe**, antes de escribir código.

## Invariantes (no negociables)

1. **No tocar auth** (`osap-auth`): usuarios, login, tokens y roles quedan como están.
2. **No tocar cuotas ni contadores verificados** (`download_plans`, `download_quota_daily`,
   `download_usage`, consumo atómico, 429). El funnel **observa**; no los modifica.
3. **No reabrir el circuito de descarga** (`download_representation`, `/api/v1/omr/download`,
   `/api/download` de storage con `storage:read`).
4. El estado **donor** tiene su **fuente de verdad en `osap-support`** (membresía/pago).
5. La **promoción de límite** debe ser **auditable y reversible**, con el mismo patrón que
   las migraciones anteriores (histórico + snapshot).

## Estados del funnel

| Estado | Identidad | Cuota vigente | Fuente |
|---|---|---|---|
| `S0 anon` | IP | `visitor` 10/día | plan `visitor` |
| `S1 anon_limit` | IP | 10/día agotada | `download_quota_daily` |
| `S2 user` | `user_id` | `registered` 100/día | plan `registered` |
| `S3 user_limit` | `user_id` | 100/día agotada | `download_quota_daily` |
| `S4 donor` | `user_id` | `donor` 1000/día | plan `donor` vía **promoción** |

Transiciones:
`S0 →(agota 10)→ S1 →(registro)→ S2 →(agota 100)→ S3 →(pago/donación)→ S4`,
y `S4 →(caduca membresía)→ S2` (reversión automática por vigencia).

## Eventos (append-only, auditables)

Nueva tabla **`funnel_events`** (no se toca el store de cuota):

```
funnel_events
-------------
id
created_at
event          -- limit_reached | registered | membership_activated
               -- membership_lapsed | promotion_applied | promotion_reverted
stage          -- S1 | S2 | S3 | S4 (según corresponda)
user_id NULL
ip_address NULL
day            -- YYYY-MM-DD
detail         -- JSON (límite, periodo, origen, override_id…)
```

Origen de cada evento **sin modificar lo verificado**:

- `limit_reached`: la **capa HTTP** emite el evento cuando `consume_omr_download` responde
  `allowed=false` (429). La cuota ya decidió; el funnel solo registra el hecho.
- `registered`: primera petición autenticada de un `user_id` que no existía en los eventos
  del funnel (primer avistamiento del usuario en osap-api).
- `membership_activated` / `membership_lapsed`: del contrato con `osap-support` (abajo).
- `promotion_applied` / `promotion_reverted`: al crear/expirar el override que materializa
  el nivel donor.

## Promoción de límite (reutiliza lo que ya existe)

El nivel donor **no** crea un plan especial por usuario: se materializa como
**`user_quota_overrides`** (ya en 4.1):

- `user_id`, `downloads_per_day = 1000`, `valid_from`/`valid_until` = **periodo de la
  membresía**, `note = "membership:<id>/<origen>"`.
- **Auditable**: cada promoción se registra también en `funnel_events`
  (`promotion_applied`) con el `override_id` y el periodo.
- **Reversible**: al caducar `valid_until`, el usuario vuelve al plan `registered` **sin
  acción manual** (el override simplemente deja de aplicar). Una revocación anticipada =
  borrar el override + evento `promotion_reverted`.

## Contrato `osap-api` ⇄ `osap-support`

`osap-support` es la **fuente de verdad** del donor. Interfaces existentes:
`GET /api/v1/membership/me` (usuario), `POST /api/v1/checkouts/{donation,membership}`,
`POST /api/v1/webhooks/payment`, y endpoints **m2m** (`/api/v1/m2m/...`).

Contrato a definir en 4.2 (lado support, mínimo):

1. **Lectura m2m por usuario** (service token): `GET /api/v1/m2m/membership?user_id=…`
   → `{active, tier, valid_from, valid_until, source}`. Permite a osap-api acreditar donor
   **sin depender del token del usuario**.
2. **Reconciliación**: job periódico en osap-api que, por cada usuario con actividad en el
   funnel, consulta la membresía y **aplica/actualiza/expira** el override
   (`valid_until` manda). Idempotente.
3. (Opcional, posterior) **Push firmado** desde support → osap-api (`membership_changed`)
   para acreditar al instante; el pull por reconciliación sigue siendo la red de seguridad.

Reglas:
- osap-api **nunca** decide quién es donor: solo refleja lo que dice support.
- Cambios de límite solo por plan (`visitor/registered/donor`) o por override; nunca por
  código.

## Métricas (derivadas, sin escrituras nuevas en cuota)

- Embudo: `#S1`, `#registros` (S1→S2), `#S3`, `#donaciones` (S3→S4), tasas de conversión.
- Denominadores desde `funnel_events`; volumen de descargas desde `download_usage`
  (ya existe); límites alcanzados desde `funnel_events(event='limit_reached')`.
- Panel admin: extiende la sección **Estadísticas** de 4.1 con el embudo.

Implementación (paso 7): **servicio interno de solo lectura** `FunnelMetricsUseCase`
(`funnel_events` + `download_usage`), **sin API pública nueva** en 4.2. Distingue
explícitamente **eventos** (`COUNT(*)`, p. ej. renovaciones) de **usuarios únicos**
(`COUNT(DISTINCT user_id)`, conversiones), desdobla `limit_reached` por stage (S1/S3) y
separa `promotion_reverted` de `membership_lapsed`. No escribe nada ni expone IPs.

## Fuera de alcance (4.2)

- Cambios en auth, en el store de cuota o en el circuito de descarga.
- Pasarela de pago (sigue en osap-support; osap-api solo **lee** el resultado).
- Gamificación/otros niveles no acordados.

## Entregables de 4.2 (cuando se apruebe este contrato)

1. DDL `funnel_events` + emisión en la capa HTTP (429) y en primer avistamiento.
2. Endpoint m2m de membresía en `osap-support` (o adaptación del existente).
3. Reconciliador idempotente osap-api → support → `user_quota_overrides`.
4. Panel de embudo (admin).
5. Tests (estados, promoción, caducidad, reversibilidad) y **verificación E2E en producción**
   con usuario temporal, igual que 4.1.

## Decisiones cerradas (4.2)

1. **Lectura de membresía** — **nuevo endpoint M2M** en `osap-support` (no se reutiliza un
   contrato existente con semántica distinta):

   ```
   GET /api/v1/m2m/membership?user_id=<id>
   → { "active": bool, "tier": "donor", "valid_from": ..., "valid_until": ..., "source": ... }
   ```

   **osap-api consulta; osap-support decide.** osap-api no interpreta importe, pago ni
   donación: solo materializa el resultado.

2. **Reconciliación** — **solo pull cada 15 min, idempotente. Sin push en 4.2.**
   `osap-api` → (cada 15 min) → `osap-support /m2m/membership` → reconciliación idempotente:
   membresía activa → crear/actualizar override; inactiva/caducada → retirar override.
   Debe poder ejecutarse 100 veces sobre el mismo estado sin generar basura ni promociones
   duplicadas.

3. **Granularidad donor** — **un único nivel**: `tier=donor → 1000/día`. No se introducen
   `donor_500`, `donor_1000`, etc. El campo `tier` existe en el contrato (la fuente de verdad
   es osap-support), pero en 4.2 osap-api solo materializa `donor`.

4. **Reversión** — **las dos**:
   - **Caducidad automática** (reversión normal): `valid_until < now` → membership inactiva →
     el override deja de aplicar → `S2 user`.
   - **Revocación manual de admin**: borra/revoca el override → evento
     `promotion_reverted` con **motivo + `override_id`**.
   `funnel_events` es **append-only**: no se modifican eventos anteriores.

## Orden de implementación (4.2)

1. Contrato M2M en `osap-support` (endpoint + auth M2M si aplica + respuesta + tests).
2. Modelo/eventos de funnel en `osap-api` (`funnel_events`, append-only, tipos definidos,
   `override_id` cuando corresponda, tests).
3. Integración de `limit_reached`: detectar el **429 real** de la capa HTTP y registrar el
   evento — **cero cambios en el quota store**.
4. `registered`: evento asociado al usuario, **sin alterar auth**.
5. Reconciliador de membership: consulta M2M, idempotencia, creación/actualización/revocación
   del `user_quota_overrides`, eventos `membership_activated/lapsed` y
   `promotion_applied/reverted`.
6. Revocación administrativa.
7. Métricas del funnel, derivadas **exclusivamente** de `funnel_events` + `download_usage`
   (sin contador paralelo).

Después: **E2E en producción controlada**, igual que en 4.1.
