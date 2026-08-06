# OSAP — Open Sheet Music Aggregation Platform

> Documentación web de OSAP. Fuente de verdad técnica: **OSAP Architecture Book**
> (`osap-architecture-book.md`).

---

## Hero

**OSAP no busca partituras. Construye conocimiento fiable sobre las obras musicales.**

OSAP agrega catálogos musicales abiertos, resuelve la **identidad** de las obras y
**explica cada decisión** con hechos estructurados. Determinista. Tipado. Sin IA en la
decisión de identidad.

### Estado actual

| Versión | Estado |
|---------|--------|
| V2.0 · V2.1 · V2.2.a · V2.2.b · V2.2.c | ✅ Implementado |
| V2.2.d — Knowledge Mining | ⏳ Pendiente |
| V3 — Motor inteligente | 🔮 Futuro |

---

## El problema

Una misma obra existe en IMSLP, MuseScore, OpenScore, CPDL, MusicBrainz... Cada
proveedor usa **nombres, catálogos, idiomas y formatos distintos**.

El reto no es encontrar resultados, sino saber **cuándo hablan de la misma obra** y
**cuál merece la pena elegir**.

---

## Qué hace OSAP

- **Agrega** catálogos bajo un mismo contrato (`ICatalogProvider`).
- **Resuelve la identidad** de las obras (Identity ≠ Similarity).
- **Explica** cada decisión con Evidence estructurado y trazable.
- **Construye** conocimiento reutilizable sobre las obras.

---

## El pipeline

```
Query → Tokenizer → Lexicon → Canonicalizer → WorkMatcher
      → WorkGrouping → Ranking → Merge → Selection
      → Evidence → Resultado
```

Cada etapa es **explicable**: sabes *por qué* se eligió cada cosa.

---

## Características

### Identity ≠ Similarity
El `WorkMatcher` decide **identidad** (¿es la misma obra?), no solo parecido textual.

### Merge que nunca cambia identidad
`Merge` consolida conocimiento descriptivo y expone conflictos, sin alterar la
identidad decidida. Inmutable, determinista, independiente del orden.

### Evidence, hechos no frases
Matcher, Ranking, Merge y Selection producen `EvidenceItem` tipados. El renderer vive
fuera del dominio.

### Jobs que solo orquestan
Los Jobs no contienen reglas de negocio; el scheduler queda fuera del alcance.

### Contratos congelados
`domain/` y `ports/` son API pública: cambiarlos requiere un ADR.

---

## ¿Por qué no IA?

OSAP no decide identidad con IA. Usa **conocimiento musicológico declarativo**
(catálogos, autoridades, normalización, reglas tipadas).

- **Determinismo** — mismas entradas, mismas salidas.
- **Explicabilidad** — cada decisión deja evidencia.
- **Fiabilidad** — sin resultados plausibles pero erróneos sin causa.
- **Mantenibilidad** — las reglas se auditan como código.

La IA asistida se reserva (V3) para conocimiento acumulado y OMR asistida, **nunca**
para decidir identidad.

---

## Calidad

- **Ruff** — lint limpio en `src/osap` + `tests/osap`.
- **mypy --strict** — sin errores en todo `src`.
- **Tests** — **323** en verde, con el pipeline recorrido **sin mocks del dominio**.
- **Arquitectura congelada** — evolución por adaptación, no por rediseño.

---

## Tecnologías

Python 3.12 · FastAPI (prevista) · SQLite / PostgreSQL · MediaWiki API · MusicBrainz ·
MuseScore / OpenScore · IMSLP · Docker · pytest / Ruff / mypy.

---

## Roadmap

```
V2.2.d  Knowledge Mining ─► V3  Motor inteligente
```

Entre V2.2.c y V2.2.d: sprint corto de presentación (API + web) para validar visualmente
el dominio.

---

## Get started

```bash
pip install -e .
osap search "Ave Maria"
osap resolve "Mozart Nocturnes"
```

```bash
mypy --strict
ruff check src tests
pytest tests/
```

---

## Documentación

- **OSAP Architecture Book** — fuente de verdad técnica: `osap-architecture-book.md`.
- Diseños: Search Intelligence · Canonicalizer · WorkMatcher · Ranking · Evidence ·
  Dedup/Merge · Jobs.
- **ADR** — Architecture Decision Records (decididos y congelados).
- **Presentación V2.2** — 20 diapositivas: `presentation-v22.md`.
