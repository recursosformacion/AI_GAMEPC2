# OSAP — Arquitectura (Work-Centric + Catalog + Resource)

OSAP es una plataforma de **resolución de recursos musicales**. El usuario pide
una obra; OSAP localiza, evalúa, selecciona y obtiene la mejor representación
disponible, gestionando automáticamente los recursos que necesita. El usuario
nunca piensa en PDMX, OpenScore, IMSLP, Hugging Face o GitHub.

## Principios

- Clean/Hexagonal: el dominio es el centro; la infraestructura depende del dominio.
- DDD: objetos de dominio inmutables y fuertemente tipados.
- DI, Composition over Inheritance, Open/Closed.
- **Work-Centric**: se resuelve la obra (`WorkDescriptor`), no el documento.
- **Metadata-first**: nunca se busca leyendo MusicXML.
- **Dataset-first**: los datos estructurados tienen prioridad sobre OMR/IA.
- **Resource management transparente**: OSAP decide automáticamente qué
  recursos (datasets, catálogos, modelos, cachés, knowledge bases) hacen falta,
  los descarga bajo demanda y nunca obliga al usuario a conocerlos.
- El dominio **nunca** conoce Hugging Face, IMSLP, CPDL, OpenScore, PDMX ni GitHub.

## El dominio solo conoce

`WorkDescriptor` · `CandidateRepresentation` · `ResolveRequest` · `ResolveResult` · `Resource`

## Diagrama de arquitectura

```
                        ┌───────────────────────────────┐
                        │            Domain             │
                        │  WorkDescriptor, CandidateRep,│
                        │  ResolveRequest, ResolveResult,│
                        │  Resource, CatalogCapabilities│
                        └──────────────┬────────────────┘
                                       │
              ┌────────────────────────▼────────────────────────┐
              │                        Ports                    │
              │  ICatalogProvider      IResourceProvider        │
              │  IRankingEngine        IWorkResolver            │
              │  IScoreValidator       IScoreExporter           │
              │  ILibraryProvider      IKnowledgeBase           │
              └────────────────────────┬────────────────────────┘
                                       │
              ┌────────────────────────▼────────────────────────┐
              │                  Application                     │
              │  WorkResolutionEngine  CatalogManager           │
              │  ResourceManager        WorkResolver            │
              │  RankingEngine          Managers                │
              └────────────────────────┬────────────────────────┘
                                       │
              ┌────────────────────────▼────────────────────────┐
              │              Infrastructure                     │
              │  catalogs/ (IMSLP, OpenScore, CPDL, Local,       │
              │           Filesystem, HuggingFace)               │
              │  resources/ (HuggingFaceResourceProvider)        │
              │  rankings/  export/  library/  validation/  http/│
              └──────────────────────────────────────────────────┘
```

## Flujo de resolución

```
ResolveRequest
   │
   ▼
WorkResolutionEngine
   │
   ├─► ResourceManager  (asegura los recursos de cada catálogo, instala si es
   │                     necesario, de forma transparente o con aprobación)
   │
   ├─► CatalogManager → ICatalogProviders  ──► CandidateRepresentation[]
   │
   ├─► RankingEngine  (selección)
   │
   └─► (opcional) Download ──► ResolveResult
```

## Separación de responsabilidades

| Componente       | Responsabilidad                                                     |
|------------------|---------------------------------------------------------------------|
| `ICatalogProvider` | Responde **preguntas musicales** (search/resolve/download/metadata/capabilities). **Nunca instala recursos.** |
| `IResourceProvider` | Gestiona la instalación de un **recurso** (install/update/remove/exists/status/metadata). |
| `ResourceManager` | Decide automáticamente qué recursos usar, descargar o actualizar; sin intervención del usuario salvo aprobación justificada. |
| `CatalogManager` | Registra proveedores de catálogo y lista capacidades.               |

## Capas y responsabilidades

| Capa            | Contenido                                                             |
|-----------------|----------------------------------------------------------------------|
| `domain`        | WorkDescriptor, CandidateRepresentation, ResolveRequest/Result, Resource, enums, VOs; sin dependencias externas |
| `ports`         | ICatalogProvider, IResourceProvider, IRankingEngine, IWorkResolver, validators/exporters/library/knowledge-base |
| `application`   | WorkResolutionEngine, CatalogManager, ResourceManager, WorkResolver, RankingEngine, managers |
| `infrastructure`| catálogos (IMSLP real, HF confinado, esqueletos), recursos (HF), ranking, export, library, validation, http |
| `bootstrap`     | `Container`, `Configuration`, `wiring`                               |

## Subsistema de datasets

| Componente            | Responsabilidad                                                         |
|-----------------------|-------------------------------------------------------------------------|
| `DatasetRegistry`     | Registro declarativo de datasets (nombre, tamaño, licencia, formatos, url, estado, versiones). Nunca hardcodea PDMX. |
| `DatasetInstaller`    | Descarga real vía Hugging Face (progreso, reanudar, verificar hash, espacio, cancelar, borrar, actualizar). Solo bajo petición. |
| `DatasetManager`      | `install/update/remove/list/status/verify/repair/location/info`.        |
| `DatasetSettings`     | `cache_dir, streaming, num_proc, offline, download_mode, max_disk_usage`. Configurable, nunca hardcodeado. |
| `MusicQueryNormalizer`| Normaliza términos de búsqueda (acentos, mayúsculas, parcial, idioma).   |

En la resolución, un dataset no instalado se reporta como `SKIPPED / Dataset
not installed` (nunca error, sin penalizar); el sistema continúa con el resto de
proveedores. La consulta de datasets usa siempre `Dataset.filter()/select()/
map()/iter()`, nunca `for item in dataset`.

## Plataforma (API REST / React / automatización)

| Componente          | Responsabilidad                                                    |
|---------------------|--------------------------------------------------------------------|
| `IEventBus`         | Eventos (Provider*, Dataset*, ScoreValidated, LibraryStored, Job*, Stage*) para UI/monitor/WebSocket |
| `IJobRunner`        | `Job` asíncronos (id/type/state/progress/logs/result) para operaciones largas |
| `IPipelineEngine`   | Compone etapas-plugin (`IPipelineStage`) dinámicamente            |
| `IDuplicateResolver`| Decide si dos representaciones son la misma obra (sin proveedor)  |
| `IMergeEngine`      | Combina fuentes (OpenScore + Audiveris + humano) en un Score      |
| `QualityReport`     | Calidad multidimensional (Structure, Notation, Lyrics, Harmony, Voices, Metadata, Attachments) → `QualityLevel` |
| `IMetricsCollector` | Métricas (tiempos, éxito, calidad, proveedor, tamaño, memoria)     |
| `IUserProfileStore` | Preferencias de usuario para el ranking                           |
| `ICache`            | Caché con TTL/versionado para no re-descargar                     |
| `IKnowledgeBase`    | Aprendizaje estadístico (sin ML) para priorizar estrategias        |

El contrato de la futura API REST y del frontend React se documenta en
[`api.md`](api.md) y [`frontend.md`](frontend.md).

## Invariantes

- El dominio nunca importa de infraestructura ni conoce librerías concretas.
- `datasets` (Hugging Face) solo existe en `infrastructure.hf` (importación perezosa).
- `CatalogProvider` nunca instala recursos; `ResourceProvider` nunca responde preguntas musicales.
- `ResolveResult` explica **por qué** se eligió una representación (y qué fuentes no estuvieron disponibles).
- Objetos inmutables; DI en todo el sistema.
