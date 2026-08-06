# OSAP Architecture Book

> **Open Sheet Music Aggregation Platform — V2.2**
>
> Referencia técnica completa del estado de OSAP tras cerrar **V2.2.c**. Este documento es
> la **única fuente de verdad** de la arquitectura. A partir de él se derivan la
> presentación, la documentación web y la documentación para GitHub.
>
> Status: **en curso** (single source of truth, V2.2).

---

## Executive Summary

OSAP es una plataforma para **resolver la identidad de obras musicales** provenientes de
múltiples catálogos abiertos.

Sus objetivos son:

- **Agregar** catálogos.
- **Resolver** identidad.
- **Explicar** cada decisión.
- **Construir** conocimiento reutilizable.

### Estado actual

| Estado | Versión |
|--------|---------|
| V2.0 | ✅ |
| V2.1 | ✅ |
| V2.2.a | ✅ |
| V2.2.b | ✅ |
| V2.2.c | ✅ |
| V2.2.d | Pendiente |
| V3 | Futuro |

---

## 1. Qué es OSAP

**OSAP** (Open Sheet Music Aggregation Platform) es una plataforma que **agrega múltiples
catálogos musicales**, **resuelve la identidad de las obras** y **explica todas sus
decisiones**.

Los tres problemas que resuelve:

1. **Agregar** múltiples catálogos musicales (IMSLP, MuseScore, OpenScore, CPDL,
   MusicBrainz...) bajo un mismo contrato.
2. **Resolver la identidad** de las obras (decidir cuándo dos resultados se refieren a la
   misma obra).
3. **Explicar** todas las decisiones (por qué se eligió una representación y no otra).

Y lo hace con una **arquitectura desacoplada**: el dominio no depende de proveedores, ni
de la web, ni de la infraestructura.

---

## 2. El problema

Buscar partituras es complicado. **Una misma obra puede existir en** IMSLP, MuseScore,
OpenScore, CPDL, MusicBrainz, etc., y cada proveedor usa:

- **nombres distintos** («Ave Verum», «Ave Verum Corpus», «Ave verum KV 618»...);
- **catálogos distintos** (KV 618, K. 618, K618...);
- **idiomas distintos** (Latin, Alemán, Inglés...);
- **formatos distintos** (PDF, MusicXML, MEI, MIDI...).

El problema central no es encontrar resultados, sino saber **cuándo hablan de la misma
obra** y **cuál merece la pena elegir**.

---

## 3. Filosofía

Tres principios:

- **Identidad**: el sistema decide cuál es la obra real y cuáles son variantes.
- **Explicabilidad**: toda decisión deja evidencia estructurada y trazable.
- **Determinismo**: mismas entradas → mismas salidas. Sin aleatoriedad.

Y una regla explícita: **nunca IA para decidir identidad**. La identidad se decide con
conocimiento musicológico declarativo (catálogos, autoridades, normalización), no con
modelos de lenguaje ni embeddings.

---

## 4. ¿Por qué no IA?

Es una de las decisiones más importantes y una de las **más poco habituales**.

OSAP **no decide identidad con IA**. Resuelve la identidad de las obras con
**conocimiento musicológico declarativo**: catálogos (BWV, KV...), autoridades,
normalización y reglas tipadas. No con modelos de lenguaje, embeddings ni LLM.

Por qué:

- **Determinismo** — las mismas entradas producen siempre la misma decisión.
- **Explicabilidad** — cada decisión deja evidencia estructurada y trazable.
- **Fiabilidad** — no hay resultados plausiblemente erróneos sin causa.
- **Mantenibilidad** — las reglas se auditan y se corrigen como código.

La IA no está prohibida en todo OSAP; lo está en la **decisión de identidad**. La IA
asistida se reserva, en el roadmap (V3), para el conocimiento acumulado y la OMR
asistida, **nunca** para decidir si dos obras son la misma.

---

## 5. Arquitectura

OSAP sigue una **arquitectura hexagonal** con cuatro capas:

