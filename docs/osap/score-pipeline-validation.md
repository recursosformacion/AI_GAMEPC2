# Score Acquisition Pipeline — validación y trazabilidad

Incremento sobre `docs/osap/musicxml-validation.md`: el validador MusicXML
(`BasicValidator`) se conecta al circuito de adquisición real, produciendo
`Score` + `QualityReport` + `PipelineLog` con trazabilidad.

> **Estado (sept 2026):** `PipelineEngine`/`IPipelineEngine` fueron **eliminados** por
> estar huérfanos (no participaban en el circuito real). La coordinación la hace
> `resolve_session()` + `AcquisitionService` + `BestRepresentationSelector`, que
> invoca `ScoreValidationStage` directamente.

## Flujo real

```
obra → POST /works/resolve → resolve_session()
  → AcquisitionService.run_until_terminal()
  → BestRepresentationSelector.select()
  → ScoreValidationStage.execute() → BasicValidator → MusicXmlValidator
  → Score + QualityReport + PipelineLog → selection_json → complete
```

## Componentes

- `src/osap/infrastructure/pipeline/score_validation_stage.py`
  - `ScoreValidationStage` — ejecuta `BasicValidator` sobre un
    `AcquisitionResult` (contenido MusicXML/.mxl en `source.content`) y produce
    el `Score` + `QualityReport` + `PipelineLog` exactos del validador.
  - Es invocado por `BestRepresentationSelector` (selección de la mejor
    representación) dentro de `resolve_session`.
- `src/osap/application/representation_selector.py`
  - `BestRepresentationSelector` — selecciona la mejor representación entre las
    adquiridas (descargable → MusicXML → mayor QualityLevel → mejor
    QualityReport → menos errores → desempate por provider) y conserva las
    alternativas como evidencia.

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
