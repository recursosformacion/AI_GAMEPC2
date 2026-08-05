# Ranking de obras — Diseño (V2.1.3)

> **Status: draft** (iteración 3 — se congelará antes de la implementación de V2.1.3).
>
> Parte del Search Intelligence (V2.1). Define **qué** se rankea, **qué** devuelve y
> **cómo** se puntúa. No se escribe código hasta congelar este diseño.

## Principio rector

> **El Ranking nunca cambia la identidad de una obra; únicamente decide el orden en
> que se presentan las alternativas.**

- **WorkMatcher** → decide si A y B representan la **misma** obra.
- **Ranking** → decide **cuál de las obras ya identificadas aparece antes**.

## 1. Contrato uniforme con V2.1.2

| WorkMatcher (V2.1.2) | Ranking (V2.1.3) |
|----------------------|-------------------|
| `MatchField` (Enum) | `RankingCriterion` (Enum) |
| `MatchReason` | `RankingReason` |
| `MatchResult` | `RankingResult` (+ `RankingScore`) |
| `MatchingConfig` | `RankingConfig` |

Mismos principios: **tipos fuertes, sin `str`, sin `dict[str, …]`, todo renderizable,
todo explicable, todo determinista**.

## 2. Posición en el pipeline

```
texto → Tokenizer → Lexicon → Canonicalizer → WorkMatcher → WorkGroup → Ranking → Evidence
```

El Ranking recibe **obras ya agrupadas** (`WorkGroup`) y devuelve un **orden**. Nunca
re-agrupa ni cambia la identidad de las obras.

## 3. ¿Qué se rankea? (Obras, no candidatos)

| Nivel | Componente | Decide |
|-------|-----------|--------|
| **Obra** (`WorkGroup`) | Ranking (V2.1.3) | orden de aparición de las obras |
| **Representación** (dentro) | Evidence + selección | qué representación se entrega |

## 4. Sin ejes fijos: todo son criterios

No se programan tres conceptos especiales (`relevance`/`quality`/`preference`). Cada
criterio pertenece a una **familia** por su nombre, y el `score` total **sale solo** de
la suma de criterios:

```python
class RankingCriterion(Enum):
    RELEVANCE_TITLE = "relevance_title"
    RELEVANCE_COMPOSER = "relevance_composer"
    RELEVANCE_CATALOGUE = "relevance_catalogue"
    QUALITY_CONFIDENCE = "quality_confidence"
    QUALITY_COMPLETENESS = "quality_completeness"
    PREFERENCE_FORMAT = "preference_format"
    PREFERENCE_LICENSE = "preference_license"
    PREFERENCE_PROVIDER = "preference_provider"
    PREFERENCE_LOCALITY = "preference_locality"
    COVERAGE = "coverage"
```

Un renderer puede agrupar por familia ("Relevance total", "Quality total",
"Preference total") **derivándolo** de los `RankingReason`, sin que el dominio lo
almacene.

## 5. Tipos del contrato

### `RankingReason` (totalmente estructurado)

```python
@dataclass(frozen=True)
class RankingReason:
    criterion: RankingCriterion
    field_score: float    # 0..1 (cuánto cumple este criterio)
    weight: float         # peso configurado
    contribution: float   # field_score × weight (explica exactamente el 0.38)
```

Ejemplo: `criterion=QUALITY_CONFIDENCE, field_score=0.95, weight=0.40,
contribution=0.38`.

### `RankingScore`

```python
@dataclass(frozen=True)
class RankingScore:
    work: WorkGroup
    score: float                    # Σ contribution, normalizado
    reasons: tuple[RankingReason, ...]
    # NO almacena relevance/quality/preference: se derivan de los reasons
```

### `RankingResult`

```python
@dataclass(frozen=True)
class RankingResult:
    order: tuple[RankingScore, ...]              # obras ordenadas (mayor → menor)
    context: RankingContext
    evaluated_criteria: tuple[RankingCriterion, ...]  # qué se evaluó (como compared_fields)
```

`evaluated_criteria` permite al Knowledge Mining saber "esta búsqueda no usó LICENSE /
PROVIDER / QUALITY", igual que `compared_fields` en el WorkMatcher.

