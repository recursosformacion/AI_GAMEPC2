# Architecture Audit 2026

> **Status: completed**
>
> Documento congelado. No se vuelve a editar: refleja el reinicio de OSAP y la
> limpieza aplicada (2026-08-05). Cualquier auditoría futura se escribe como
> `architecture-audit-YYYY.md`; no se reescribe la historia.
>
> Las auditorías anteriores se eliminaron; este documento es la fuente de verdad
> del reinicio.

## Propósito

Auditar la totalidad de `src/osap/` **contra el código real**, no contra la
intención. Cada módulo se clasifica en una de cuatro categorías:

1. **Se queda** — responsabilidad que sigue siendo de OSAP (resolución de obras).
2. **Se mueve a Open Music Repository (OMR)** — servir/almacenar/distribuir.
3. **Se elimina** — esqueletos muertos, provisionales, duplicados, falsos.
4. **Se aplaza** — se construirá, pero aún no merece la pena.

La arquitectura actual se considera **buena** (dominio + puertos + aplicación +
infraestructura, DI, metadata-first, dataset-first). No se reinventa: se hace
crecer. Este documento identifica **qué** conservar, **qué** trasladar y **qué**
retirar antes de empezar la V2.

## Estado real del código

- `src/osap/domain/` — 40+ objetos de dominio, inmutables, sin deps externas. Sólido.
- `src/osap/ports/` — 20+ contratos. Sólido.
- `src/osap/application/` — la lógica real de resolución/búsqueda/agrupación. Sólido.
- `src/osap/infrastructure/` — mezcla de **implementaciones reales** y **esqueletos `NotImplementedError`**.
- `src/osap/bootstrap/`, `cli/`, `api/` — cableado, CLI y REST. Funcionales.
- `lexicon/*.yaml` — datos de normalización musical (varios vacíos o provisionales).
- `chorus/` — aplicación consumidora (Chorus Study Generator), mayormente esqueleto; **proyecto aparte**.

### Implementaciones reales frente a esqueletos

Con `NotImplementedError` (esqueleto): `adapters/export/*` (5), `adapters/library/git`,
`adapters/validation/basic_validator` (parcial), `catalogs/cpdl`, `catalogs/filesystem`,
`datasets/dataset_installer`, `datasets/dataset_registry` (interfaz),
`knowledge_base/*`, `merge/merge_engine`, `resources/*` (parcial), y varios `ports/*`
(interfaces, normal). El resto es código real.

---

## 1. Se queda — núcleo de OSAP (resolución de obras)

La responsabilidad central de OSAP es: **dado un `WorkDescriptor`, localizar,
evaluar, seleccionar y obtener la mejor representación disponible**.

### Dominio
`domain/` completo: `WorkDescriptor`, `CandidateRepresentation`, `ResolveRequest`,
`ResolveResult`, `Resource`, `MusicalSource`, `MusicalDocument`, `Score`, `Edition`,
`Arrangement`, `QualityReport`, `RankingConfig`, `CatalogInfo/Capabilities/Status`,
`DatasetDescriptor`, `Job`, `Event`, `Errors`, `ValueObjects`, etc.
La identidad musical y el modelo de resolución **son** OSAP.

### Puertos
`ports/` completo como contrato de la plataforma: `ICatalogProvider`,
`IResourceProvider`, `IRankingEngine`, `IWorkResolver`, `IScoreValidator`,
`IScoreExporter`, `ILibraryProvider`, `IKnowledgeBase`, `IDuplicateResolver`,
`IMergeEngine`, `ICredentialStore`, `IJobRunner`, `IEventBus`, `IMetrics`,
`IUserProfile`.

### Aplicación
`application/` completo: `WorkResolutionEngine`, `CatalogManager`, `ResourceManager`,
`WorkResolver`, `WorkMatcher`, `WorkGrouper`, `WorkMergeService`, `RepresentationIdentity`,
`MetadataNormalizer`, `MetadataParser`, `CanonicalMetadata`, `NormalizedMetadata`,
`ResourceResolver`, `Acquisition`, `LibraryManager`, `CapabilitiesDto`, `Lexicon`.
Es la lógica de negocio de OSAP.

`ExportManager` se queda **únicamente para exportaciones del usuario** (bundle JSON,
informe, resultados). La producción de MusicXML/PDF/MEI/MIDI/JSON para **servir** no es
de OSAP: pertenece a OMR (ver «Se mueve»).

### Infraestructura (adquisición y soporte)
- `catalogs/{imslp, openscore, cpdl, pdmx, local, filesystem}` y `hf/huggingface_catalog_provider`
  → **adaptadores de adquisición**. El corazón de OSAP.
