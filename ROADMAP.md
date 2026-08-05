# ROADMAP OSAP — V2

> Reinicio de OSAP. El punto de partida es la **Architecture Audit 2026**
> (`docs/architecture-audit.md`, congelada). Los hitos aquí son **versiones de
> plataforma**, no sprints; cada versión tiene criterios de salida verificables.
>
> El contrato de proveedores se define en `docs/provider-contract.md` y es el
> documento más importante de la V2: todos los proveedores obedecen el mismo contrato.

Principios de V2:
- **OMR es un proveedor más.** Para OSAP, IMSLP, MuseScore, CPDL, OpenScore,
  Open Music Repository, Filesystem y PDMX son exactamente iguales: todos
  implementan `ICatalogProvider`. No existe un camino especial para OMR. Eso
  mantiene a OSAP independiente.
- **Freeze primero, código después.** Los contratos se escriben antes de
  implementar. IMSLP, MuseScore, OMR... todos obedecen el mismo contrato.
- **Búsqueda en dos fases (ADR-0019).** OSAP responde preguntas **musicales**;
  OMR responde preguntas sobre **sus recursos**. El flujo es siempre
  `Usuario → OSAP Search → Work → Resolve → Provider → Download`. Nunca se
  preguntan cosas complejas directamente a OMR. Esto mantiene ambos proyectos
  independientes y permite sustituir OMR por otro proveedor sin tocar el núcleo.
- **Primero el contrato en acción, luego la prueba de estrés.** OMR (V2.0.5)
  demuestra que el contrato funciona **sin casos especiales**; IMSLP (V2.0.6)
  prueba que el mismo contrato generaliza a un proveedor completamente distinto.

Leyenda de impacto (de la auditoría):
- 🔒 **Núcleo** = se queda.
- 📦 **OMR** = se mueve a Open Music Repository (la aplicación repositorio).
- 🗑️ **Eliminar** = se retira.
- ⏳ **Aplazar** = no se toca todavía.

---

## V2.0.0 — Auditoría + limpieza + contratos públicos

**Alcance**
- Architecture Audit 2026 (`docs/architecture-audit.md`), congelada.
- Limpieza del árbol (código muerto fuera, OMR separado, `docs/old/`).
- `docs/provider-contract.md` como especificación de contratos públicos.
- ADR-0018 (todos los proveedores son iguales), ADR-0019 (búsqueda en dos fases).

**Estado:** ✅ **Hecho**

---

## V2.0.1 — Congelar contratos públicos

**Alcance**
- Contratos de dominio congelados: `SearchRequest`, `ResolveRequest`, `CostLevel`,
  `CatalogCapabilities`, `CandidateRepresentation`, `AcquisitionResult`, `Evidence`.
- El núcleo piensa con estos tipos (`SearchRequest` circula en el sistema).

**Estado:** ✅ **Hecho**

---

## V2.0.2 — Provider Orchestrator

El cerebro que decide:
- qué proveedores consultar
- en qué orden (por coste de consulta)
- coste (`FREE/CHEAP/NORMAL/EXPENSIVE`)
- caché (reutilizar búsquedas recientes)
- parada temprana (no consultar un proveedor caro si uno barato basta)

**Estado:** ✅ **Hecho**

---

## V2.0.3 — Provider Result Aggregator

Responsable de:
- unificar resultados multiproveedor
- deduplicar (mismo proveedor + `remote_id` / `checksum`)
- agrupar por obra (`WorkDescriptor`)
- entregar una colección homogénea al ranking
- conservar diagnósticos y procedencia

**Estado:** ✅ **Hecho**

---

## ADR-0020 — Provider Search Strategy (previo)

Documento **muy pequeño (2–3 páginas)** que congela el comportamiento del orquestador
antes de conectar cualquier proveedor real. Responde de forma definitiva:

- ¿Cuándo se detiene el `ProviderOrchestrator`?
- ¿Cuándo merece la pena consultar un proveedor caro?
- ¿Cuándo se reutiliza la caché?
- ¿Cuándo se ejecuta en paralelo?
- ¿Qué significa que una búsqueda está "satisfecha"?

No cambia código: congela el comportamiento. `docs/adr/0020-provider-search-strategy.md`.

---

## V2.0.5 — OMR Provider

**Alcance**
- Open Music Repository como `ICatalogProvider` estándar.
- Implementa únicamente `search()`, `resolve()`, `download()`, `metadata()`,
  `capabilities()`.
