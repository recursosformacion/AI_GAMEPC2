# Provider Contract — V2.0 (Freeze Public Contracts)

> **Status: core · frozen en V2.0**
>
> Especificación definitiva del contrato de proveedores de OSAP. Tercer documento
> fundamental del proyecto, junto a `docs/architecture-audit.md` y `ROADMAP.md`.
>
> Este documento **no se adapta a los proveedores**: los proveedores se adaptan a
> este contrato.

## Regla de congelación (obligatoria)

A partir de V2.0, **cualquier nuevo proveedor deberá implementar este contrato sin
excepciones**.

- El contrato **no** se adapta al proveedor; el proveedor se adapta al contrato.
- Un proveedor no puede exigir campos nuevos ni ignorar campos obligatorios.
- Si un proveedor futuro necesita algo que no está aquí, se modifica el contrato
  **por revisión de versiones**, no por excepción puntual. La regla vale para OMR,
  IMSLP, MuseScore, CPDL, OpenScore, Filesystem, PDMX y cualquier proveedor futuro.

---

## Principios que gobiernan el contrato

1. **Provider autonomy** — cada proveedor describe únicamente lo que conoce; nunca
   adapta resultados para favorecer un ranking, nunca fusiona obras, nunca decide
   cuál es la mejor representación.
2. **Todos los proveedores son iguales** (ADR-0018) — no hay camino especial para
   ningún proveedor, incluido OMR.
3. **Buscar ≠ resolver** — `SearchRequest` y `ResolveRequest` son contratos distintos.
4. **OSAP piensa y decide** — la lógica de negocio (ranking, fusión, evidencia,
   selección) vive en el núcleo de OSAP.

### Interfaz canónica

```python
class ICatalogProvider(ABC):
    provider_id -> ProviderId
    search(request: SearchRequest) -> tuple[CandidateRepresentation, ...]
    resolve(work: WorkDescriptor) -> CandidateRepresentation | None
    download(candidate, output_format=None) -> AcquisitionResult
    metadata() -> CatalogInfo
    capabilities() -> CatalogCapabilities
```

---

## Contrato 1 — `SearchRequest`

Una **búsqueda**. Puede pedir varios términos a la vez sin intención de resolver
una obra concreta.

Campos (inmutables):
- `query` — texto libre (opcional)
- `title` — título (opcional)
- `composer` — compositor (opcional)
- `catalogue` — catálogo, p. ej. `BWV`, `KV` (opcional)
- `instrumentation` / `voices` — instrumentación / voces (opcional)
- `genre` — género (opcional)
- `key` — tonalidad (opcional)
- `year_range` — rango de años (opcional)
- `format` — `OutputFormat` deseado (opcional)
- `min_quality` — calidad mínima (opcional)
- `public_domain_only` — bool (opcional)
- `online` / `offline` — modo de red
- `allowed_providers` / `excluded_providers` — (opcional)

Semántica: *"devuélveme candidatos que coincidan con esto"*. No implica resolver.

---

## Contrato 2 — `ResolveRequest`

*"Quiero esta obra concreta."* Contiene la **identidad** de la obra, no texto libre.

Campos:
- `work` — `WorkDescriptor` (identidad normalizada) **o** `work_id`
- `format` / `min_quality` / `public_domain_only` (opcional)
- `online` / `offline`

Regla: nunca un simple string como `"Mozart Ave Verum"`. Para llegar aquí, OSAP ya
ha buscado.

---

## Contrato 3 — `Work` (`WorkDescriptor`)

Identidad pura de una obra: título, compositor, movimiento, géneros, instrumentación
esperada. **Sin formatos ni archivos.**

Es la unidad sobre la que OSAP piensa y sobre la que se agrupan las
`CandidateRepresentation` de distintos proveedores.

---

## Contrato 4 — `Representation` (`CandidateRepresentation`)

Forma concreta de una obra encontrada en un proveedor. Es un objeto **frozen** con:

| Campo | Tipo | Semántica |
|-------|------|-----------|
| `candidate_id` | `CandidateId` | identidad del candidato |
| `work_descriptor` | `WorkDescriptor` | la obra que representa |
| `provider_id` | `ProviderId` | proveedor que la ofrece |
| `format` | `OutputFormat` | formato |
| `origin` / `remote_id` | `str \| None` | dónde está |
| `license` / `public_domain` | `str \| bool` | licencia |
| `quality` | `QualityLevel` | calidad (§8) |
| `confidence` | `Confidence` | confianza (§8) |
| `completeness` | 0–1 | completitud (§8) |
| `download_url` / `local_path` | `str \| None` | acceso |
| `edition` | `str \| None` | edición |
| `size_bytes` / `checksum` | `int \| str \| None` | integridad |
| `downloadable` / `manual_download` | `bool` | modo de acceso |
| `rating` / `notes` / `metadata` | varios | adicional |

Regla: un proveedor devuelve representaciones **completas y verificadas**; no
rellena campos que no conoce.

---

## Contrato 5 — `AcquisitionResult`

Resultado de `download()`:

| Campo | Semántica |
|-------|-----------|
| `provider_id` | proveedor |
| `source` | `MusicalSource` obtenido |
| `confidence` | confianza del resultado |
| `processing_time` | duración |
| `format` | formato |
| `quality_level` | calidad resultante |
| `warnings` / `diagnostics` | avisos y diagnóstico |

