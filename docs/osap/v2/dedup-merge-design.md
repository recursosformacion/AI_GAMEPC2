# Dedup / Merge — Diseño (V2.2.b)

> **Status: draft** (iteración 2 — se congelará antes de la implementación de V2.2.b).
>
> Parte de V2.2. Define cómo **fusionar** información de múltiples representaciones de
> una **misma** obra. No se escribe código hasta congelar este diseño.

## Principio rector

> **Merge nunca decide identidad. Solo consolida conocimiento.**

Merge no re-agrupa, no rompe `WorkGroup`, no decide si dos obras son la misma. La
identidad ya la decidió el `WorkMatcher`. Merge toma esa decisión como **dato de
entrada** y produce un descriptor consolidado y enriquecido.

## 1. Posición en el pipeline

```
… WorkMatcher → WorkGroup → Ranking → Selection → EvidenceCollector → EvidenceResult
                     │
                     ▼
                   Merge   ← V2.2.b (consolida el WorkGroup en un descriptor enriquecido)
```

Merge actúa **por obra** (`WorkGroup`): recibe las representaciones de la misma obra y
devuelve **un descriptor consolidado** más el registro de procedencia y conflictos.

## 2. ¿Qué significa realmente "fusionar"?

No es "decidir si son iguales" (eso es el Matcher). Es **consolidar conocimiento**:
a partir de N representaciones de la misma obra, producir **un** descriptor que:

- confirme la identidad que ya fue decidida;
- **enriquezca** los campos descriptivos con la mejor información disponible;
- **registre** de dónde viene cada valor (procedencia) y qué discrepancias existen.

Fusionar ≠ elegir "la mejor representación". Es elegir **el mejor valor por campo**,
con trazabilidad.

## 3. Contrato principal

```python
class IMergeEngine(ABC):
    def merge(self, group: WorkGroup, policy: MergePolicy) -> MergeResult: ...
```

Componente **puro, determinista, inmutable, sin IA y sin texto**; **independiente del
orden** de las representaciones de entrada.

### `MergeResult` (exactamente estos campos, nada más)

```python
@dataclass(frozen=True)
class MergeResult:
    merged_descriptor: MergedWorkDescriptor
    provenance: tuple[MergeProvenance, ...]
    conflicts: tuple[MergeConflict, ...]
    evidence: tuple[EvidenceItem, ...]
```

- `merged_descriptor` — el descriptor consolidado de la obra.
- `provenance` — por campo: valor elegido + fuente + estrategia + confidence.
- `conflicts` — discrepancias tipadas que Merge **no** resolvió.
- `evidence` — los hechos estructurados que Merge produce (ver §11).

## 4. `MergedWorkDescriptor` (tipo nuevo, no `WorkDescriptor`)

**No se reutiliza `WorkDescriptor`.** Un `WorkDescriptor` representa una
**representación**; un descriptor consolidado representa **conocimiento agregado de la
obra**. Son conceptos distintos. Un tipo separado evita que alguien haga algo
conceptualmente absurdo como:

```
WorkMatcher.match(merged_descriptor, work_descriptor)
```

`MergedWorkDescriptor` es un tipo **nuevo e inmutable** que expone:
- la **identidad confirmada** (los campos de identidad, tal y como los decidió el
  Matcher, ya confirmados);
- los **campos descriptivos enriquecidos** con su procedencia.

## 5. ¿Qué información nunca modifica?

Merge **nunca modifica** la identidad de la obra. Los campos que definen identidad:

- `work_id` (clave interna)
- catálogo (`catalogue_number`) y `opus` (como identidad)
- compositor (como identidad)
- título canónico (`canonical_title`) y aliases de identidad
- `work_authority_identifiers` (identificadores de obra)

Estos campos se **confirman** (si coinciden) o se **registran como conflicto**; nunca
se re-escriben ni se "fusionan" para producir un valor nuevo.

## 6. ¿Qué campos pueden enriquecerse?