- **Sin hacks, sin excepciones, sin `if provider == "omr"` por ninguna parte.**
  Si hay que escribir eso, la arquitectura está mal.
- No es especial: demuestra que el contrato funciona tal cual.

**Criterios de salida**
- `osap search/resolve` consulta OMR como un proveedor más.
- No existe ninguna referencia a "omr" especializada en el núcleo.

---

## V2.0.6 — IMSLP

**Alcance**
- Adaptar `catalogs/imslp` al contrato (hoy adaptador real pero parcial).
- IMSLP es la **prueba de estrés**: búsqueda compleja, múltiples ediciones,
  licencias, varias representaciones, MediaWiki, errores, páginas ambiguas,
  descargas manuales.
- `mediawiki/MediaWikiClient` y `auth/*` a producción (credenciales por proveedor).

**Criterios de salida**
- Si el **mismo contrato** que sirve a OMR sirve a IMSLP, significa que acertamos.
- `resolve` y `download` con IMSLP de extremo a extremo, con metadata-first.
- Cualquier hueco del contrato se corrige **en el contrato**, no con excepciones.

---

## V2.0 Freeze

**El núcleo de resolución queda congelado.**

- V2.0.0–V2.0.6 ✅ completadas y verificadas (contratos, SearchRequest, Orchestrator,
  Aggregator, Evidence, OMR, IMSLP).
- Validado el caso más importante de OSAP: **varios proveedores describiendo la misma
  obra** → un solo `WorkGroup` con sus representaciones.
- OMR e IMSLP funcionan simultáneamente bajo el mismo `ICatalogProvider`, sin casos
  especiales y sin tocar el núcleo.

**Regla desde aquí:** los siguientes desarrollos (Search Engine, MuseScore, YouTube...)
se **adaptan** a este núcleo. Solo se modifica si un proveedor real demuestra una
**limitación general** del contrato. Este freeze marca el momento en que se deja de
rediseñar arquitectura y se empieza a construir producto.

---

## V2.1 — Search Intelligence (Nuevo Search Engine)

> **Diseño antes que código.** La V2.1 no empieza implementando: empieza con un
> documento de diseño (`docs/search-engine-design.md`, el **4º documento fundamental**,
> junto a la Auditoría, el ROADMAP y el Provider Contract) que responda, de forma estable:

- ¿Qué significa **buscar una obra**?
- ¿Qué diferencia hay entre **búsqueda libre** y **resolución**?
- ¿Cómo se **combinan** los resultados de varios proveedores?
- ¿Cómo se **ordenan**? ¿Qué peso tienen compositor, catálogo, género, instrumentación...?
- ¿Qué hace OSAP cuando una búsqueda devuelve **cientos de candidatos**?

> **El Search Engine ya existe** (`SearchRequest → Orchestrator → Providers →
> Aggregator → WorkGroups`). V2.1 no construye infraestructura: la hace **inteligente**
> (Search Intelligence). Se divide en tres bloques de algoritmos:

| Sub | Bloque | Contenido |
|-----|--------|-----------|
| **V2.1.1** | Normalización | `Lexicon` creciente, catálogos (BWV/KV), nombres, acentos, transliteraciones |

> **Normalización explicable** (`docs/normalization-explorable.md`) + **ADR-0021**
> (Separation of Classification and Canonicalization): el `Lexicon` clasifica (se
> mantiene igual); un **Canonicalizer** transforma alias → canónico con reglas
> declarativas (`catalogue_aliases.yaml`, ...); el `WorkMatcher` compara solo formas
> ya normalizadas. Es la **única incorporación antes de escribir código de V2.1.1**.
| **V2.1.2** | Matching | `WorkMatcher` real, `WorkMerge`, coincidencias, puntuación explicable |

> **V2.1.2 ✅ Hecho.** Contrato congelado en `docs/work-matcher-design.md` e
> implementado: `MatchLevel` (SAME/POSSIBLE/DIFFERENT), `field_score` continuo
> (título parcial 0.6), `MatchReason` tipado sin `matched`, `FieldComparison.SKIPPED`,
> el matcher itera `config.weights` (campos desactivables sin código) y las reglas de
> veto (catálogo → DIFFERENT) y coincidencia segura (authority → SAME) viven en
> `MatchingConfig`, no en el código. El `WorkMatcher` V2.0 se renombró a
> `WorkGroupingMatcher` para eliminar la colisión.
| **V2.1.3** | Ranking | pesos **medidos** (no decididos), ranking de obras, paginación, filtros |

