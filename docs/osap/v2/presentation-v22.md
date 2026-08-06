# Presentación OSAP v2.2

> Open Sheet Music Aggregation Platform
>
> Derivada del *OSAP Architecture Book* (`osap-architecture-book.md`), fuente de verdad.
> 20 diapositivas. Cada sección es una diapositiva.

---

## 1 — Qué es OSAP

**Open Sheet Music Aggregation Platform**

- Agrega **múltiples catálogos** musicales.
- **Resuelve la identidad** de las obras.
- **Explica todas** las decisiones.
- Arquitectura **desacoplada**.

> OSAP no busca partituras. Construye conocimiento fiable sobre las obras musicales.

---

## 2 — El problema

Buscar partituras es complicado. Una misma obra existe en:

- IMSLP · MuseScore · OpenScore · CPDL · MusicBrainz · ...

Y cada proveedor usa:

- **nombres** distintos
- **catálogos** distintos
- **idiomas** distintos
- **formatos** distintos

El reto no es encontrar resultados, sino saber **cuándo hablan de la misma obra**.

---

## 3 — Filosofía

Tres principios:

- **Identidad** — decidir cuál es la obra real y cuáles las variantes.
- **Explicabilidad** — toda decisión deja evidencia estructurada.
- **Determinismo** — mismas entradas → mismas salidas.

Regla explícita: **nunca IA para decidir identidad.**

---

## 4 — Arquitectura

El pipeline completo (la diapositiva más importante):

```
Query → Tokenizer → Lexicon → Canonicalizer → WorkMatcher
      → WorkGrouping → Ranking → Merge → Selection
      → Evidence → Resultado
```

Dominio hexagonal: `domain` / `ports` / `application` / `infrastructure`.
El dominio **no conoce a nadie**.

---

## 5 — Evolución

```
V2.0 ─► V2.1 ─► V2.2 ─► V3
```

- **V2.0** — auditoría, contratos, orquestador, OMR + IMSLP.
- **V2.1** — Search Intelligence: Canonicalizer, Matcher, Grouping, Ranking.
- **V2.2** — Evidence (a) · Merge (b) · Jobs (c).
- **V3** — motor inteligente y conocimiento acumulado.

---

## 6 — Canonicalizer

Transforma alias y variantes en forma **canónica** normalizada.

```
K618
  ↓
KV 618
  ↓
Descriptor normalizado
```

Reglas **declarativas** (p. ej. `catalogue_aliases.yaml`), no heurísticas en código.
Cada regla aplicada queda registrada (`AppliedRule`) → **explicable**.

---

## 7 — WorkMatcher

**Identity ≠ Similarity**

- **Similarity** = dos textos se parecen.
- **Identity** = dos resultados son la **misma obra**.

El `WorkMatcher` decide **identidad**, no solo similitud.
`MatchLevel` (SAME / POSSIBLE / DIFFERENT), `field_score`, `MatchReason` tipado.
Vetos y coincidencias seguras viven en `MatchingConfig`, **no en el código**.

---

## 8 — Ranking

Ordena **obras** (`WorkGroup`), no representaciones.

- **Relevance** — cuánto responde a la búsqueda.
- **Quality** — confianza, completitud, formato.
- **Preference** — preferencias del usuario / localidad.

Internamente, criterios **tipados** (`RankingCriterion`) sin ejes fijos.
**Nunca cambia la identidad** de una obra; solo ordena alternativas.
Cada `RankingReason` explica **por qué una obra aparece antes**.

---

## 9 — Merge

```
IMSLP
MusicBrainz
OpenScore
   ↓
Merged Descriptor
```

- **Merge nunca cambia identidad.**
- Enriquece **solo campos descriptivos**; confirma o expone como conflicto los de identidad.
- Resultado **inmutable**: `MergedWorkDescriptor` + `MergeProvenance` + `MergeConflicts`.
- Determinista e **independiente del orden**.

---

## 10 — Evidence

```
Matcher →┐
Ranking →┼─► EvidenceCollector ─► EvidenceResult
Merge   →┤      (IEvidenceContributor)
Selection→┘
```

- `EvidenceItem`: `source` + `code` + `score` + `strength` + `fields`, todo tipado.
- **Hechos, no texto.** El renderer (texto/JSON/HTML) vive fuera del dominio.
- Responde: **¿por qué OSAP ha elegido esta representación?**

