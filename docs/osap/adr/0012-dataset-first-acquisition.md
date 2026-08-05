# ADR-0012 – Dataset-first Acquisition

## Estado

Aceptado.

## Contexto

OSAP puede adquirir una representación por múltiples vías: datasets locales,
proveedores online y procesos de reconstrucción (OMR, IA, entrada humana). Las
reconstrucciones son caras, lentas y propensas a error.

## Decisión

**Siempre que exista una representación estructurada disponible en un dataset
local o remoto, esta tendrá prioridad sobre cualquier proceso de adquisición
mediante OMR o IA.** La reconstrucción de una partitura será siempre el **último
recurso**.

### Orden de resolución

1. **Dataset locales** (PDMX, OpenScore snapshot, CPDL snapshot, biblioteca local) — prioridad máxima.
2. **Lookup providers online** (IMSLP, CPDL, GitHub/OpenScore).
3. **Adquisición** (MusicXML parser, Audiveris, IA, Human) — solo si no existe una representación estructurada.

### Consecuencias

- El `RankingEngine` favorece candidatos con disponibilidad local
  (`local_path`) y datasets estructurados.
- Los procesos de adquisición (Audiveris, IA) se tratan como excepción, no como
  camino principal.
- El `DatasetManager` y el `HuggingFaceDatasetProvider` proveen las
  representaciones estructuradas; los `AcquisitionProvider` quedan reservados
  para cuando no exista ninguna.