Los campos **descriptivos** que no definen identidad:

- `subtitle`, `language` / idiomas
- `genres`, `instrumentation`, `voices`
- `creation_year`
- `key` (tonalidad; la transposición no es identidad)
- `notes`, `edition` / información de edición
- `aliases` adicionales (nombres alternativos no-identidad)

Enriquecer = tomar el valor **más completo y fiable** de entre las representaciones,
con su procedencia.

## 7. ¿Qué campos nunca deben fusionarse?

Los campos de **identidad** (sección 5) **nunca** se fusionan para producir un valor
nuevo. Además:

- `work_id` no se toca (identidad interna).
- `metadata` de representación no se fusiona (es específico de cada representación).
- Datos contradictorios de identidad → **conflicto**, no valor fusionado.

Regla: si dos fuentes difieren en un campo que, si se consolidara, cambiaría la
identidad de la obra → **conflicto**; Merge no elige.

## 8. Detección y tipo de conflictos

Un conflicto existe cuando **dos o más representaciones** aportan valores distintos
para un campo que se espera **consistente** dentro de una misma obra. Todo conflicto
tiene un **tipo** (para que Knowledge Mining detecte patrones):

```python
class MergeConflictType(Enum):
    IDENTITY_CONFLICT   # difieren en identidad (catálogo/compositor/título canónico)
    VALUE_CONFLICT      # difieren en un valor descriptivo (p. ej. creation_year)
    MISSING_DATA        # una fuente no aporta el campo
    AUTHORITY_CONFLICT  # difieren en identificadores de autoridad
    FORMAT_CONFLICT     # difieren en formato/edición
```

Todo conflicto se **expone** en `MergeConflicts`, con su tipo, los valores y las
fuentes; nunca se resuelve por azar.

## 9. `MergeProvenance` (trazabilidad por campo)

Cada valor consolidado debe responder a "¿por qué ganó IMSLP?" — no "porque sí". Por
eso cada `MergeProvenance` contiene:

- **campo** — qué campo se consolidó.
- **valor elegido** — el valor final.
- **fuente** — de qué representación/proveedor salió.
- **estrategia usada** — qué `MergeCriterion` ganó (ver §10).
- **confidence** — fuerza de la decisión (0..1).

```python
@dataclass(frozen=True)
class MergeProvenance:
    field: str
    value: object
    source: str
    strategy: MergeCriterion
    confidence: float
```

## 10. `MergePolicy` — criterios tipados (como el Ranking)

La **estrategia** (qué fuente gana) es **política**, no contrato. Usa criterios
**tipados** (`MergeCriterion`), igual que `RankingCriterion`:

```python
class MergeCriterion(Enum):
    SOURCE_AUTHORITY        # prioriza la fuente más fiable para ese campo
    FIELD_COMPLETENESS      # prioriza el valor más completo
    REPRESENTATION_CONFIDENCE  # prioriza la representación con mayor confidence
    MAJORITY                # el valor con más fuentes a favor
    NEWEST                  # la fuente más reciente
    MANUAL_PRIORITY         # prioridad manual explícita
```

```python
@dataclass(frozen=True)
class MergePolicy:
    enabled_criteria: tuple[MergeCriterion, ...]
    weights: dict[MergeCriterion, float]
```

El contrato solo dice **qué** se consolida y **cómo** se registra; **qué criterio gana**
es política (`MergePolicy`, configurable), sin tocar el contrato.

## 11. Integración con Evidence (exactamente igual que el resto)

Merge implementa `IEvidenceContributor` **exactamente igual** que Matcher, Ranking y
Selection:

```
MatchResult     → MatchEvidenceContributor
RankingResult   → RankingEvidenceContributor
SelectionResult → SelectionEvidenceContributor
MergeResult     → MergeEvidenceContributor
```