- `rankings/DefaultRankingEngine` → criterios ponderados.
- `resources/*` → instalación/gestión de recursos (datasets, modelos).
- `datasets/*` → subsistema de datasets (índice PDMX).
- `dedup/DuplicateResolver`, `merge/MergeEngine` → identidad y fusión de obras.
- `adapters/validation/basic_validator` → validación de partituras.
- `adapters/library/local/LocalLibrary` → almacén local de lo resuelto (salida cliente).
- `http/http_client`, `github/GitHubClient`, `mediawiki/MediaWikiClient`,
  `hf/HuggingFaceDatasetInstaller` → clientes necesarios para los catálogos.
- `auth/*` → credenciales de proveedores.
- `cache/InMemoryCache`, `events/InMemoryEventBus` → infraestructura base.
- `adapters/export/musicxml` → se mantiene **solo como stub cableado** en espera de OMR
  (ver decisiones).

### Provider Orchestrator — la pieza que falta

Hoy la orquestación de proveedores está **repartida** dentro de
`WorkResolutionEngine`: decide quién se consulta, con qué prioridad, en qué orden y
cuándo parar. No se propone arquitectura nueva, sino **ponerle nombre y hacerla
explícita** como componente de aplicación:

- `ProviderOrchestrator` — decide **a quién se pregunta primero y después**, si se
  **paraleliza**, si se **espera** o se **cancela**.
- `ProviderExecutionPlan` — el plan de ejecución resultante (orden, timeouts, límites).
- `ProviderResultAggregator` — reúne y normaliza los resultados de los proveedores.

Responde a: cuándo dar la búsqueda por terminada, cuándo merece la pena consultar un
proveedor lento y cuándo reutilizar una búsqueda anterior. Es el **corazón de V2**.

### Bootstrap, CLI, API
`bootstrap/` (`Configuration`, `Container`, `wiring`), `cli/main.py`,
`api/app.py`, `api/dto.py` → el cliente OSAP. Permanecen.

### Datos
`lexicon/*.yaml` que tengan contenido real (arrangement, forms, instruments,
liturgical, movemets, notes, performing_forces, phrases) → datos del núcleo de
normalización. **Depurar los vacíos** (ver «Se elimina»).

---

## 2. Se mueve a Open Music Repository (OMR)

Responsabilidades de **servir / almacenar / distribuir** representaciones, no de
resolverlas. Cuando OMR exista, estos módulos viven allí; hoy solo hay esqueletos.

| Módulo | Responsabilidad | Nota |
|--------|-----------------|------|
| `adapters/library/git/GitLibrary` | Almacén git como repositorio/CDN | Esqueleto `NotImplementedError`. Construir en OMR. |
| `adapters/export/{musicxml, mei, midi, pdf, json}` | Producción de formatos servibles | 4 esqueletos muertos + musicxml stub cableado. La emisión de MusicXML/PDF/MEI/MIDI/JSON para servir pertenece al repositorio OMR. |
| `metrics/*` (estadísticas de uso/rendimiento) | Métricas del repositorio | Las estadísticas de contenido y uso son de OMR. |

> Matiz abierto: si OSAP necesita **exportar a un formato para el usuario final**
> (p. ej. PDF de estudio local), esa exportación "cliente" puede quedarse en OSAP.
> Lo que se mueve a OMR es la **producción para servir/distribuir**.

---

## 3. Se elimina

Código muerto, provisional, duplicado o vacío. Candidato a borrar en el reinicio.

> **Ejecutado el 2026-08-05**: todos los ítems marcados 🗑 en la checklist se han
> eliminado y verificado (`pytest` 209 pass, `mypy` limpio).

| Ítem | Razón |
|------|-------|
| `adapters/export/{mei, pdf, json, midi}/*_exporter.py` | Esqueletos `NotImplementedError` sin valor; se recrearán en OMR cuando toque. |
| `adapters/library/git/GitLibrary` | Esqueleto; ya migrado conceptualmente a OMR. |
| `knowledge_base/in_memory_knowledge_base.py` | Esqueleto de un subsistema que hoy no se usa (se aplaza). Borrar o congelar hasta V3. |
| `gold_dataset/` | Directorio vacío. |
| `lexicon/catalogue_prefixes.yaml`, `genres.yaml`, `instrumentation.yaml`, `languages.yaml`, `opus_prefixes.yaml` | Ficheros de **0 bytes** (falsos). |
| `lexicon/sinAsignar.yaml`, `lexicon/sinAsignarTexto.yaml` | Provisional / basura de normalización. |
| Duplicados o utilidades provisionales que aparezcan al limpiar | Verificar con búsqueda de imports antes de borrar. |

> Regla de seguridad: antes de eliminar cualquier archivo de código, verificar con
> `grep`/`rg` que no esté importado en `wiring.py`, `cli`, `api` o tests.

---

## 4. Se aplaza

Se sabe que existirán, pero no se construyen todavía.

| Módulo | Cuándo |
|--------|--------|
| `knowledge_base/*` | V3 (aprendizaje de la plataforma). |
| `pipeline/*` (motor de pipeline definitivo) | Cuando se fije el pipeline canónico de resolución (V2.1+). El `PipelineEngine` actual es mínima. |
| `user_profile/*` | Personalización; sin demanda todavía. |
| `adapters/export/*` (construcción real) | Con OMR (V2.0). |
| IA avanzada: embeddings, aprendizaje automático, análisis armónico profundo | V3 — **no tocar ahora**. |

