# ADR-0007 – Motor de decisión, no ejecución secuencial

## Estado

Aceptado.

### Decisión

El Score Acquisition Pipeline utiliza un motor de decisión (`CapabilityAnalyzer` + `Selector`) en lugar de ejecutar proveedores en orden de preferencia.

### Motivación

Permite incorporar nuevos proveedores sin modificar el pipeline. El sistema decide qué proveedores ejecutar en función de las capacidades del documento, no de una lista hardcodeada.

### Consecuencias

- Se añaden proveedores registrándolos en el sistema, no modificando el pipeline.
- El `CapabilityAnalyzer` determina qué proveedores son compatibles con cada `MusicalDocument`.
- El `ScoreSelector` escoge el mejor resultado entre múltiples `AcquisitionResults`.
