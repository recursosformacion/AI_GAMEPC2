# Search Engine — Diseño (V2.1)

> **Status: draft** (se congelará antes de la implementación de V2.1).
>
> Cuarto documento fundamental del proyecto, junto a:
> 1. `docs/osap/v2/architecture-audit.md` (Auditoría arquitectónica)
> 2. `ROADMAP.md`
> 3. `docs/osap/v2/provider-contract.md`
>
> La V2.1 **no empieza implementando**: empieza con este diseño estable. Solo cuando
> este documento esté estable se escribe código. El núcleo (V2.0) queda **congelado**;
> el Search Engine se construye **sobre** él, adaptándose, sin modificarlo.

## Objetivo: Search Intelligence (no infraestructura)

**El Search Engine ya existe.** Hoy el flujo real ya es un motor de búsqueda:

```
SearchRequest
   → ProviderOrchestrator
   → Providers
   → Aggregator
   → WorkGroups
```

Eso **ya es** un motor de búsqueda. Lo que falta no es construirlo, sino hacerlo
**inteligente**. Por eso V2.1 se entiende mejor como **Search Intelligence** (o
**Search Quality**): pasamos de infraestructura a **algoritmos**. El nombre público
puede seguir siendo "V2.1"; lo que cambia es la filosofía — ya no añadimos piezas,
mejoramos las decisiones.

### División V2.1

| Subversión | Responsabilidad | No es infraestructura, es... |
|------------|-----------------|------------------------------|
| **V2.1.1 Normalización** | `Lexicon`, catálogos, nombres, acentos, transliteraciones | Algoritmos de convergencia textual |
| **V2.1.2 Matching** | `WorkMatcher`, `WorkMerge`, coincidencias, puntuación | Algoritmos de identidad |
| **V2.1.3 Ranking** | pesos medidos, ranking de obras, paginación, filtros | Algoritmos de ordenación |

Cada subversión introduce una responsabilidad nueva y bien delimitada, **sin reabrir
el núcleo congelado**. Si un proveedor futuro obliga a ampliar algo, el cambio será
localizado y justificable, no una revisión de arquitectura.

## 1. ¿Qué significa "buscar una obra"?

Buscar es pasar de **texto/signos** (lo que escribe el usuario) a **identidad musical**
(lo que OSAP entiende). Una obra tiene:

- **Identidad** (`WorkDescriptor`): título, compositor, catálogo, opus, tonalidad,
  género, instrumentación, movimientos.
- **Representaciones** (`CandidateRepresentation`): formas concretas de esa obra
  (PDF, MusicXML, MIDI...) que aportan los proveedores.

Buscar **no** es resolver. Buscar produce candidatos e identidades; resolver elige una
representación concreta para entregar. La búsqueda vive en la entrada del pipeline;
la resolución, al final.

## 2. Búsqueda libre vs. resolución

| | Búsqueda libre | Resolución |
|---|---|---|
| Entrada | `SearchRequest` (términos sueltos) | `ResolveRequest` → `WorkDescriptor` |
| Salida | candidatos + obras | representación elegida + evidencia |
| Objetivo | "¿qué hay?" | "quiero esta obra" |
| Orquestador | `ProviderOrchestrator.search` | pipeline completo (orchestrator → aggregator → ranking → evidence) |

Regla (ADR-0019): la búsqueda de OSAP es de **dos fases** — primero se busca, luego se
resuelve. Nunca se salta a un proveedor con preguntas complejas.

## 3. ¿Cómo se combinan los resultados de varios proveedores?

El `ProviderOrchestrator` consulta los proveedores (todos iguales) según un
`ProviderExecutionPlan` (coste, caché, parada temprana — ver ADR-0020) y el
`ProviderResultAggregator`:

1. **Deduplica** duplicados triviales (mismo proveedor + `remote_id` / `checksum`).
2. **Agrupa** por `WorkDescriptor` en `WorkGroup` (una obra → varias representaciones).
3. Entrega una colección **homogénea** al ranking.

Los resultados de distintos proveedores se combinan **a nivel de obra**, no a nivel de
proveedor: dos representaciones de la misma obra de fuentes distintas viven en el
mismo `WorkGroup`.

## 4. ¿Cómo se ordenan? Pesos por campo

El ranking ordena candidatos/obras con criterios **configurables** (`RankingConfig`) e
independientes (`ScoreRanking`). Pesos propuestos para V2.1 (a medir sobre OMR+IMSLP):

