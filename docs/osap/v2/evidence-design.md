# Evidence definitivo — Diseño (V2.2.a)

> **Status: draft** (iteración 1 — se congelará antes de la implementación de V2.2.a).
>
> Parte de V2.2. Objetivo: que **cada decisión del sistema sea explicable** —
> no solo "esta es la mejor obra", sino "esta es la mejor obra **porque...**" y
> "esta es la mejor representación **porque...**". No se escribe código hasta congelar.

## Principio rector

> **Evidence no genera frases. Genera hechos.**

El sistema produce `EvidenceItem` **tipados** (hechos estructurados). El renderer
decidirá después si eso se convierte en texto, JSON o HTML. El dominio no queda atado
al lenguaje natural (misma decisión que en Canonicalizer/WorkMatcher/Ranking).

## 1. Posición en el pipeline

```
… WorkMatcher → WorkGroup → Ranking → Selection → EvidenceCollector → EvidenceResult
        │            │          │           │              │
      MatchResult  RankingResult  SelectionResult          │
        └────────────┴────────────┴────────────┘────────────┘
```

Cada decisión del sistema produce un resultado tipado; el **EvidenceCollector** los
agrupa en una **evidencia uniforme**.

## 2. ¿Quién recoge la evidencia? (`EvidenceCollector`)

Ya no se habla de un "Evidence Engine" monolítico: hay un **EvidenceCollector** que
recibe:

- `MatchResult` (del WorkMatcher)
- `RankingResult` (del Ranker)
- `SelectionResult` (de la selección de representación)

y devuelve un `EvidenceResult`.

## 3. Tipos del contrato

### `EvidenceSource`

```python
class EvidenceSource(Enum):
    MATCHER = "matcher"
    RANKER = "ranker"
    SELECTION = "selection"
```

### `EvidenceCode` (estable)

```python
class EvidenceCode(Enum):
    # matcher
    CATALOGUE_MATCH = "catalogue_match"
    COMPOSER_MATCH = "composer_match"
    TITLE_MATCH = "title_match"
    WORK_AUTHORITY_MATCH = "work_authority_match"
    KEY_MATCH = "key_match"
    # ranker
    RELEVANCE = "relevance"
    QUALITY_CONFIDENCE = "quality_confidence"
    QUALITY_COMPLETENESS = "quality_completeness"
    PREFERRED_FORMAT = "preferred_format"
    PREFERRED_LICENSE = "preferred_license"
    COVERAGE = "coverage"
    # selection
    SELECTED_REPRESENTATION = "selected_representation"
```

### `EvidenceStrength` (fuerza/importancia de la evidencia)

No toda la evidencia pesa igual: un `WORK_AUTHORITY_MATCH` es mucho más fuerte que un
`PREFERRED_FORMAT`, aunque ambos tengan `score = 1.0`. No es para calcular, es para
**explicar**.

```python
class EvidenceStrength(Enum):
    CRITICAL = "critical"
    STRONG = "strong"
    NORMAL = "normal"
    WEAK = "weak"
```

### `EvidenceField` (un dato del hecho, tipado)

```python
@dataclass(frozen=True)
class EvidenceField:
    name: str
    value: object
```

### `EvidenceItem` (un hecho)

```python
@dataclass(frozen=True)
class EvidenceItem:
    source: EvidenceSource
    code: EvidenceCode
    score: float                # 0..1
    strength: EvidenceStrength = EvidenceStrength.NORMAL
    fields: tuple[EvidenceField, ...] = ()
```

```python
EvidenceItem(
    source=EvidenceSource.MATCHER,
    code=EvidenceCode.CATALOGUE_MATCH,
    score=1.0,
    fields=(EvidenceField("catalogue", "KV 618"),),
)
EvidenceItem(
    source=EvidenceSource.RANKER,
    code=EvidenceCode.PREFERRED_FORMAT,
    score=1.0,
    fields=(EvidenceField("format", "musicxml"),),
)
```

Sin `dict[str, …]` dinámicos: `fields` es una tupla tipada de `EvidenceField`.

### `EvidenceSummary` (VO explícito)