---

## Checklist de ejecución (estado real, verificado)

Recorrido módulo a módulo contra el árbol actual. Estado verificado el 2026-08-05
con `pytest` (209 pass), `mypy --strict` (limpio) y `ruff`.

### Aplicación — `application/`
| Módulo | Estado |
|--------|--------|
| `work_resolution_engine`, `work_resolver`, `work_matcher`, `work_grouper`, `work_merge_service`, `representation_identity`, `resource_resolver`, `resource_resolver`, `acquisition`, `catalog_manager`, `library_manager`, `metadata_normalizer`, `metadata_parser`, `canonical_metadata`, `normalized_metadata`, `capabilities_dto`, `lexicon` | ✅ se queda |
| `export_manager` | ✅ se queda (solo exportaciones de usuario: bundle/informe/resultados) |
| `use_cases/*` | ✅ se queda |

### Dominio y puertos — `domain/`, `ports/`
| Módulo | Estado |
|--------|--------|
| `domain/*` completo | ✅ se queda |
| `ports/*` completo | ✅ se queda (incl. `IKnowledgeBase`, contrato para V3) |

### Infraestructura — `infrastructure/`
| Módulo | Estado |
|--------|--------|
| `catalogs/{imslp, openscore, cpdl, pdmx, local, filesystem}`, `hf/huggingface_catalog_provider` | ✅ se queda (adquisición) |
| `rankings/default_ranking_engine`, `resources/*`, `datasets/*`, `dedup/*`, `merge/*`, `http/*`, `github/*`, `mediawiki/*`, `auth/*`, `cache/*`, `events/*`, `adapters/validation/basic_validator`, `adapters/library/local` | ✅ se queda |
| `adapters/export/musicxml` | ✅ se queda (stub cableado, en espera de OMR) |
| `jobs/*`, `pipeline/*`, `metrics/*`, `user_profile/*`, `knowledge_base/*` | ✅ se queda (cableado, mínimo) · ⏳ versión definitiva aplazada |
| `adapters/export/{mei,pdf,json,midi}` | 🗑 **eliminado** (esqueletos muertos) |
| `adapters/library/git` | 🗑 **eliminado** (esqueleto; su home es OMR 📦) |

### Bootstrap, CLI, API
| Módulo | Estado |
|--------|--------|
| `bootstrap/{configuration,container,wiring}`, `cli/main.py`, `api/{app,dto}` | ✅ se queda |

### Datos y miscelánea
| Ítem | Estado |
|------|--------|
| `lexicon/*.yaml` con contenido (arrangement, forms, instruments, liturgical, movemets, notes, performing_forces, phrases) | ✅ se queda |
| `lexicon/*.yaml` de 0 bytes (catalogue_prefixes, genres, instrumentation, languages, opus_prefixes) | 🗑 **eliminado** |
| `lexicon/sinAsignar*.yaml` | ✅ se queda (salida de runtime de `Lexicon`; se ignoran al cargar) |
| `gold_dataset/` | 🗑 **eliminado** (vacío) |
| `chorus/` | fuera del alcance OSAP (proyecto consumidor; ver decisiones) |

---

## Decisiones abiertas

1. **`chorus/`**: proyecto consumidor aparte, mayormente esqueleto. ¿Se elimina el
   esqueleto y se reconstruye sobre OSAP V2, o se mantiene? Recomendación: sacarlo
   del repo de OSAP a su propio repositorio cuando se reinicie.
2. **Exportación cliente**: confirmar si OSAP debe exportar a formato local para el
   usuario final (entonces `ExportManager` + un exporter local se quedan) o si toda
   la exportación es responsabilidad de OMR.
3. **`jobs/` + `events/`**: la API los usa para resolución asíncrona. Mantener el
   mínimo hoy; el motor definitivo de jobs se aplaza a V2.2.
4. **`catalogs/cpdl` y `catalogs/filesystem`** son esqueletos: ¿se completan (V2.4-IMSLP/CPDL)
   o se retiran hasta que toque? Recomendación: mantener como esqueletos con contrato, no implementar aún.

---

## Principios que rigen OSAP V2

- **Work-centric** (ADR-0010): se resuelve la obra, no el documento.
- **Metadata-first** (ADR-0011): nunca buscar leyendo MusicXML.
- **Dataset-first** (ADR-0012): los datos estructurados tienen prioridad sobre OMR/IA.
- El dominio solo conoce `WorkDescriptor`, `CandidateRepresentation`, `ResolveRequest`,
  `ResolveResult` y `Resource`.
- **No reinventar la arquitectura**: se conserva dominio/puertos/aplicación/infraestructura.
- OSAP **resuelve**; OMR **sirve**. Cada pieza vive donde le corresponde.