| Campo | Qué aporta | Peso sugerido |
|-------|------------|---------------|
| Título | coincidencia de identidad | Alto |
| Compositor | coincidencia de identidad | Alto |
| Catálogo (BWV, KV) | coincidencia exacta | Alto |
| Género / Instrumentación / Voces | filtro descriptivo | Medio |
| Tonalidad | filtro | Medio |
| Formato pedido | `desired_format` | Alto (corta) |
| Dominio público / licencia | preferencia | Medio |
| Proveedor / local | disponibilidad | Bajo |
| Confianza / calidad / completitud | señal de fuente | Medio |

Regla: los pesos son **configurables y medibles**; en V2.1 se ajustan con datos reales
de OMR e IMSLP, no por intuición.

## 5. ¿Qué hace OSAP cuando una búsqueda devuelve cientos de candidatos?

Principio: **el usuario ve obras, no candidatos.** Ante cientos de representaciones:

1. **Agrupar** por `WorkDescriptor` (el agregador ya lo hace) → cientos de candidatos
   se convierten en decenas de obras.
2. **Rankear obras** por identidad (exactitud de título/compositor/catálogo) y no por
   ruido.
3. **Acotar**: el usuario puede filtrar por compositor, formato, instrumentación,
   licencia (los `SearchRequest` ya los soportan).
4. **Paginación** a nivel de obra (no de candidato).

El objetivo no es mostrar 500 resultados, sino la **lista de obras más relevantes**
sobre las que el usuario puede decidir.

## 6. V2.1.1 — Normalización (Lexicon, catálogos, nombres)

Normalizar es hacer que **distintas formas converjan a la misma forma canónica**.

- **Catálogos**: `BWV 846`, `BWV846`, `BWV-846` → el mismo catálogo. Igual `K618`,
  `KV618`, `K.618`, `Köchel 618`, `Köchel 618`.
- **Nombres**: `W.A. Mozart`, `Wolfgang Amadeus Mozart`, `Mozart`,
  `Mozart, Wolfgang Amadeus` → el mismo compositor.
- **Términos equivalentes**: `Sinfonía`/`Symphony`/`Sinfonie`/`Symphonie`;
  `No.`/`Nr.`/`Nº`/`Number`; `K`/`KV`/`Köchel`.
- **Acentos y transliteraciones** sobre el `Lexicon` existente.

Aquí el `Lexicon` empieza a **crecer** con conocimiento musicológico (reglas
explicables, sin modelos).

## 7. V2.1.2 — Matching (WorkMatcher / WorkMerge)

El `WorkMatcher` debe pasar de un matcher simple (title/composer/catalogue) a un
**matcher real**:

```
Ave Verum Corpus
Ave Verum
Ave Verum K618
K618
KV618
K.618
```
→ todo debe acabar siendo el mismo `WorkDescriptor` (o candidatos a la misma obra).

Junto a `WorkMerge`, decide con **puntuación explicable** cuándo dos representaciones
son la misma obra.

## 8. V2.1.3 — Ranking (pesos medidos)

Ahora sí tiene sentido **medir**, no decidir. Ejemplo:

```
Buscar:  Mozart · Ave Verum   (IMSLP + OMR)
Medir:   ¿title pesa demasiado? ¿composer pesa poco? ¿catalogue ayuda mucho?
```

Los pesos (`RankingConfig`/`ScoreRanking`) se ajustan **con datos reales** de
OMR+IMSLP, no por intuición. Incluye ranking de obras, paginación y filtros.

## 9. Componentes implicados (V2.1)

- `WorkMatcher` — **matcher real** de identidad entre obras (V2.1.2).
- `WorkGrouper` / `WorkMergeService` — agrupar representaciones en una obra.
- `Lexicon` — normalización musical creciente: catálogos, nombres, términos (V2.1.1).
- `ProviderOrchestrator` + `ProviderResultAggregator` — consulta y unión (ya existe).
- `IRankingEngine` (`ScoreRanking`) — ordenar por pesos **medidos** (V2.1.3).
- `SearchRequest` — entrada; `WorkDescriptor` — unidad de salida.

## 10. Qué NO hace el Search Intelligence

- No resuelve (eso es el pipeline de resolución).
- No introduce **IA, embeddings, LLM, búsqueda semántica ni vectores**: todavía no
  hacen falta. Primero se agota por completo el **conocimiento musicológico** (reglas
  explicables).
- No modifica el núcleo congelado de V2.0.
- No añade campos exclusivos por proveedor.

## 8. Criterios de aceptación (V2.1)

- El documento queda **congelado** antes de implementar.
- `osap search` consistente entre OMR, IMSLP, OpenScore y PDMX.
- Búsqueda correcta en acentos, mayúsculas y parcial.
- Cientos de candidatos → lista de obras relevante y acotable.
- Medidas de peso validadas con datos reales (no intuición).