```
        HTTP / CLI / Tests
               │
               ▼
      ┌─────────────────┐
      │  Infrastructure  │   providers, mediawiki, in-memory engines, cachés
      └────────┬─────────┘
               │
      ┌────────▼─────────┐
      │   Application    │   orquestación: ProviderOrchestrator, WorkMatcher,
      │     Services      │   Ranker, MergeService, EvidenceCollector, Jobs
      └────────┬─────────┘
               │
      ┌────────▼─────────┐
      │      Ports       │   interfaces (ICatalogProvider, IJob, ...)
      └────────┬─────────┘
               │
      ┌────────▼─────────┐
      │      Domain       │   Value Objects, WorkDescriptor, Matching, Ranking,
      │                   │   Evidence, Merge, Jobs  (API pública congelada)
      └──────────────────┘
```

Regla de dependencia: **el dominio no conoce a nadie**; la infraestructura depende de los
puertos; los puertos se implementan en el dominio/aplicación. `domain/` y `ports/` son
**API pública congelada**.

### El pipeline completo

```
  Query
    ↓
  Tokenizer
    ↓
  Lexicon
    ↓
  Canonicalizer
    ↓
  WorkMatcher
    ↓
  WorkGrouping
    ↓
  Ranking
    ↓
  Merge
    ↓
  Selection
    ↓
  Evidence
    ↓
  Resultado
```

Esta diapositiva es la más importante: es el flujo que recorre **cada** búsqueda y cada
decisión.

---

## 6. Evolución

OSAP se construye por **versiones de plataforma**, no por sprints:

```
V2.0 ─► V2.1 ─► V2.2 ─► V3
```

| Versión | Contenido |
|---------|-----------|
| **V2.0** | Auditoría + limpieza + contratos públicos, Provider Orchestrator, Aggregator, proveedores OMR e IMSLP. |
| **V2.1** | Search Intelligence: Canonicalizer, WorkMatcher, WorkGrouping, Ranking. |
| **V2.2** | Evidence definitivo (a), Dedup/Merge (b), Jobs (c). |
| **V3** | Motor inteligente y conocimiento acumulado. |

---

## 7. Canonicalizer

**Qué hace.** Transforma alias y variantes en una forma **canónica** normalizada. Es
clasificación y normalización, separadas del matching (ADR-0021).

**Ejemplo:**

```
K618
  ↓
KV 618
  ↓
Descriptor normalizado
```

El `Canonicalizer` usa reglas **declarativas** (p. ej. `catalogue_aliases.yaml`), no
heurísticas en código. Produce `CanonicalResult` con `AppliedRule` (qué regla se aplicó),
lo que lo hace **explicable**.

---

## 8. WorkMatcher

Separa claramente dos conceptos que a menudo se confunden:

```
Identity   ≠   Similarity
```

- **Similarity** = dos textos se parecen (parecido léxico).
- **Identity** = dos resultados se refieren a la **misma obra** (decisión de dominio).

El `WorkMatcher` decide **identidad**, no solo similitud. Usa `MatchLevel`
(SAME / POSSIBLE / DIFFERENT), una puntuación de campo continua (`field_score`) y
`MatchReason` tipado. Las reglas de veto (catálogo → DIFFERENT) y de coincidencia segura
(authority → SAME) viven en `MatchingConfig`, **no en el código** (ADR-0022).

Por qué separar: confundirlas produce falsos positivos (dos obras con títulos similares)
y rompe la explicabilidad.

---

## 9. Ranking

Ordena **obras** (`WorkGroup`), no representaciones. Los criterios se agrupan por familia:

- **Relevance** — cuánto responde a la búsqueda.
- **Quality** — confianza, completitud, formato.
- **Preference** — preferencias del usuario/localidad.

Aunque en la presentación se muestran como Relevance/Quality/Preference, internamente
están **derivados por criterios** tipados (`RankingCriterion`) sin ejes fijos. El Ranking
**nunca cambia la identidad de una obra**: solo ordena las alternativas
(ADR-0023). Cada `RankingReason` explica **por qué una obra aparece antes**.

---

## 10. Merge

Consolida el conocimiento de las representaciones de una **misma** obra:

```
IMSLP
MusicBrainz
OpenScore
    ↓
Merged Descriptor
```

