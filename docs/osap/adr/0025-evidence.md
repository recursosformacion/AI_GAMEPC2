# ADR-0025 – Evidence (hechos estructurados)

## Estado

Aceptado. Cierre de V2.2.a (`v2.2.0-alpha`).

## Principios

- **Evidence se produce como hechos estructurados** (`EvidenceItem`), nunca como texto.
- **No existe renderer dentro del dominio**: convertir `EvidenceItem` en texto/JSON/HTML
  se hace fuera del dominio.
- **Cada decisión arquitectónica produce evidencia**: Matcher, Ranking y Selection
  producen `EvidenceItem` (vía `IEvidenceContributor`).
- **Evidence es inmutable** (objetos `frozen`).

## Contexto

Durante V2.2.a apareció una **asimetría**: no todo `MatchReason`/`RankingReason`
produce un `EvidenceItem`, porque el `EvidenceCode` congelado no cubre todos los
`MatchField`/`RankingCriterion` (p. ej. OPUS, MOVEMENT, GENRES, INSTRUMENTATION,
PERSON_AUTHORITY, PREFERENCE_PROVIDER, PREFERENCE_LOCALITY). Eso rompe la relación
1:1 `Reason → EvidenceItem`.

## Decisión (opción A)

Ampliar `EvidenceCode` hasta cubrir **todos** los `MatchField` y `RankingCriterion`,
de modo que siempre sea cierto:

```
Reason
  ↓
EvidenceItem
```

sin excepciones. Esto hace el sistema extremadamente coherente.

**Estado de implementación**: pendiente (tarea V2.2.x) — no se toca ahora el enum
congelado.

## Consecuencias

- El dominio solo produce hechos; el renderer es externo.
- Cada decisión (match, ranking, selección) deja evidencia trazable.
- La evidencia es inmutable y determinista.
- (Pendiente) al ampliar `EvidenceCode`, `Reason → EvidenceItem` será siempre 1:1.
