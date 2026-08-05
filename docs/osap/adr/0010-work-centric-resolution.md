# ADR-0010 – Work-Centric Resolution

## Estado

Aceptado.

## Contexto

La arquitectura previa de OSAP estaba orientada a resolver **documentos**
musicales (PDF, MusicXML, imágenes...). Eso hacía que la unidad principal del
sistema fuera un archivo, lo que dificultaba razonar sobre una misma obra
existente en varios formatos, ediciones, proveedores o niveles de calidad, y
repetía lógica de normalización y comparación entre proveedores.

## Decisión

OSAP pasa a estar orientado a resolver **obras musicales**. La unidad principal
del sistema deja de ser un documento y pasa a ser una `MusicalWork`.

Principio fundamental:

> OSAP nunca intenta resolver un documento.
> Siempre intenta resolver una obra musical.
> Los documentos son únicamente una posible fuente de información.

Una `MusicalWork` es la **identidad** de una obra, independiente del formato y
del repositorio. Contiene título, compositor, libretista, arreglista, idioma,
voces, opus, número de catálogo, alias e identificadores. **No contiene
archivos.**

Cada hallazgo concreto de una obra en un proveedor es una
`CandidateRepresentation` (proveedor, formato, calidad, licencia, URL de
descarga, confianza, metadatos). Una misma obra puede tener decenas de
`CandidateRepresentation`.

### Nuevo pipeline

```
MusicalRequest
   │
   ▼
Work Resolver ──► MusicalWork
   │
   ▼
Lookup Providers ──► CandidateRepresentation[]
   │
   ▼
Ranking Engine
   │
   ▼
Resolution Engine ──► Download ──► Validation ──► Score
                                                  │
                                                  ▼
                                            Export ──► Library
```

- `WorkResolver`: normaliza títulos y compositores, detecta alias y agrupa
  resultados equivalentes procedentes de distintos proveedores.
- `RankingEngine`: ordena las `CandidateRepresentation` según criterios
  configurables (formato, licencia, dominio público, calidad, coincidencia de
  compositor/título, idioma, proveedor, preferencias del usuario, tiempo).
- `ResolutionEngine`: descarga la representación elegida, valida, convierte a
  `Score`, exporta y guarda en la biblioteca.
- `SearchOrchestrator`: solo **busca y ordena** (`CandidateRepresentation[]` →
  ranking → selección). **No descarga automáticamente.**

### Familias de proveedores

- **`IOnlineLookupProvider`**: requieren Internet (IMSLP, CPDL, OpenScore, GitHub, MuseScore).
- **`IOfflineLookupProvider`**: no requieren Internet (biblioteca local, PDMX, repositorio Git, NAS, dataset OSAP).

### Orden de búsqueda por defecto (configurable)

1. Biblioteca local · 2. OpenScore · 3. CPDL · 4. IMSLP · 5. PDMX local ·
6. Adquisición (MusicXML parser) · 7. Audiveris · 8. IA · 9. Human Provider.

## Consecuencias

- El dominio solo conoce `MusicalRequest`, `MusicalWork`, `CandidateRepresentation`, `Score`, `QualityLevel` y `PipelineLog`. **Nunca** conoce IMSLP, CPDL, OpenScore, Audiveris, MuseScore ni PDMX.
- `PdmxProvider` se **renombra a `ImslpProvider`** (consulta la API de IMSLP). PDMX queda como TODO para un proveedor **offline** sobre dataset local.
- La biblioteca deja de almacenar solo archivos: **almacena una obra** (carpeta con `work.json`, `metadata.json`, `acquisition.json`, `score.<ext>`, `source.json`), preservando trazabilidad completa.
- El CLI separa `search`, `inspect`, `resolve` y `download`.
- La arquitectura queda lista para crecer sin romper Open/Closed: añadir un proveedor, un criterio de ranking o un formato no exige tocar el núcleo.
