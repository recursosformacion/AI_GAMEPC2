# Validación MusicXML — alcance y limitaciones

## Qué detecta el validador (`MusicXmlValidator` / `BasicValidator`)

El validador analiza la representación MusicXML por niveles y produce un
`Score` con `QualityReport` (STRUCTURE, NOTATION, VOICES, LYRICS) y `QualityLevel`.

### Nivel 0 — XML inválido
- XML mal formado (parser rechaza).
- Encoding no reconocido.
- Documento vacío.
- Root incorrecto (no `score-partwise`).

### Nivel 1 — estructura MusicXML
- Presencia de `part-list` / `score-part` / `part` / `measure`.
- `part-list` vacío.
- Part sin `id` o con `id` no declarado en `part-list`.
- Ausencia de `measure`.

### Nivel 2 — contenido musical mínimamente utilizable
- Ausencia de notas.
- Solo silencios (sin pitch).
- Ausencia de `divisions` (duraciones ambiguas) — warning.
- `divisions=0` (división por cero al procesar) — warning.
- `duration` no numérica — warning.
- Múltiples voces / staves — warning informativo.
- Presencia de `time` (firma de compás) — contribuye a NOTATION.

### Nivel 3 — calidad
- `QualityReport` con dimensiones independientes:
  - `STRUCTURE` (part-list/parts/measures coherentes),
  - `NOTATION` (notas, divisions, time),
  - `VOICES` (monofonía vs polifonía),
  - `LYRICS` (presencia de texto).
- `QualityLevel` derivado (UNREADABLE → HUMAN_VALIDATED).

## Qué NO detecta (limitaciones explícitas)

El validador **no reproduce MuseScore** ni un compilador MusicXML completo.
Quedan fuera:

- Reglas de armonía / contrapunto / notación musical avanzada.
- Validación contra el DTD/XSD completo de MusicXML.
- Errores de redondeo de duraciones en relación al compás (sumas por measure).
- Equis / alteraciones inconsistentes con la armadura.
- Lyrics incoherentes con el número de notas.
- Problemas que solo MuseScore (u otro motor de renderizado) detecta al abrir
  la partitura (por ejemplo, conflictos internos que MusicXML permite pero el
  renderizador rechaza o degrada).

Si se necesita detectar esos casos, el mecanismo correcto es un adaptador a un
motor externo (p. ej. un ejecutable/CLI de MuseScore) **detrás de un puerto**,
nunca simulando su comportamiento.

## Fixtures reales usados

Se copiaron dos `.mxl` reales del corpus OMR (`osap-storage/devdata/mxl`) a
`tests/fixtures/musicxml/`:

- `real_short.mxl` — 1 part, 14 measures, 100 notas, monofónico.
- `real_large.mxl` — 7 parts, 441 measures, 2,420 notas, 2 voces (warning "múltiples voces").

Ambos son MusicXML 3.1 `score-partwise` generados por el pipeline OMR y se
usan como casos "reales válidos" en los tests.

## CLI

```
python -m src.osap.cli.main validate <fichero.musicxml|.mxl>
```

Salida:

```text
valid: true/false
quality_level: <0..4>
report:
  structure: 0.00-1.00
  notation: 0.00-1.00
  voices: 0.00-1.00
  lyrics: 0.00-1.00
errors: [...]
warnings: [...]
parts/measures/notes/voices/lyrics
```

## Correspondencia con QualityLevel

| Estado | QualityLevel |
|---|---|
| XML inválido / root incorrecto / estructura rota | `UNREADABLE` (0) |
| Estructura mínima + fallos musicales graves | `PARTIAL_STRUCTURE` (1) |
| Notas presentes, con warnings | `BASIC_MELODY` (2) |
| Válido y consistente | `FULL_NOTATION` (3) |
| (humano validado) | `HUMAN_VALIDATED` (4) |