Principio rector: **Merge nunca cambia identidad.** La identidad ya la decidió el
`WorkMatcher`; Merge solo enriquece campos **descriptivos** (subtitle, language, key,
genres, instrumentation...) y confirma o expone como conflicto los de identidad. El
resultado es un `MergedWorkDescriptor` inmutable con `MergeProvenance` (por campo, por
fuente, por estrategia) y `MergeConflicts`, determinista e **independiente del orden** de
las representaciones. La estrategia de selección es **política** (`MergePolicy`), no
contrato.

---

## 11. Evidence

Todo el pipeline produce **hechos estructurados**, no texto:

```
Matcher  ─┐
Ranking  ─┼─► EvidenceCollector ─► EvidenceResult
Merge    ─┤        (IEvidenceContributor)
Selection─┘
```

- Cada `EvidenceItem` tiene `source` (MATCHER / RANKER / MERGE / SELECTION), `code`
  (`EvidenceCode` estable), `score`, `strength` y `fields` tipados.
- **No existe renderer dentro del dominio**: convertir hechos en texto/JSON/HTML se hace
  fuera (ADR-0025).
- La pregunta que responde: **¿por qué OSAP ha elegido esta representación?**

---

## 12. Jobs

```
Jobs   ≠   Dominio
```

Los Jobs **solo orquestan procesos ya existentes**. No contienen reglas de negocio ni
conocen proveedores: siempre usan Application Services.

- Contrato mínimo: `IJob.run(context) -> JobResult`.
- `JobContext` = solo información de ejecución (execution_id, triggered_by, dry_run...).
- `JobResult` = resultado totalmente tipado (status, duration, counts, errors).
- Observabilidad por **eventos** (`JobEvent`), nunca logs directos.
- El **scheduler** (cron, Celery, APScheduler, workers) queda **fuera del alcance**:
  el contrato del Job no depende del mecanismo de ejecución (ADR-0026).

---

## 13. Contratos congelados

`domain/` y `ports/` forman la **API pública** de OSAP.

```
domain/
  value_objects, work_descriptor, canonicalization, matching,
  ranking, evidence, merge, jobs
ports/
  ICatalogProvider, IJob, IMergeService, IRankingEngine, ...
```

Regla: **cambiar un contrato congelado requiere un ADR.** Esto permite evolucionar el
sistema (MuseScore, YouTube, V3) **adaptándose** al núcleo, sin rediseñarlo.

---

## 14. ADR

Un **ADR** (Architecture Decision Record) es un documento corto que **congela una
decisión arquitectónica** y su contexto, para que no haya dudas dentro de unos meses.

Formato mínimo: Estado, Principios, Contexto, Decisión, Consecuencias.

Ejemplos recientes:

- **ADR-22** — Separación de Identity/Matching y Ranking.
- **ADR-23** — Search Intelligence (cierre de V2.1).
- **ADR-25** — Evidence como hechos estructurados (cierre de V2.2.a).
- **ADR-26** — `domain.jobs` (V2.2) frente a `domain.job` (legado).

---

## 15. Calidad

Cifras de la rama actual:

- **Ruff** — limpio en `src/osap` + `tests/osap` (reglas E, F, W, I, N, UP, B, SIM, TCH).
- **mypy --strict** — sin errores en todo `src` (207–210 ficheros tipados estrictamente).
- **Tests** — **323 tests** en verde.
- **Arquitectura congelada** — `domain/` y `ports/` como API pública; cambios requieren ADR.

Sin IA para identidad, sin strings mágicos, sin `dict` dinámicos, sin `Exception` como
contrato.

---

## 16. Pipeline de integración

Los tests de integración son el **«canario de la mina»**: si algo del pipeline se rompe,
el canario canta.

Los tests recorren el pipeline completo

```
Canonicalizer
    ↓
Matcher
    ↓
Grouping
    ↓
Ranking
```

**sin mocks del dominio.** El dominio se prueba con datos reales de extremo a extremo, de
modo que una regresión en cualquier etapa se detecta de inmediato y los contratos
congelados se protegen de cambios silenciosos.

---

## 17. Explicabilidad — ejemplo

Resultado de una búsqueda:

```
Ave Verum Corpus
```

**porque**

