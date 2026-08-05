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

Leyenda de impacto (de la auditoría):
- 🔒 **Núcleo** = se queda.
- 📦 **OMR** = se mueve a Open Music Repository (la aplicación repositorio).
- 🗑️ **Eliminar** = se retira.
- ⏳ **Aplazar** = no se toca todavía.

---

## V2.0 — Freeze public contracts

Se **definen por escrito** los contratos públicos de OSAP. `docs/provider-contract.md`
es la especificación definitiva.

**Alcance**
- `search()` / `resolve()` / `download()` / `metadata()` / `capabilities()`.
- Contratos de dominio congelados: `SearchRequest`, `ResolveRequest`,
  `ResourceBundle`, `Work`, `Representation`, `Evidence`.
- `ProviderExecutionPlan` (como contrato) y `ProviderOrchestrator` (como concepto).

**Criterios de salida**
- `docs/provider-contract.md` revisado y aceptado.
- Los contratos de dominio están escritos y no cambian por implementación.

---

## V2.0.1 — Adaptar el núcleo al nuevo contrato

Todavía no se tocan proveedores. Solo cambia el **núcleo** para que piense con los
nuevos contratos.

**Alcance**
- `SearchRequest`, `ResolveRequest`, `WorkDescriptor`, `CandidateRepresentation`,
  `AcquisitionResult`, `CatalogCapabilities`, `CostLevel` son los **únicos objetos**
  que circulan por el sistema.
- Los servicios de aplicación (`WorkResolutionEngine`, `WorkMatcher`, ...) se alinean
  a estos tipos.
- No se modifica ningún proveedor.

**Criterios de salida**
- El núcleo compila y pasa tests pensando en los contratos nuevos.
- `ruff` / `mypy` limpios.

---

## V2.0.2 — ProviderOrchestrator

Aquí empieza realmente la V2. Todo pasa por `ProviderOrchestrator`, no por llamadas
directas de cada comando a un proveedor.

**Flujo**
```
Search
   ↓
ExecutionPlan
   ↓
IMSLP | OMR | MuseScore | Filesystem | ...
   ↓
Aggregator
   ↓
Ranking
   ↓
Resultado
```

**Alcance**
- `ProviderOrchestrator` decide el plan de ejecución; no necesita ser inteligente.
  Puede empezar con un plan fijo:
  ```
  ExecutionPlan:
    1. Filesystem
    2. OMR
    3. IMSLP
  ```
- `ProviderExecutionPlan` y `ProviderResultAggregator` como contratos.
- Usa `CatalogCapabilities` (incl. `cost_level` y campos de búsqueda) para decidir.
- Es el componente que convierte a OSAP en una **plataforma multiproveedor real**.

**Criterios de salida**
- `osap search/resolve` fluyen a través del orquestador.
- Añadir un proveedor = implementar el contrato, no modificar el núcleo.

---

## V2.0.3 — OMR Provider

**Alcance**
- Open Music Repository como `ICatalogProvider` estándar.
- Implementa exactamente `search()`, `resolve()`, `download()`, `metadata()`,
  `capabilities()`.
- **Nada más.** Sin privilegios, sin rutas especiales, sin `if provider == omr`.
- OSAP **no publica** nada en OMR; OMR ya contiene sus propios recursos.

**Criterios de salida**
- `osap search/resolve` consulta OMR como un proveedor más.

---

## V2.0.4 — IMSLP

**Alcance**
- Adaptar `catalogs/imslp` al contrato (hoy adaptador real pero parcial).
- MediaWiki como índice, descarga, múltiples formatos, metadata rica, licencias y
  dominio público.
- `mediawiki/MediaWikiClient` y `auth/*` a producción (credenciales por proveedor).

**Criterios de salida**
- Con OMR e IMSLP funcionando hay **dos proveedores reales** bajo el mismo contrato.
- `resolve` y `download` con IMSLP de extremo a extremo, con metadata-first.

---

## V2.1 — Nuevo Search Engine

**Alcance**
- Motor de búsqueda definitivo sobre `WorkMatcher` / `WorkGrouper` / `Lexicon`.
- Búsqueda tolerante, sinónimos, transliteración, por compositor/obra/movimiento.
- Aprovechar el subsistema de datasets (PDMX) e IMSLP como fuentes indexadas.
- `WorkResolutionEngine` fija el **pipeline canónico** de resolución (sobre el
  `ProviderOrchestrator` de V2.0.2).

**Criterios de salida**
- `osap search` consistente entre proveedores (OpenScore, PDMX, IMSLP).
- Búsqueda correcta en acentos/mayúsculas/parcial (ya hay tests, ampliar al dataset real).

---

## V2.2 — Evidence Engine definitivo

**Alcance**
- Sustituir la selección por ranking simple por un **motor de evidencia**: cada
  representación se justifica (fuente, calidad, licencia, confianza, checksum).
- `QualityReport` y `ScoreRanking` se convierten en el contrato de evidencia.
- Motor de jobs asíncronos definitivo (hoy `InMemoryJobEngine` mínimo) para adquisición
  y validación no bloqueante.

**Criterios de salida**
- Cada `ResolveResult` incluye evidencia trazable de por qué se eligió.
- Deduplicación/fusión (`Dedup`/`Merge`) se aplica de forma verificable.

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
