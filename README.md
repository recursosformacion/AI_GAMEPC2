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

- [Arquitectura](docs/architecture.md)
- [Pipeline](docs/pipeline.md)
- [Subsistema de datasets](docs/datasets.md)
- [Modelo de calidad](docs/quality.md)
- [Knowledge Base](docs/knowledge_base.md)
- [Jobs (procesamiento asíncrono)](docs/jobs.md)
- [API REST (contrato)](docs/api.md)
- [Frontend React (contrato)](docs/frontend.md)
- [Responsabilidades](docs/responsibilities.md)
- [ADRs](docs/adr/)

### Desarrollo

```bash
pip install -e .
mypy --strict
ruff check src tests
pytest tests/
```
