# Ranking de obras — Diseño (V2.1.3)

> **Status: draft** (se congelará antes de la implementación de V2.1.3).
>
> Parte del Search Intelligence (V2.1). Define **qué** se rankea, **qué** devuelve,
> **qué** métricas son objetivas y cuáles preferencias, **qué** produce para el
> Evidence Engine y **cómo** se mide la mejora. No se escribe código hasta congelar
> este diseño.

## Principio rector

> **El Ranking nunca cambia la identidad de una obra; únicamente decide el orden en
> que se presentan las alternativas.**

El Ranking no descubre la verdad (eso es el WorkMatcher), **ordena alternativas** ya
identificadas. Mantiene separadas dos responsabilidades:

- **WorkMatcher** → decide si A y B representan la **misma** obra.
- **Ranking** → decide **cuál de las obras ya identificadas aparece antes**.

Esa separación evita que el ranking "corrija" decisiones del matcher, algo que suele
romper muchos buscadores.

## 1. Posición en el pipeline

```
texto → Tokenizer → Lexicon → Canonicalizer → WorkMatcher → WorkGroup → Ranking → Evidence
```

El Ranking recibe **obras ya agrupadas** (`WorkGroup`) y devuelve un **orden**. Nunca
re-agrupa ni cambia la identidad de las obras.

## 2. ¿Qué se rankea exactamente? (Works, no candidatos)

Se rankean **obras** (`WorkGroup`), no representaciones individuales. El usuario ve
**obras ordenadas**; las representaciones viven *dentro* de cada obra.

| Nivel | Componente | Decide |
|-------|-----------|--------|
| **Obra** (`WorkGroup`) | Ranking (V2.1.3) | orden de aparición de las obras |
| **Representación** (dentro de la obra) | Evidence + selección | qué representación de la obra se entrega |

Dos niveles, dos responsabilidades. El Ranking de obras **no** elige la representación;
eso ya lo hace la selección con evidencia.

## 3. ¿Qué devuelve el ranking?

```python
@dataclass(frozen=True)
class WorkRankScore:
    work: WorkGroup
    score: float            # puntuación total (relevancia + preferencias)
    objective: float        # parte objetiva (relevancia derivada de los datos)
    preference: float       # parte de preferencias (formato, dominio público, proveedor...)
    criteria: dict[str, float]   # desglose por criterio
    reasons: tuple[str, ...]     # razones explicables

@dataclass(frozen=True)
class WorkRanking:
    order: tuple[WorkRankScore, ...]   # obras ordenadas (de mayor a menor)
    query: SearchRequest
```

Contrato propuesto:

```python
class IWorkRanker(ABC):
    def rank(self, works: tuple[WorkGroup, ...], query: SearchRequest, config: RankingConfig) -> WorkRanking: ...
```

Componente **puro, determinista y sin IA**.

## 4. Métricas objetivas vs. preferencias

El ranking separa **qué es cierto** (objetivo) de **qué se prefiere** (política):

### Objetivas (derivadas de los datos, no de preferencias)
- **Relevancia de identidad**: qué bien coincide la obra con la consulta (título,
  compositor, catálogo — ya normalizado por el Canonicalizer).
- **Confianza / calidad / completitud** de sus representaciones (`confidence`,
  `quality`, `completeness`).
- **Coincidencia de autoridad** (catálogo, `work_authority_identifier`).
- **Cobertura**: cuántas representaciones/formatos tiene la obra.

### Preferencias (política, en `RankingConfig`)
- **Formato pedido** (`desired_format`).
- **Dominio público / licencia**.
- **Proveedor** / local vs remoto.
- **Idioma**.

`score = peso_objetivo × objective + peso_preferencia × preference`, con ambos pesos
en `RankingConfig`. Las preferencias **nunca** pueden cambiar la identidad ni crear una
obra nueva; solo alteran el orden.

## 5. ¿Qué información produce para el Evidence Engine?

El Ranking produce un `WorkRankScore` por obra con `criteria` y `reasons`. Eso alimenta
al Evidence Engine:

- **Por qué esta obra aparece primero** (qué criterios la impulsaron).
- **Por qué esta representación de la obra se eligió** (ya lo hace el Evidence Engine
  sobre la representación elegida).

El `MatchReason`/`WorkRankScore` tipados se podrán renderizar como texto/JSON/HTML o
convertir en `Evidence` (vía un futuro `MatchExplanationRenderer`).

## 6. ¿Cómo se mide si un ranking mejora respecto al anterior?

Evaluación **offline y reproducible** (sin IA, sin intuición):

1. **Golden set**: un conjunto fijo de consultas con las obras esperadas (anotado).
2. **Métricas**:
   - `NDCG@k`, `Precision@k`, `Recall`, `Mean Reciprocal Rank (MRR)`.
   - `score` medio de obras relevantes no penalizado por irrelevantes.
3. **Regresión**: se comparan dos configuraciones de `RankingConfig` sobre el mismo
   golden set; solo se acepta un cambio si la métrica global mejora (o no empeora)
   dentro de un umbral.
4. Los **pesos se ajustan con mediciones**, no por decisión.

Esto responde "¿este ranking es mejor que el anterior?" con datos.

## 7. Qué NO hace el Ranking

- No cambia la identidad de una obra (no re-agrupa, no fusiona, no "corrige" al
  WorkMatcher).
- No elige la representación final (eso es Evidence/selección).
- No usa IA, embeddings ni modelos.
- No consulta proveedores.
- No modifica el núcleo congelado de V2.0.

## 8. Criterios de aceptación (V2.1.3)

- Documento congelado antes de implementar.
- `IWorkRanker.rank` puro y determinista, devuelve `WorkRanking` con `WorkRankScore`.
- Separación `objective` vs `preference`; preferencias nunca alteran identidad.
- Golden set + métricas (`NDCG@k`, `MRR`, ...) para medir mejora.
- `reasons`/`criteria` alimentan el Evidence Engine.
- Tests: relevancia por catálogo/compositor, formato preferido no rompe identidad,
  dominio público, determinismo, inmutabilidad de los `WorkGroup`.
