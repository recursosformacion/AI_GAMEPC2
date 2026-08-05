# ADR-0011 – Metadata-first Architecture

## Estado

Aceptado.

## Contexto

Búsquedas anteriores leían los archivos musicales (MusicXML, PDF) para decidir si
una representación correspondía a la obra solicitada. Esto es lento e
innecesario: un MusicXML de un movimiento puede pesar cientos de kilobytes y un
dataset contiene cientos de miles de registros.

## Decisión

**OSAP nunca buscará leyendo MusicXML.** Toda búsqueda se realiza
exclusivamente sobre **metadatos indexados**. Los archivos pesados solo se
cargan cuando una representación ha sido **seleccionada** por el Ranking Engine.

```
Dataset ──► Hugging Face Datasets ──► DatasetAdapter ──► DatasetQueryService
              (metadatos indexados)                        │
                                                            ▼
                                             CandidateRepresentation (metadatos)
                                                            │
                                              (se carga el archivo solo aquí)
                                                            ▼
                                                   RankingEngine ──► ResolutionEngine
```

### Consecuencias

- El `DatasetQueryService` consulta metadatos y nunca recorre manualmente
  millones de registros.
- El `DatasetAdapter` traduce un `DatasetQuery` (del dominio) al mecanismo de
  filtrado del motor. El dominio nunca conoce lambdas ni la API de `datasets`.
- No se duplican índices: mientras Hugging Face Datasets ofrezca filtrado
  eficiente (Arrow, filtros paralelos, streaming), no se crean índices SQLite
  propios. Se aplica: *"no optimizar antes de medir"*.
- El `CandidateRepresentation` transporta toda la metainformación disponible
  (título, subtítulo, movimiento, arreglista, idioma, géneros, licencia, dominio
  público, instrumentación, número de partes, voces, tonalidad, compás, tempo,
  duración, rango, polifonía, calidad, hash, fuente, parser_version) para que el
  Ranking Engine decida sin abrir el archivo.