### `RankingContext` y `UserPreferences` (Value Objects)

El `RankingContext` **no** contiene preferencias mezcladas:

```python
@dataclass(frozen=True)
class UserPreferences:
    desired_format: OutputFormat | None = None
    preferred_license: str | None = None
    allowed_providers: tuple[str, ...] = ()
    # formatos, proveedores, países, idiomas, licencias, premium/free...

@dataclass(frozen=True)
class RankingContext:
    query_descriptor: WorkDescriptor
    user_preferences: UserPreferences = UserPreferences()
    execution_context: object | None = None   # contexto de ejecución (mínimo, aún por definir)
```

```python
class IWorkRanker(ABC):
    def rank(
        self, works: tuple[WorkGroup, ...], context: RankingContext, config: RankingConfig
    ) -> RankingResult: ...
```

El Ranking **no conoce el `SearchRequest` completo**: solo `RankingContext`
(`query_descriptor` + `user_preferences` + `execution_context`).

## 6. `RankingConfig` (preparado)

```python
@dataclass(frozen=True)
class RankingConfig:
    enabled_criteria: tuple[RankingCriterion, ...] = (
        RankingCriterion.RELEVANCE_TITLE,
        RankingCriterion.RELEVANCE_COMPOSER,
        RankingCriterion.RELEVANCE_CATALOGUE,
        RankingCriterion.QUALITY_CONFIDENCE,
        RankingCriterion.QUALITY_COMPLETENESS,
        RankingCriterion.PREFERENCE_FORMAT,
        RankingCriterion.PREFERENCE_LICENSE,
        RankingCriterion.PREFERENCE_PROVIDER,
        RankingCriterion.PREFERENCE_LOCALITY,
        RankingCriterion.COVERAGE,
    )
    weights: dict[RankingCriterion, float] = field(default_factory=dict)
    sorting_policy: SortingPolicy = SortingPolicy.STABLE
    # normalizadores, empates, política: preparado (no implementado)
```

`enabled_criteria` permite **activar / desactivar / medir** criterios sin tocar código.

## 7. Ranking ≠ Sorting

- **Ranking** → calcula `score` por obra.
- **Sorting** → ordena; ante **empates**, decide (política).

```python
class SortingPolicy(Enum):
    STABLE = "stable"
    BY_PROVIDER = "provider"
    BY_TITLE = "title"
    BY_CATALOGUE = "catalogue"
```

`SortingPolicy` se introduce como concepto (aún sin implementar).

## 8. Para el Evidence Engine

Cada obra produce un `RankingScore` con `reasons` (un `RankingReason` por criterio).
Eso alimenta al Evidence Engine: por qué esta obra aparece primero, y por qué se eligió
esa representación. Todo tipado, renderizable a texto/JSON/HTML o convertible en
`Evidence`. El **propio ranking es explicable**.

## 9. Medición de mejora (documento separado)

El dominio solo dice: *el Ranking produce un `RankingResult`*. Las métricas de
validación (MRR, NDCG, Precision, Recall, **golden ranking**) **no pertenecen al
contrato del Ranking**: viven en un documento separado de **Ranking Evaluation**
(`docs/ranking-evaluation.md`, por escribir). Mantenerlas fuera del dominio mantiene
el contrato limpio.

## 10. Qué NO hace el Ranking

- No cambia la identidad de una obra (no re-agrupa, no fusiona, no "corrige" al matcher).
- No elige la representación final (eso es Evidence/selección).
- No usa IA, embeddings ni modelos.
- No consulta proveedores.
- No conoce el `SearchRequest` completo (solo `RankingContext`).
- No almacena relevance/quality/preference (se derivan de los `RankingReason`).
- No contiene métricas de evaluación en el dominio.
- No modifica el núcleo congelado de V2.0.

## 11. Criterios de aceptación (V2.1.3)

- Documento congelado antes de implementar.
- `IWorkRanker.rank` puro y determinista → `RankingResult` con `RankingScore`.
- Criterios por familia (`RELEVANCE_*`, `QUALITY_*`, `PREFERENCE_*`), sin ejes fijos.
- `RankingReason(criterion, field_score, weight, contribution)`; sin `str` ni `dict`.
- `RankingScore` sin campos derivados; `evaluated_criteria` en el resultado.
- `RankingContext` (query_descriptor + `UserPreferences` + execution_context), no el
  `SearchRequest`.