---

## 11 — Jobs

**Jobs ≠ Dominio**

- **Solo orquestan** procesos ya existentes.
- No contienen reglas de negocio ni conocen proveedores → siempre Application Services.
- `IJob.run(context) -> JobResult`, `JobResult` totalmente tipado.
- Observabilidad por **eventos** (`JobEvent`), nunca logs directos.
- El **scheduler** (cron, Celery, APScheduler...) queda **fuera del alcance**.

---

## 12 — Contratos congelados

`domain/` y `ports/` = **API pública**.

```
domain/  value_objects · work_descriptor · canonicalization · matching
         ranking · evidence · merge · jobs
ports/   ICatalogProvider · IJob · IMergeService · IRankingEngine · ...
```

Regla: **cambiar un contrato congelado requiere un ADR.**
El sistema evoluciona (MuseScore, YouTube, V3) **adaptándose** al núcleo, no rediseñándolo.

---

## 13 — ADR

**Architecture Decision Record** — documento corto que **congela una decisión**.

Formato: Estado · Principios · Contexto · Decisión · Consecuencias.

Ejemplos:

- **ADR-22** — separación Identity / Matching / Ranking.
- **ADR-23** — Search Intelligence (cierre V2.1).
- **ADR-25** — Evidence como hechos estructurados.
- **ADR-26** — `domain.jobs` (V2.2) frente a `domain.job` (legado).

---

## 14 — Calidad

- **Ruff** — limpio en `src/osap` + `tests/osap`.
- **mypy --strict** — sin errores en todo `src`.
- **Tests** — **323** en verde.
- **Arquitectura congelada** — `domain/` + `ports/` como API pública.

Sin IA para identidad · sin strings mágicos · sin `dict` dinámicos · sin `Exception`
como contrato.

---

## 15 — Pipeline de integración

El **«canario de la mina»**.

Los tests recorren:

```
Canonicalizer → Matcher → Grouping → Ranking
```

**sin mocks del dominio.** Datos reales de extremo a extremo.
Una regresión en cualquier etapa se detecta de inmediato y protege los contratos
congelados.

---

## 16 — Explicabilidad — ejemplo

```
Ave Verum Corpus
```

**porque**

- ✓ catálogo (KV 618 coincide)
- ✓ compositor (Mozart)
- ✓ autoridad (identificador de autoridad)
- ✓ MusicXML preferido
- ✓ Merge (representaciones consolidadas)
- ✓ Evidence (hechos trazables)

Cada ✓ = un `EvidenceItem`. El usuario puede preguntar **«¿por qué?»** y OSAP responde
con hechos.

---

## 17 — Principios

- **Determinista** — mismas entradas, mismas salidas.
- **Tipado** — mypy --strict; sin `dict[str, ...]` como contrato.
- **Sin strings mágicos** — todo `Enum` o constante con nombre.
- **Sin dict dinámicos** — modelos explícitos.
- **Frozen dataclasses** — inmutabilidad por defecto.
- **Value Objects** — `ProviderId`, `WorkId`, `WorkIdentifier`...
- **Interfaces** — todo acceso externo pasa por un puerto.
- **Arquitectura hexagonal** — el dominio no conoce a nadie.

---

## 18 — Roadmap

```
V2.2.d  Knowledge Mining
   ↓
V3      Motor inteligente
```

- **V2.2.d** — observar OSAP y generar **propuestas** (`knowledge/proposals/`), sin IA.
- **V3** — Knowledge Base, IA avanzada, personalización.

Entre V2.2.c y V2.2.d: sprint corto de **presentación** (API + web) para validar el dominio.

---

## 19 — Futuro

- **Web** — buscador y visualización de Evidence / Ranking / Merge.
- **API** — REST mínima sobre el pipeline.
- **CLI** — ya existe (`osap search/resolve`).
- **Desktop** — aplicación de escritorio.
- **Plugins** — extensión a otros ecosistemas.
- **Knowledge Mining** — propuestas desde el uso real.

Todas consumen el mismo **núcleo congelado** vía los puertos.

---

## 20 — Conclusión

> **«OSAP no busca partituras. Construye conocimiento fiable sobre las obras
> musicales.»**

Cada obra resuelta deja:

identidad decidida · ranking explicable · fusión consolidada · evidencia trazable.

Ese **conocimiento**, no la lista de PDFs, es el producto.