- ✓ catálogo (KV 618 coincide)
- ✓ compositor (Mozart)
- ✓ autoridad (identificador de autoridad coincide)
- ✓ MusicXML preferido (formato preferido)
- ✓ Merge (se consolidaron representaciones)
- ✓ Evidence (cada motivo dejó un hecho estructurado)

Cada ✓ corresponde a un `EvidenceItem` trazable. El usuario puede preguntar «¿por qué?»
y OSAP puede responder **con hechos**, no con frases hechas.

---

## 18. Principios

Lista corta de cómo se escribe el código:

- **Determinista** — mismas entradas, mismas salidas.
- **Tipado** — mypy --strict; sin `dict[str, ...]` como contrato.
- **Sin strings mágicos** — todo es `Enum` o constante con nombre.
- **Sin dict dinámicos** — modelos explícitos.
- **Frozen dataclasses** — inmutabilidad por defecto.
- **Value Objects** — `ProviderId`, `WorkId`, `WorkIdentifier`...
- **Interfaces** — todo acceso externo pasa por un puerto.
- **Arquitectura hexagonal** — el dominio no conoce a nadie.

---

## 19. Tecnologías

La gente siempre pregunta **«¿con qué está hecho?»**. Respuesta:

- **Python 3.12** — lenguaje del dominio, la aplicación y la infraestructura.
- **FastAPI** — API REST (prevista).
- **SQLite / PostgreSQL** — persistencia (índice, credenciales...).
- **MediaWiki API** — cliente para catálogos basados en MediaWiki (IMSLP).
- **MusicBrainz** — autoridades y normalización de identidad.
- **MuseScore / OpenScore** — catálogos agregados.
- **IMSLP** — catálogo agregado (prueba de estrés del contrato).
- **Docker** — empaquetado y despliegue.
- **pytest / Ruff / mypy** — calidad (tests, lint, tipado estricto).

---

## 20. Roadmap

```
V2.2.d  Knowledge Mining
   ↓
V3      Motor inteligente
```

- **V2.2.d — Knowledge Mining**: observar el funcionamiento de OSAP y generar
  **propuestas** (`knowledge/proposals/`); puente natural hacia V3 (conocimiento
  declarativo, sin IA).
- **V3 — Motor inteligente**: Knowledge Base y aprendizaje de la plataforma, IA avanzada
  (embeddings, OMR/IA asistida), personalización con `user_profile`.

Entre V2.2.c y V2.2.d se recomienda un **sprint corto de presentación** (API REST mínima +
web sencilla) para validar visualmente el dominio antes de cerrarlo.

---

## 21. Futuro

Superficies donde OSAP puede presentarse:

- **Web** — buscador y visualización de Evidence/Ranking/Merge.
- **API** — REST mínima sobre el pipeline.
- **CLI** — ya existe (`osap search/resolve`).
- **Desktop** — aplicación de escritorio.
- **Plugins** — extensión a otros ecosistemas.
- **Knowledge Mining** — propuestas generadas desde el uso real.

Todas consumen el mismo núcleo congelado vía los puertos.

---

## 22. Conclusión

> **«OSAP no busca partituras. Construye conocimiento fiable sobre las obras
> musicales.»**

Cada obra resuelta deja identidad decidida, ranking explicable, fusión consolidada y
evidencia trazable. Ese conocimiento, no la lista de PDFs, es el producto.

---

## 23. Glosario

- **WorkDescriptor** — descripción normalizada de una obra (identidad + campos descriptivos).
- **WorkGroup** — grupo de representaciones que el Matcher decidió que son la misma obra.
- **Representation** — un resultado concreto de una obra dentro de un `WorkGroup`.
- **CandidateRepresentation** — candidato devuelto por un proveedor antes de agrupar.
- **Evidence** — hechos estructurados que explican una decisión (match/ranking/merge/selección).
- **Merge** — consolidar el conocimiento descriptivo de un `WorkGroup` sin cambiar identidad.
- **Ranking** — ordenar obras/alternativas sin cambiar su identidad.
- **Identity** — decisión de que dos resultados son la misma obra.
- **Similarity** — parecido léxico/textual; no equivale a identidad.