> **Diseño**: `docs/ranking-design.md` (V2.1.3). Principio: **el Ranking nunca cambia
> la identidad de una obra; solo ordena las alternativas** (WorkMatcher decide,
> Ranking ordena). Se rankean **obras** (`WorkGroup`), no candidatos; `score =
> peso_objetivo×objective + peso_preferencia×preference`; métricas objetivas vs
> preferencias; `NDCG@k`/`MRR` sobre un golden set para medir mejora; `WorkRankScore`
> alimenta al Evidence Engine. No se escribe código hasta congelar el diseño.

**Alcance**
- Con OMR e IMSLP funcionando (V2.0.5/0.6), mejorar: sinónimos, transliteración,
  búsquedas por catálogo, normalización y ranking textual.
- Motor de búsqueda definitivo sobre `WorkMatcher` / `WorkGrouper` / `Lexicon`.
- Aprovechar el subsistema de datasets (PDMX) e IMSLP como fuentes indexadas.

**Criterios de salida**
- Documento de diseño estable antes de la implementación.
- `osap search` consistente entre proveedores (OpenScore, PDMX, IMSLP).
- Búsqueda correcta en acentos/mayúsculas/parcial.
- Sin IA / embeddings / LLM / búsqueda semántica: solo conocimiento musicológico.

---

## V2.2 — Evidence Engine

**Alcance**
- Responde a una única pregunta: **¿por qué OSAP ha elegido esta representación?**
- Modelo **completamente estructurado** (sin IA, sin lenguaje natural): `Evidence`
  con `reasons` (confidence, format, public_domain, quality, completeness, checksum),
  `metrics`, `provider`, `checksum`, `ranking_score`. Asociado al `ResolveResult`.
- Versión definitiva: motor de jobs asíncronos para adquisición/validación no
  bloqueante y verificación de dedup/fusión.

**Estado:** núcleo ✅ **Hecho** (modelo estructurado + `EvidenceEngine`); queda el
scope definitivo (jobs + dedup/merge).

**Criterios de salida**
- Cada `ResolveResult` con candidato elegido incluye `Evidence` trazable.
- Deduplicación/fusión se aplica de forma verificable.

---

## V2.3 — MuseScore

**Alcance**
- Nuevo adaptador `catalogs/musescore` sobre el catálogo MuseScore/OpenScore.
- Cliente HTTP dedicado; gestión de licencias y de la API de MuseScore.
- `IResourceProvider` aplicado a los recursos que MuseScore declare.

**Criterios de salida**
- `osap search/resolve` incluyen MuseScore con el mismo contrato que IMSLP/OpenScore.

---

## V2.4 — YouTube

**Alcance**
- Adquisición audiovisual: `catalogs/youtube` (audio/referencia), no como fuente
  principal de partituras sino como evidencia y referencia de interpretación.
- Integración en `ResolveResult` como fuente auxiliar (no compite con las partituras).

**Criterios de salida**
- OSAP enlaza/obtiene la interpretación de referencia de una obra cuando existe.

---

## V3 — Inteligencia musical

**Alcance** (todo lo ⏳ de la auditoría)
- Knowledge Base (`knowledge_base/*`) y aprendizaje de la plataforma.
- IA avanzada: embeddings, aprendizaje automático, análisis armónico profundo,
  OMR/IA asistida (Audiveris ya presente como adaptador).
- Personalización con `user_profile/*`.

**Criterios de salida**
- OSAP mejora la resolución con conocimiento acumulado y asiste la conversión
  cuando no hay datos estructurados.

---

## Qué NO está en el roadmap

- No se reinventa la arquitectura (dominio/puertos/aplicación/infraestructura).
- No se construye IA (embeddings, ML, armónico profundo) antes de V3.
- No se tocan `knowledge_base`, `pipeline` definitivo ni `user_profile` hasta su versión.
- No se implementa exportación/CDN dentro de OSAP: eso es OMR.
- No hay camino especial para OMR: es un `ICatalogProvider` más.
- No se consultan cosas complejas directamente a OMR: siempre búsqueda en dos fases (ADR-0019).
- **El núcleo ya está maduro.** No se tocan `ProviderOrchestrator`, `Evidence`,
  `Aggregator`, `Ranking`, `SearchRequest` ni `ResolveRequest` salvo que un proveedor
  real obligue a cambiarlos. No se cambia el diseño por nuevas posibilidades.