Así el `EvidenceCollector` **no tiene que saber nada** sobre Merge: recibe
`MergeResult → MergeEvidenceContributor.to_evidence()` como un contribuidor más. Cada
campo consolidado y cada conflicto produce un `EvidenceItem` (hechos estructurados, no
texto).

## 12. ¿Qué NO hace Merge?

- **No decide identidad** (ni crea ni rompe `WorkGroup`).
- No re-agrupa ni desagrupa representaciones.
- No resuelve conflictos de identidad por sí mismo (los expone).
- No elige "la mejor representación" como unidad.
- No usa IA, embeddings ni modelos.
- No consulta proveedores.
- No modifica las representaciones de entrada (inmutable).
- No modifica el núcleo congelado de V2.0/V2.1.
- No conoce `SearchRequest` ni el pipeline de resolución.
- No reutiliza `WorkDescriptor` como salida (usa `MergedWorkDescriptor`).

## 13. Preguntas de diseño resueltas

- **¿IMSLP y MusicBrainz discrepan?** → `MergeConflict` con `AUTHORITY_CONFLICT` /
  `VALUE_CONFLICT`, no decisión silenciosa. La discrepancia queda registrada con fuentes
  y tipo; el descriptor conserva el valor que la política decida, pero el conflicto es
  visible para el Matcher/Knowledge Mining.
- **¿Mejor catálogo pero peor título?** → Merge es **por campo**: no elige "la mejor
  fuente" globalmente, sino el mejor valor de **cada** campo con su procedencia. El
  catálogo de una fuente y el título de otra pueden coexistir en el descriptor.
- **¿Cómo se conserva la procedencia?** → `MergeProvenance` por campo (valor + fuente +
  estrategia + confidence); nunca se pierde el origen.
- **¿Independiente del orden de entrada?** → Sí: el resultado debe ser **conmutativo**
  (misma entrada en distinto orden → mismo `MergeResult`). El orden nunca altera el
  valor consolidado ni el conjunto de conflictos.
- **¿Cómo evitamos que Merge vuelva a decidir lo del Matcher?** → Los campos de
  identidad **nunca se fusionan** (solo se confirman o se marcan como conflicto). Merge
  opera exclusivamente sobre campos descriptivos; la identidad es **dato de entrada**.
- **¿Qué significa "mejor información"?** → No es global: es **por campo**. "Mejor" =
  el valor más completo/fiable para ese campo, definido por la **política**
  (`MergePolicy`), no por el contrato.
- **¿Reglas de contrato vs política?** → **Contrato**: `IMergeEngine.merge`,
  `MergeResult`, `MergedWorkDescriptor`, `MergeProvenance`, `MergeConflict` (+ tipo) y la
  contribución a Evidence. **Política**: qué criterio gana y sus pesos (`MergePolicy`).

## 14. Criterios de aceptación (V2.2.b)

- Documento congelado antes de implementar.
- `IMergeEngine.merge(group, policy) -> MergeResult` puro, determinista, inmutable e
  **independiente del orden**.
- `MergeResult` con exactamente: `merged_descriptor`, `provenance`, `conflicts`,
  `evidence`.
- `MergedWorkDescriptor` es un **tipo nuevo** (no `WorkDescriptor`).
- Identidad confirmada o marcada como conflicto; solo se enriquecen campos descriptivos.
- `MergeProvenance` con campo + valor + fuente + estrategia + confidence.
- `MergeConflict` tipado (`IDENTITY/VALUE/MISSING_DATA/AUTHORITY/FORMAT_CONFLICT`).
- `MergeCriterion` + `MergePolicy(enabled_criteria, weights)`; la estrategia es política.
- Merge implementa `IEvidenceContributor` igual que Matcher/Ranking/Selection
  (`MergeResult → MergeEvidenceContributor`).
- Tests previstos: enriquecimiento por campo, identidad no modificada, cada tipo de
  conflicto, procedencia correcta, independencia del orden, inmutabilidad,
  determinismo, contribución a Evidence.
