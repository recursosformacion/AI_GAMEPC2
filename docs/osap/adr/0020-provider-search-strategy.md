# ADR-0020 – Work Resolution Strategy

## Estado

Aceptado. **Revisado** para alinearse con V3.4 (Work Resolution, ADR-0030).

## Contexto

*(El fichero conserva su nombre `0020-provider-search-strategy.md` por continuidad de
referencias; el título refleja el contenido actual: resolución y enriquecimiento.)*

OSAP orquesta varios proveedores (`ProviderOrchestrator` → `ProviderExecutionPlan`
→ `ProviderResultAggregator`). La versión original congelaba una orquestación
**secuencial con early-stop** (detenerse al primer proveedor "suficiente").

Ese modelo es correcto para un **buscador de documentos**, pero entra en conflicto con la
filosofía de V3.4:

> **"El objetivo de OpenMusicRepository no es devolver una lista de archivos, sino
> identificar una obra musical con el mayor grado de confianza posible y ofrecer al
> usuario todas sus representaciones disponibles."**

La resolución de una obra **no puede depender de que un proveedor "barato" haya contestado
antes**. Si IMSLP responde un PDF y paramos, nunca descubrimos que OMR tenía MusicXML,
MIDI, MEI, versiones críticas, aliases, relaciones o metadata. Habríamos "resuelto" una
obra sin conocer todas sus representaciones.

## Decisión

La resolución se divide en **dos fases**:

### Fase 1 — Resolver la obra

La Fase 1 finaliza cuando el motor ha obtenido **la mejor resolución posible con la
información disponible**. El resultado puede ser:

- una **única obra** (Work Resolution), o
- un **conjunto ordenado de Matching Works** cuando persiste la ambigüedad.

```
Query
  ↓
Entity Resolution
  ↓
Matching Works  (si persiste la ambigüedad)
  ↓
Work Resolution (identificada)
```

No se busca un único formato: se busca **la obra**. No siempre hay una "identificación
inequívoca" (Ave Verum, Requiem, Missa Brevis, Sonata No. 1, obras sin catálogo...); en
esos casos se presenta un conjunto ordenado de Matching Works y el usuario elige.

### Fase 2 — Enriquecer la resolución

**Todos los proveedores compatibles con la obra identificada pueden consultarse** para
incorporar representaciones, metadatos, relaciones y evidencias adicionales.

El enriquecimiento puede realizarse en **segundo plano** (paralelo) y **actualizar la Work
Resolution progresivamente** (Progressive Disclosure):

```
0.6 s  usuario ve  Ave Verum
2 s    aparece     MusicXML
3 s    aparece     MIDI
4 s    aparece     Relationships
5 s    aparece     Evidence ampliada
```

### ¿Cuándo termina la Fase 2?

> **La Fase 2 finaliza cuando todos los proveedores planificados han respondido, han
> agotado su tiempo máximo de espera o han fallado. La ausencia o fallo de un proveedor
> no invalida la Work Resolution ya obtenida.**

Ninguna resolución queda en "Loading" indefinidamente por un proveedor lento o que no
responde.

### ¿Cuándo se detiene?

- **Fase 1**: se detiene al identificar la obra.
- **Fase 2**: se consultan **todos** los proveedores relevantes; no se detiene porque un
  proveedor "satisfaga" un formato.

### ¿Cuándo se ejecuta en paralelo?

- **Fase 2 (enriquecimiento)**: paralelo, en segundo plano. El plan se ejecuta sobre todos
  los proveedores compatibles con la obra.
- La caché se reutiliza para búsquedas idénticas (TTL 180 s); no se usa para
  `provider_status`.

### Ordenación del plan (estrategia configurable)

> **El `ProviderExecutionPlan` ordena los proveedores según una estrategia configurable
> (coste, prioridad, capacidades, disponibilidad o una combinación). La implementación por
> defecto usa el coste como criterio de planificación para minimizar latencia, pero el
> **algoritmo de resolución no depende de ese criterio**.**

Así, el ADR no obliga para siempre al coste; si mañana un proveedor local debe ejecutarse
antes por latencia, no se rompe el ADR; el algoritmo permanece estable.

### OMR / OpenMusicRepository — un proveedor con capacidades adicionales

Algunos proveedores pueden **declarar capacidades adicionales** (metadata, relationships,
aliases, evidence, etc.). Durante la **Fase 2** el orquestador consulta **todos los
proveedores compatibles** y **fusiona toda la información disponible**. OMR es actualmente
uno de esos proveedores, pero **el comportamiento no depende de un proveedor concreto**:

- hoy funciona con OMR;
- mañana podría existir otro proveedor con las mismas capacidades;
- el algoritmo sigue siendo **genérico** (sin excepciones por proveedor).

### Regla general

```
# Fase 1 — Resolver
plan = proveedores elegibles, ordenados por la estrategia configurable del plan
para cada paso del plan:
    resultados = proveedor.search()
    si se logra la mejor resolución posible con la información disponible:
        DETENER
        → única obra (Work Resolution) o conjunto ordenado de Matching Works

# Fase 2 — Enriquecer (paralelo, segundo plano)
para cada proveedor compatible con la obra identificada:
    resultados = proveedor.search()
    merge + representaciones + metadata + relaciones + evidence
actualizar la Work Resolution progresivamente
```

### La Work Resolution es un recurso vivo

> **La incorporación de nueva información durante la Fase 2 puede actualizar
> representaciones, metadatos, relaciones, evidencias y el nivel de confianza, sin
> alterar la identidad de la obra ya resuelta.**

No se crea una nueva resolución cada vez que aparece un proveedor nuevo: la misma
Work Resolution se **enriquece** (Work Resolution as Knowledge Hub).

## Consecuencias

- La resolución **no depende** de que un proveedor barato conteste antes.
- Una Work Resolution **reúne todas las representaciones** disponibles (no solo la primera).
- La Fase 1 puede terminar en una **única obra** o en un **conjunto ordenado de Matching
  Works** cuando persiste la ambigüedad (alineado con la UX `Search → Matching Works →
  Work Resolution`).
- El **enriquecimiento en segundo plano** (Fase 2) preserva el rendimiento (Progressive
  Disclosure) y **actualiza la resolución viva** sin cambiar su identidad.
- El comportamiento es **genérico** (proveedores con capacidades adicionales de metadata,
  relationships, aliases, evidence); **sin excepciones por proveedor concreto**.
- La Fase 1 sigue usando orden por coste para una resolución rápida.
- Este ADR queda alineado con ADR-0030 (Work Resolution); cambios futuros requieren
  revisar este ADR, no parches puntuales en el orquestador.
