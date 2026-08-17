# ADR-0033 – Resolución asíncrona mediante ResolutionSession

## Estado

Aceptado (arquitectura).

## Contexto

`POST /works/resolve` (ADRs previos y `docs/osap/works-resolution.md`) es **síncrono y
bloqueante**: espera a que todo el lote termine dentro de la petición HTTP. Aunque se
pueda reanudar, eso degrada la experiencia (el cliente espera "30 segundos mientras
consulto todos los proveedores") y provoca timeouts frecuentes. Además, la adquisición
completa del universo antes de mostrar nada es innecesariamente lenta: OMR puede devolver
490 obras para `Mozart` cuando el usuario solo necesita ver resultados ya.

También queda claro (prueba de 250 obras reales) que **estado de la sesión y estado de
cada resolución son dos cosas diferentes**: una sesión puede estar `partial` y contener
180 obras `resolved`, 40 `ambiguous` y 30 `not_found`.

## Decisión

Se separa la **petición de búsqueda** de la **adquisición/resolución**. La resolución
pasa a ser un **trabajo progresivo e independiente de la petición HTTP**, persistido en
el estado operativo de osap-api.

Tres conceptos:

- **Search**: respuesta síncrona rápida. Nunca crea sesiones.
- **ResolutionSession**: trabajo de adquisición/resolución que progresa en segundo plano.
- **ResolutionResult**: resultado por obra que se va mejorando a medida que crece el
  universo adquirido.

### Puntos fijados

1. **`/search` sigue siendo síncrono** y **no crea sesiones**.
2. **`/works/resolve` deja de ser bloqueante**: crea una `ResolutionSession`, devuelve
   `202 Accepted` + `session_id` inmediatamente.
3. La **`ResolutionSession` pertenece al estado operativo de osap-api**, en `OpStore`
   (`src/osap/infrastructure/state/op_store.py`).
4. **`OpStore` no es caché global ni catálogo**: aloja solo estado operativo.
5. **`provider_results`** conserva lo adquirido durante esa sesión concreta, para poder
   **reanudar/reprocesar sin volver a consultar a los proveedores**.
6. La **adquisición se ejecuta mediante el worker de `domain/jobs`** (V2.2, ADR-0026).
7. El **matching puede ejecutarse provisionalmente** y **volver a ejecutarse cuando
   aumenta el universo adquirido** (re-resolver es idempotente: no se re-consulta a los
   proveedores, se re-rankea sobre el universo ya en `OpStore`).
8. La **paginación de proveedores queda completamente separada de la paginación que
   consume la Web**.
9. Una sesión puede terminar en: `complete`, `partial`, `failed`, `expired`.
10. **`resolved` no significa que se haya consultado todo el universo posible**: significa
    que el motor considera **suficientemente fuerte** la resolución con la evidencia
    disponible.
11. **No se crea una tabla global `works`** en osap-api.
12. Las **políticas de adquisición serán configurables** y tendrán **límites** para
    impedir adquisiciones indefinidas (ver "Política de adquisición").

### Estado de la sesión vs. estado de cada obra

No se mezclan. Son dos máquinas de estado independientes.

**Estado de la sesión:**

```
acquiring ──► resolving ──► complete

acquiring / resolving ──► partial   (se alcanzaron límites de política)
acquiring / resolving ──► failed    (no pudo completarse)
acquiring / resolving ──► expired   (superó su TTL)
```

`partial`, `failed` y `expired` no son ramas exclusivas de `complete`: pueden producirse
desde `acquiring` o desde `resolving`.

- `acquiring`: el worker está adquiriendo páginas de los proveedores.
- `resolving`: adquisición terminada (o en curso para provisional); ejecutando matching.
- `complete`: adquisición terminada según el plan y resolución ejecutada.
- `partial`: se alcanzaron límites de política sin completar el universo (honesto, no se
  finge completitud).
- `failed`: la sesión no pudo completarse.
- `expired`: superó su TTL sin resolverse.

**Estado de cada obra (`ResolutionResult`):**

- `resolved`
- `ambiguous`
- `not_found`

Una sesión `partial` puede contener 180 `resolved`, 40 `ambiguous` y 30 `not_found`.

### Política de adquisición (configurable)

Los límites son **política configurable de la sesión**, no valores cerrados de este ADR:

- `max_results_to_acquire`
- `max_pages_per_provider`
- `max_duration`

El motor clasifica la consulta y genera un **`AcquisitionPlan`**:

| Consulta | Perfil | Plan |
|---|---|---|
| `Mozart Ave Verum K.618` | concreta (título + catálogo + compositor) | adquisición pequeña, resolución rápida |
| `Mozart` | por compositor | muchas páginas, proceso progresivo |
| `a` | demasiado amplia | no adquiere todo; sesión `partial` |

Si se alcanzan los límites sin completar el universo, la sesión se marca `partial`.

### Dos niveles de matching

- **Provisional**: sobre el universo adquirido hasta el momento, para mostrar resultados
  pronto a la Web (`OMR página 1 → 50 obras → normalizar → comparar → 20 coincidencias`).
- **Definitivo**: cuando la adquisición termina, se re-ejecuta el matching sobre el
  universo completo en `OpStore` (p. ej. 490 de OMR + IMSLP completo + MusicBrainz +
  Mutopia) y se actualizan los resultados.

## Endpoints

```
POST /works/resolve
    → 202 Accepted
    → { "session_id": "..." }

GET /sessions/{session_id}
    → estado de la sesión + progreso + contadores

GET /sessions/{session_id}/results?page=...
    → resultados de resolución (paginación de la Web, desacoplada de la de proveedores)
```

## Consecuencias

- La búsqueda deja de ser "espera 30 segundos" y pasa a ser "aquí tienes resultados;
  estoy ampliando y mejorando la búsqueda".
- `OpStore` (MySQL + fallback a memoria) permite que una sesión **sobreviva a un timeout,
  a un reinicio de API y a que el usuario cierre el navegador**.
- Se reutiliza: `domain/jobs` (worker), `MetadataNormalizer`, `WorkResolutionEngine`/
  `WorkComposerMatcher`, ranking existente, `RemoteCatalogProvider` (`/api/search`).
- API no se convierte en catálogo: los candidatos quedan **embebidos por ítem**, no en
  una tabla global `works`.
- Este ADR **congela la arquitectura, no la implementación SQL**. El esquema concreto de
  tablas de `OpStore` (`resolution_sessions`, `provider_results`, `resolution_items`) y su
  ciclo de paginación se define en un paso posterior.
