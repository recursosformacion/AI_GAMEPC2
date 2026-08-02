# OSAP — Quality Model

OSAP no usa un único valor numérico de confianza. Cada representación se evalúa
en **dimensiones independientes** (`QualityReport`), y de ahí se deriva un
`QualityLevel` global.

## Dimensiones

| Dimensión     | Evalúa                                    |
|---------------|-------------------------------------------|
| STRUCTURE     | Estructura formal (compases, secciones)    |
| NOTATION      | Corrección y completitud de la notación    |
| LYRICS        | Texto / letra presente y alineado          |
| HARMONY       | Armonía y acordes                          |
| VOICES        | Voces/partes presentes                     |
| METADATA      | Metadatos (título, compositor, ...)        |
| ATTACHMENTS   | Adjuntos (PDF, audio, imágenes)            |

Cada dimensión puntúa en **[0, 1]**.

## QualityLevel derivado

A partir de la media del informe:

| Media       | Nivel                 |
|-------------|-----------------------|
| ≥ 0.90      | HUMAN_VALIDATED       |
| ≥ 0.70      | FULL_NOTATION         |
| ≥ 0.50      | BASIC_MELODY          |
| ≥ 0.25      | PARTIAL_STRUCTURE     |
| < 0.25      | UNREADABLE            |

Este modelo lo usará **Chorus** para decidir qué materiales puede generar a
partir de un Score (p. ej. solo un `FULL_NOTATION` admite armonización completa).
