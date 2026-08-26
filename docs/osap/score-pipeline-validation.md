# Score Acquisition Pipeline — validación y trazabilidad

Incremento sobre `docs/osap/musicxml-validation.md`: el validador MusicXML
(`BasicValidator`) se conecta al **Score Acquisition Pipeline** como un stage,
produciendo `Score` + `QualityReport` + `PipelineLog` con trazabilidad.

## Flujo

```
MusicalDocument → adquisición/representación MusicXML → BasicValidator →
Score + QualityReport → PipelineLog
```

## Componentes

- `src/osap/infrastructure/pipeline/score_validation_stage.py`
  - `ScoreValidationStage(IPipelineStage)` — lee del `PipelineContext.data`:
    - `musical_request` (clave `KEY_REQUEST`): `MusicalRequest` (opcional),
    - `musical_document` (clave `KEY_DOCUMENT`): `MusicalDocument` (opcional),
    - `acquisition_result` (clave `KEY_ACQUISITION`): `AcquisitionResult`
      obligatorio, con el contenido MusicXML/.mxl en `source.content`.
  - Ejecuta `BasicValidator` (validación MusicXML por niveles, real, sin simular
    MuseScore).
  - Escribe en el contexto:
    - `score` (`KEY_SCORE`): `Score` con contenido, `QualityReport` y
      `QualityLevel` exactos del validador,
    - `quality_report` (`KEY_QUALITY_REPORT`): `QualityReport`,
    - `pipeline_log` (`KEY_PIPELINE_LOG`): `PipelineLog`,
    - `validation_diagnostic` (`KEY_VALIDATION`): `ValidationDiagnostic`.
- `src/osap/infrastructure/pipeline/pipeline_engine.py`
  - `PipelineEngine(IPipelineEngine)` — motor mínimo: registra stages
    (`add_stage`) y los ejecuta en orden (`run`). Acepta un `IEventBus`
    opcional (compatible con `wiring.py`) y publica `pipeline.stage.<name>`.

## Fallo controlado

Si el MusicXML no es utilizable (XML mal formado, estructura incorrecta, sin
notas, contenido inválido), el stage lanza `ScoreValidationError` de forma
controlada. La excepción **transporta el `ValidationDiagnostic`**
(`exc.diagnostic`) con:

- `score`, `report`, `log` (si se llegó a validar),
- `errors`, `warnings`,
- `failed=True`.

Así el pipeline falla pero se conserva todo el diagnóstico para auditoría.

## Trazabilidad en el PipelineLog

Cada ejecución del stage registra un `PipelineStep` con:

- `step_name`: `"score_validation"`,
- `provider_id`: el del `AcquisitionResult`,
- `result`: dict con `document` (document_id, document_type), `errors`,
  `warnings` y `quality_level`,
- `success`, `duration`, `timestamp`.

El `PipelineLog` lleva `request_id`, `final_quality_level`, `output_format` y
`created_at`. Así se responde: qué documento, qué fuente, qué resultado, qué
errores/warnings, qué nivel de calidad y cuándo.

## Tests

`tests/osap/test_score_validation_pipeline.py`:

- `.mxl` válido pequeño → `Score` con `valid=True`, `QualityLevel.BASIC_MELODY`.
- `.mxl` válido grande → 7 parts / 441 measures, warning "múltiples voces".
- `PipelineLog` completo (request_id, step, document, quality_level).
- XML mal formado → `ScoreValidationError` controlado + diagnóstico conservado.
- Estructura incorrecta (`<foo/>`) → fallo controlado.
- Sin notas → fallo controlado con diagnóstico.
- Contenido inválido (part-list vacío) → fallo controlado con diagnóstico.
- **Prueba clave**: el `Score` producido por el stage conserva exactamente el
  `QualityReport`, `QualityLevel`, errores, warnings y campos estructurales
  que devuelve `BasicValidator` (no se aplanan ni se pierde el diagnóstico).

## No toca

`works`, `work_matcher`, identidad de compositores, búsqueda, producción y los
generadores de Chorus se dejan intactos (próximo salto: primer `ScoreProvider`
real aprovechando los MusicXML de OMR).

## Verificación

```powershell
python -m pytest tests/osap/test_score_validation_pipeline.py -q
python -m ruff check src/osap/infrastructure/pipeline/
python -m mypy src/osap/
```
