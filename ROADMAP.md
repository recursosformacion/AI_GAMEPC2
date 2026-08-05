# ROADMAP OSAP — V2

> Reinicio de OSAP. El punto de partida es la **Architecture Audit 2026**
> (`docs/architecture-audit.md`, congelada). Los hitos aquí son **versiones de
> plataforma**, no sprints; cada versión tiene criterios de salida verificables.
>
> El contrato de proveedores se define en `docs/provider-contract.md` y es el
> documento más importante de la V2: todos los proveedores obedecen el mismo
> contrato.

Principios de V2:
- **OMR es un proveedor más.** Para OSAP, IMSLP, MuseScore, CPDL, OpenScore,
  Open Music Repository, Filesystem y PDMX son exactamente iguales: todos
  implementan `ICatalogProvider`. No existe un camino especial para OMR. Eso
  mantiene a OSAP independiente.
- **Freeze primero, código después.** Los contratos se escriben antes de
  implementar. IMSLP, MuseScore, OMR... todos obedecen el mismo contrato.

Leyenda de impacto (de la auditoría):
- 🔒 **Núcleo** = se queda.
- 📦 **OMR** = se mueve a Open Music Repository (la aplicación repositorio).
- 🗑️ **Eliminar** = se retira.
- ⏳ **Aplazar** = no se toca todavía.

---

## V2.0 — Freeze public contracts

No se escribe código todavía. Se **definen por escrito** los contratos públicos de OSAP.

**Alcance**
- `docs/provider-contract.md` (o `provider-protocol.md`) con, por cada operación:
  - `search()`: entrada, salida, errores.
  - `resolve()`: entrada, salida, representaciones, licencias.
  - `download()`: acceso directo, acceso manual, streaming.
  - `provider capabilities`: qué soporta cada proveedor.
  - `costs`: coste de uso (OMR cuesta dinero; IMSLP no; Filesystem no). OSAP debe
    conocer ese dato.
  - `quality`: significado de `confidence`, `quality`, `completeness`.
- Contratos de dominio congelados: `ResourceBundle`, `Work`, `Representation`,
  `Evidence`.
- Se escriben, **no se implementan**.

**Criterios de salida**
- `docs/provider-contract.md` revisado y aceptado.
- Los contratos de dominio están escritos y no cambian por implementación.

---

## V2.1 — Integración con Open Music Repository

**Alcance**
- Registrar OMR como `ICatalogProvider` estándar, igual que IMSLP o PDMX.
- Crear el contrato de integración OSAP ↔ OMR (protocolo, autenticación, modelos).
- OSAP consulta OMR **como un proveedor más** y obtiene recursos cuando existen.
  OSAP **no publica** nada en OMR; OMR ya contiene sus propios recursos.
- Mover a OMR: `adapters/export/*`, `adapters/library/git`, `metrics/*` (OSAP no les
  publica; son responsabilidad de la aplicación repositorio OMR).
- Aplicar la clasificación de la auditoría (borrar lo marcado 🗑️, congelar lo ⏳).

**Criterios de salida**
- `osap resolve` consulta OMR como proveedor y obtiene la representación cuando existe.
- Tests verdes y `ruff`/`mypy` limpios.

---

## V2.2 — Nuevo Search Engine

**Alcance**
- Motor de búsqueda definitivo sobre `WorkMatcher` / `WorkGrouper` / `Lexicon`.
- Búsqueda tolerante, sinónimos, transliteración, por compositor/obra/movimiento.
- Aprovechar el subsistema de datasets (PDMX) e IMSLP como fuentes indexadas.
- `WorkResolutionEngine` fija el **pipeline canónico** de resolución.
- **Provider Orchestrator** explícito (`ProviderOrchestrator` → `ProviderExecutionPlan`
  → `ProviderResultAggregator`) como corazón de V2: decide a quién se pregunta primero
  y después, si se paraleliza, si se espera o se cancela, cuándo se da la búsqueda por
  terminada, cuándo merece la pena un proveedor lento y cuándo se reutiliza una búsqueda
  anterior. No es nueva arquitectura: pone nombre al orquestador que hoy está repartido
  en `WorkResolutionEngine`.

**Criterios de salida**
- `osap search` consistente entre proveedores (OpenScore, PDMX, IMSLP).
- Búsqueda correcta en acentos/mayúsculas/parcial (ya hay tests, ampliar al dataset real).

---

## V2.3 — Evidence Engine definitivo

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

## V2.4 — IMSLP completo

**Alcance**
- Completar `catalogs/imslp` (hoy adaptador real pero parcial): MediaWiki como índice,
  descarga, múltiples formatos, metadata rica, licencias y dominio público.
- `mediawiki/MediaWikiClient` y `auth/*` a producción (credenciales por proveedor).

**Criterios de salida**
- `resolve` y `download` con IMSLP de extremo a extremo, con metadata-first.
- Catalogada la cobertura real y los fallos conocidos del scrape.

---

## V2.5 — MuseScore

**Alcance**
- Nuevo adaptador `catalogs/musescore` sobre el catálogo MuseScore/OpenScore.
- Cliente HTTP dedicado; gestión de licencias y de la API de MuseScore.
- `IResourceProvider` aplicado a los recursos que MuseScore declare.

**Criterios de salida**
- `osap search/resolve` incluyen MuseScore con el mismo contrato que IMSLP/OpenScore.

---

## V2.6 — YouTube

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
