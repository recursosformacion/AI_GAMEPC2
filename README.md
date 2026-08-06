# Chorus Study Generator

Generador de materiales de estudio para coros, construido sobre OSAP.

## OSAP — Open Score Acquisition Platform

OSAP es una plataforma de **resolución de recursos musicales**. El usuario
indica qué obra necesita; OSAP localiza, evalúa, selecciona y obtiene la mejor
representación disponible, gestionando automáticamente los recursos que
necesita. El usuario nunca piensa en PDMX, OpenScore, IMSLP, Hugging Face o
GitHub.

Principios clave:

- **Work-Centric**: se resuelve la obra (`WorkDescriptor`), no el documento.
- **Metadata-first** (ADR-0011): nunca se busca leyendo MusicXML.
- **Dataset-first** (ADR-0012): los datos estructurados tienen prioridad sobre OMR/IA.
- **Resource management transparente**: OSAP decide e instala lo que necesita.
- El dominio solo conoce `WorkDescriptor`, `CandidateRepresentation`, `ResolveRequest`, `ResolveResult` y `Resource`.

### Estructura

```
src/
├── osap/
│   ├── domain/            # WorkDescriptor, ResolveRequest/Result, Resource, VOs
│   ├── ports/             # ICatalogProvider, IResourceProvider, IRankingEngine, ...
│   ├── application/       # WorkResolutionEngine, CatalogManager, ResourceManager
│   ├── infrastructure/    # catalogs/, resources/, export/, library/, rankings/
│   ├── bootstrap/         # Container, Configuration, wiring
│   └── cli/               # osap
├── chorus/
└── shared/
tests/
docs/
├── osap/                    # Documentación de OSAP (por versión)
│   ├── v1/                  # Base / pre-V2 (arquitectura, API, frontend, ...)
│   ├── v2/                  # V2: contratos y diseños (auditoría, provider, search intelligence, ...)
│   ├── adr/                 # Architecture Decision Records
│   └── old/                 # Documentos obsoletos (histórico)
└── chorus-vision.md         # Visión de Chorus (proyecto aparte)
```

### CLI

```bash
pip install -e ".[datasets]"
```

Resolución (uso normal — OSAP gestiona los recursos):

```bash
osap resolve "Mozart Nocturnes"
osap resolve "Mozart Nocturnes" --format musicxml
osap resolve "Ave Maria" --voices SATB --composer "Franz Schubert"
osap download "Die Sterne" --composer "Schubert" --format musicxml
```

Si hay varias versiones, `resolve`/`download` muestran una lista numerada para elegir (o `--index N` para evitar el prompt).

Búsqueda tolerante (acentos, mayúsculas, parcial):

```bash
osap search Schubert          # obras del compositor
osap search Schubert --works  # todas las obras del compositor
osap search "Ave Maria"
osap search nocturne
```

Datasets (instalación explícita, nunca automática):

```bash
osap dataset list
osap dataset info pdmx
osap dataset install pdmx      # muestra progreso
osap dataset verify pdmx
osap dataset location pdmx
```

Gestión (avanzado):

```bash
osap catalog list
osap catalog info openscore
osap resource list
```

### Proveedores

- **OpenScore** (`OpenScore/Lieder`, GitHub): proveedor de referencia, **completamente funcional**. Busca por título/compositor/palabras parciales mediante la GitHub REST API y descarga MusicXML (.mxl) por raw URL, almacenándolos en la biblioteca.
- **PDMX** (Hugging Face): dataset local opcional gestionado por `DatasetManager`; su ausencia en la resolución se reporta como `SKIPPED` (nunca error).
- IMSLP, CPDL, Local, Filesystem: en implementación.

### Documentación

> Índice y estructura: [docs/osap/README.md](docs/osap/README.md)

- [Arquitectura](docs/osap/v1/architecture.md)
- [Contrato de proveedores (V2)](docs/osap/v2/provider-contract.md)
- [Search Intelligence (diseño V2.1)](docs/osap/v2/search-engine-design.md)
- [Normalización explicable (V2.1.1)](docs/osap/v2/normalization-explorable.md)
- [WorkMatcher (diseño V2.1.2)](docs/osap/v2/work-matcher-design.md)
- [Ranking de obras (diseño V2.1.3)](docs/osap/v2/ranking-design.md)
- [Evidence definitivo (diseño V2.2.a)](docs/osap/v2/evidence-design.md)
- [Dedup/Merge (diseño V2.2.b)](docs/osap/v2/dedup-merge-design.md)
- [Auditoría arquitectónica 2026 (congelada)](docs/osap/v2/architecture-audit.md)
- [Pipeline](docs/osap/v1/pipeline.md)
- [Subsistema de datasets](docs/osap/v1/datasets.md)
- [Modelo de calidad](docs/osap/v1/quality.md)
- [Knowledge Base](docs/osap/v1/knowledge_base.md)
- [Jobs (procesamiento asíncrono)](docs/osap/v1/jobs.md)
- [API REST (contrato)](docs/osap/v1/api.md)
- [Frontend React (contrato)](docs/osap/v1/frontend.md)
- [Responsabilidades](docs/osap/v1/responsibilities.md)
- [ADRs](docs/osap/adr/)
- [Documentos obsoletos (histórico)](docs/osap/old/)

### Desarrollo

```bash
pip install -e .
mypy --strict
ruff check src tests
pytest tests/
```