- Ranking ≠ Sorting (`SortingPolicy`); `RankingConfig` con `enabled_criteria`/`weights`.
- Evaluación (`MRR`, `NDCG`, golden ranking) en documento separado.
- Tests: relevancia por catálogo/compositor, formato preferido no rompe identidad,
  dominio público, desempate por política, determinismo, inmutabilidad de los `WorkGroup`.

---

## 12. Deuda técnica para V3 (no tocar ahora)

No afectan a V2.1.3; se anotan para unificar la arquitectura en V3.

### 12.1 Dos `RankingConfig`

Ya hay **dos** `RankingConfig`:
- `domain/ranking_config.py` — el del motor de ranking **V2.0** (`DefaultRankingEngine`).
- `domain/ranking.py` (`RankingConfig`) — el del **WorkRanker** V2.1.3.

Se resolvió la colisión sin exportar el nuevo a nivel de paquete. En **V3** convendría
**unificar** con nombres distintos, p. ej.:
- `RankingEngineConfig` (V2.0) vs `WorkRankingConfig` (V2.1.3).

No se toca nada ahora.

### 12.2 Scoring "quemado" → objetos Strategy

Hoy las reglas de `field_score` viven en funciones del `ranker` (p. ej. título exacto
`1.0` / parcial `0.6`, cobertura `formatos / 3`). Es perfecto para V2, pero ya es
**política**. En **V3** esas reglas saldrían a objetos `Strategy`:

```python
class IRankingCriterion(ABC):
    def evaluate(self, work: WorkGroup, context: RankingContext) -> float | None: ...

class TitleCriterion(IRankingCriterion): ...
class CoverageCriterion(IRankingCriterion): ...
class QualityCriterion(IRankingCriterion): ...
class ProviderCriterion(IRankingCriterion): ...
```

Entonces el ranker solo haría:

```python
for criterion in enabled_criteria:
    score += criterion.evaluate(work, context)
```

Y añadir `PopularityCriterion`, `FreshnessCriterion`, `CommunityScoreCriterion`...
no tocaría el `Ranker`. Es arquitectura V3.

### 12.3 Consistencia de nombres entre contratos (V3)

Auditoría de nombres de los tres motores de V2.1. Están **consistente** en `*Result` y
`*Config`; hay pequeñas divergencias que conviene unificar en **V3**:

| Rol | Canonicalizer | WorkMatcher | Ranking | V3 sugerido |
|-----|---------------|-------------|---------|-------------|
| El "tipo" enumerado por unidad | `CanonicalRule` | `MatchField` | `RankingCriterion` | unificar sufijo (p. ej. `*Field` / `*Criterion`) |
| La razón por unidad | `AppliedRule` | `MatchReason` | `RankingReason` | unificar a `*Reason` |
| El resultado completo | `CanonicalResult` | `MatchResult` | `RankingResult` | `*Result` (ya consistente) |
| La configuración | (reglas en ficheros) | `MatchingConfig` | `RankingConfig` | `*Config` (ya consistente) |
| El contexto de entrada | — | — | `RankingContext` | solo donde haga falta |
| Marcador de "no aplica" | — | `FieldComparison` | (ausente) | `*Comparison` (p. ej. `CriterionComparison`) |

Divergencias detectadas (no corregir ahora):
- `AppliedRule` (Canonicalizer) vs `MatchReason`/`RankingReason` — misma función
  ("qué pasó"), nombres distintos.
- `MatchField` vs `RankingCriterion` — mismo rol (la unidad enumerada), nombres distintos.
- `FieldComparison` solo existe en el WorkMatcher; el Ranking lo resuelve con `None`
  internamente; convendría un `CriterionComparison.SKIPPED` por simetría.
- Dos `RankingConfig` (ver 12.1).

En V3 se propondría una convención única (`*Reason`, `*Result`, `*Config`, `*Context`,
`*Comparison`) aplicada a Canonicalizer, WorkMatcher y Ranking sin romper contratos
congelados.