---

## Contrato 6 — `CatalogCapabilities`

Qué puede hacer y qué puede buscar un proveedor. El orquestador lo usa para decidir
a quién consultar; **sin listas de proveedores hardcodeadas**.

Capacidades de operación:
- `supports_search` — puede buscar
- `supports_download` — puede descargar
- `supports_streaming` — puede transmitir sin descargar todo
- `supports_reference` — solo ofrece referencias (sin descarga)
- `offline` — funciona sin red
- `formats` — formatos que ofrece
- `public_domain_only` — solo dominio público
- `requires_auth` — necesita credenciales
- `cost_level` — `CostLevel` (§7)
- `metadata` — adicional

Campos de búsqueda soportados:
- `supports_title`
- `supports_composer`
- `supports_catalogue`
- `supports_instrumentation`
- `supports_genre`
- `supports_key`
- `supports_year`

> Ejemplo: el usuario busca por catálogo `BWV`; no se consulta a un proveedor que
> no soporta catálogo. Ahorra tiempo y consultas.

---

## Contrato 7 — `CostLevel` (coste de consulta)

El coste **de consulta** de un proveedor. No es solo dinero: es dinero, cuota,
limitación de API o latencia. El orquestador solo necesita saber si consultar ese
proveedor es caro, **no por qué**.

| Nivel canónico | Significado | Ejemplos |
|----------------|-------------|----------|
| `FREE` | Sin coste relevante | Filesystem, PDMX local, OpenScore (GitHub público), IMSLP |
| `CHEAP` | Coste/límite bajo | APIs con límite generoso |
| `NORMAL` | Coste moderado | APIs con cuota moderada |
| `EXPENSIVE` | Caro o muy limitado | OMR (infraestructura de pago), APIs de pago |

> Nota de alineación V2.0: el `CostLevel` actual del dominio es
> `FREE/LOW/MEDIUM/HIGH`; se alinea a la nomenclatura canónica
> `FREE/CHEAP/NORMAL/EXPENSIVE`.

---

## Contrato 8 — Quality: `confidence`, `quality`, `completeness`

Separación canónica (no se mezclan):

- **`confidence`** — *¿es esta obra?* Seguridad de que el candidato coincide con la
  identidad de `WorkDescriptor`. Escala 0–1.
- **`quality`** — *¿qué calidad tiene?* Calidad de la representación en sí
  (`QualityLevel`: `UNREADABLE → PARTIAL_STRUCTURE → BASIC_MELODY → FULL_NOTATION →
  HUMAN_VALIDATED`).
- **`completeness`** — *¿está completa?* Qué completa está la obra en esa
  representación (movimientos, instrumentación, edición). Escala 0–1.

Regla: los tres se normalizan a una escala común (0–1 / niveles ordenados) para que
el `ProviderResultAggregator` compare proveedores heterogéneos.

---

## Contrato 9 — `ResourceBundle`

Agrupación de **todos los recursos** que OSAP necesita u obtiene para una obra:
representaciones, datasets, modelos, diccionarios, cachés, referencias. El
`ResourceManager` decide qué instalar; el proveedor solo declara lo que conoce.

---

## Contrato 10 — `Evidence`

Justificación **trazable** de por qué se eligió una representación: fuente, calidad,
confianza, licencia, checksum, proveedor, motivo del ranking. Cada `ResolveResult`
expone la evidencia de su elección.

---

## Contrato 11 — `ProviderExecutionPlan` (contrato, no implementación)

Documento de comportamiento de la orquestación, definido como **contrato** (no se
congela una implementación). Un plan responde a:

- ¿A quién se pregunta primero y después?
- ¿Se paraleliza? ¿Se espera? ¿Se cancela?
- ¿Cuándo se da la búsqueda por terminada?
- ¿Cuándo merece la pena consultar un proveedor lento (según `CostLevel`)?
- ¿Cuándo se reutiliza una búsqueda anterior (caché)?

---

## Contrato 12 — `ProviderOrchestrator` (concepto)

Componente que decide el plan de ejecución y agrega resultados. Es un **concepto**
de la V2, no una implementación congelada aquí:

```
ProviderOrchestrator
    ↓  decide
ProviderExecutionPlan
    ↓  consulta proveedores (todos iguales)
ProviderResultAggregator   ← normaliza y une resultados
    ↓
ranking + evidence → selección
```

El orquestador usa `CatalogCapabilities` (incl. `cost_level` y campos de búsqueda)
para decidir. La lógica de decisión vive en OSAP, nunca en el proveedor.

---

## Modelo mental

```
OSAP
  search(SearchRequest)   -> tuple[CandidateRepresentation, ...]
  resolve(WorkDescriptor) -> CandidateRepresentation | None
  download(candidate)     -> AcquisitionResult
  capabilities()          -> CatalogCapabilities (cost_level + campos de búsqueda)
  quality                 -> confidence | quality | completeness
```
```
consulta IMSLP
consulta MuseScore
consulta OMR
consulta PDMX
consulta Filesystem
...
```
Todos son `ICatalogProvider`. Nada más.
