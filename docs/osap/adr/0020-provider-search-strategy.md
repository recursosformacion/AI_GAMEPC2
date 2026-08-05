# ADR-0020 – Provider Search Strategy

## Estado

Aceptado.

## Contexto

OSAP orquesta varios proveedores (`ProviderOrchestrator` → `ProviderExecutionPlan`
→ `ProviderResultAggregator`). Antes de conectar proveedores reales (OMR, IMSLP)
hay que **congelar el comportamiento** de la orquestación para que no se rediscuta
en cada versión. Este documento define, de una vez, cómo se comporta el orquestador.
No cambia código: congela el comportamiento.

## Decisión

### 1. ¿Cuándo se detiene el Orchestrator?

La búsqueda se detiene cuando se cumplen **las dos** condiciones:

1. Al menos un proveedor devolvió resultados, **y**
2. La búsqueda está **satisfecha** (ver §5).

Si no se satisfacen, se continúa con el siguiente paso del plan hasta agotarlo.

### 2. ¿Cuándo merece la pena consultar un proveedor caro?

Los proveedores se ordenan por **coste de consulta** (`FREE → CHEAP → NORMAL →
EXPENSIVE`). Un proveedor más caro **solo se consulta** si ninguno más barato
satisfizo la búsqueda (por formato o dominio público requerido).

Regla: el coste nunca decide por sí solo; la **suficiencia** (§5) decide. Un
proveedor `EXPENSIVE` se consulta cuando la necesidad (p. ej. MusicXML editable) no
la cubren los `FREE`/`CHEAP`.

### 3. ¿Cuándo se reutiliza la caché?

- Se reutiliza una búsqueda **idéntica** (`SearchRequest` igual) ejecutada hace menos
  del TTL (por defecto **180 s**).
- Una respuesta de caché marca el resultado como `cached = true`; no se vuelve a
  consultar ningún proveedor.
- La caché **no** se usa para `provider_status` (debe reflejar el estado vivo).

### 4. ¿Cuándo se ejecuta en paralelo?

- **V2: secuencial.** El plan se ejecuta en orden, sin paralelismo.
- El paralelismo **se aplaza** hasta que la secuencialidad sea un cuello de botella
  medido. Solo se activará con un criterio explícito (p. ej. N proveedores de coste
  `FREE` y tiempo de búsqueda > umbral). No se añade paralelismo especulativo.

### 5. ¿Qué significa que una búsqueda está "satisfecha"?

Un proveedor es **suficiente** (satisface la búsqueda) cuando:

- **Formato**: no se pidió un formato concreto, **o** el formato pedido está entre
  los `formats` del proveedor (`CatalogCapabilities`).
- **Dominio público**: no se pidió `public_domain_only`, **o** el proveedor es
  `public_domain_only`.

Con resultados de un proveedor suficiente, la búsqueda termina: no se consultan
proveedores más caros.

### Regla general

```
plan = proveedores elegibles, ordenados por coste ascendente
para cada paso del plan:
    resultados = proveedor.search()
    si hay resultados y el proveedor es suficiente:
        DETENER
si no: CONTINUAR al siguiente paso
```

## Consecuencias

- El contrato (no el proveedor) decide cuándo basta: sin excepciones por proveedor.
- OMR (`EXPENSIVE`) solo se consulta cuando un proveedor más barato no satisface.
- El comportamiento queda congelado; cambios futuros requieren revisar este ADR,
  no parches puntuales en el orquestador.
- El paralelismo, la caché y la suficiencia tienen criterios definidos y verificables.