```python
@dataclass(frozen=True)
class EvidenceSummary:
    matcher_score: float
    ranking_score: float
    selection_score: float
    overall_score: float
```

### `EvidenceResult`

```python
@dataclass(frozen=True)
class EvidenceResult:
    items: tuple[EvidenceItem, ...]
    summary: EvidenceSummary
    overall_score: float   # agregación global (no "confidence" del matcher)
```

`items` = colección de `EvidenceItem` tipados. `summary` (VO) y `overall_score` son
derivados del `EvidenceCollector`. El agregado global se llama **`overall_score`** para
no confundirlo con la confianza del matcher.

## 4. Contrato (desacoplado)

El Collector **no conoce** `MatchResult`/`RankingResult`/`SelectionResult`: conoce
**evidencia**. Cada productor implementa una interfaz común:

```python
class IEvidenceContributor(ABC):
    def to_evidence(self) -> tuple[EvidenceItem, ...]: ...

class IEvidenceCollector(ABC):
    def collect(self, contributors: tuple[IEvidenceContributor, ...]) -> EvidenceResult: ...
```

`Matcher`, `Ranking` y `Selection` implementan `IEvidenceContributor` (`to_evidence`).
Añadir un productor nuevo no cambia la interfaz del Collector.

Componente **puro, determinista, sin IA y sin texto**: solo agrega hechos.

## 5. Relación con el `Evidence` existente (V2.0.4)

Ya existe un `Evidence`/`EvidenceEngine` (por representación, en `domain/evidence.py`).
El `EvidenceCollector` lo **unifica**:
- Los `EvidenceReason` del `Evidence` actual se convierten en `EvidenceItem` con
  `source=EvidenceSource.SELECTION`.
- El `EvidenceCollector` suma los hechos del Matcher, del Ranker y de la Selección en
  un único `EvidenceResult`.
- El renderer (futuro) transforma `EvidenceItem` en texto/JSON/HTML o `Evidence`
  heredado, sin tocar el dominio.

`domain/` y `ports/` son **API pública congelada**: evolucionar el `Evidence` requiere
un ADR (V2.2.a lo contempla al unificarlo bajo `EvidenceCollector`).

## 6. Qué NO hace el EvidenceCollector

- No genera texto, HTML ni JSON (eso es el renderer).
- No decide (no elige obra ni representación).
- No usa IA.
- No modifica los resultados de entrada de los `IEvidenceContributor`.
- No modifica el núcleo congelado de V2.0/V2.1.

## 7. Criterios de aceptación (V2.2.a)

- Documento congelado antes de implementar.
- `IEvidenceCollector.collect(contributors)` puro y determinista → `EvidenceResult`.
- `EvidenceItem(source, code, score, strength, fields)` tipado; `fields` es
  `tuple[EvidenceField, ...]` (sin `dict[str, …]`); `EvidenceSource`/`EvidenceCode`/
  `EvidenceStrength` como enums.
- `EvidenceSummary` como VO (`matcher_score`, `ranking_score`, `selection_score`,
  `overall_score`); el agregado global es `overall_score`.
- `Matcher`, `Ranking` y `Selection` implementan `IEvidenceContributor`; el Collector
  no conoce sus resultados concretos.
- Cada `MatchReason`/`RankingReason` produce exactamente un `EvidenceItem`.
- La selección alimenta la evidencia de la representación elegida.
- Renderer separado (texto/JSON/HTML) como trabajo posterior; el dominio solo hechos.
- Tests: mapeo contribuidores→items, `EvidenceStrength`, agregación de `EvidenceSummary`/
  `overall_score`, determinismo, inmutabilidad de los resultados de entrada.

## 8. V3 (idea, no ahora): `EvidenceGraph`

En V3 el resultado ya no será una lista: será un **grafo de evidencia**:

```
Matcher ──► EvidenceItem ─┐
Ranking ──► EvidenceItem ─┼─► EvidenceGraph ──► Renderer
Selection ► EvidenceItem ─┘
```

Pero eso pertenece a V3; V2.2.a entrega `EvidenceResult` (lista tipada).
