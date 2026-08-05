# ADR-0013 – Subsistema de datasets como proveedor de primer nivel

## Estado

Aceptado.

## Contexto

Hasta ahora los datasets (p. ej. PDMX) se trataban como "recursos" cuya
ausencia generaba un error de aprobación dentro del flujo de resolución. Eso
mezclaba dos responsabilidades: la instalación (bajo demanda del usuario) y la
resolución (búsqueda musical). Además, PDMX estaba "hardcodeado" como un
proveedor.

## Decisión

Se introduce un **subsistema de datasets** completo e independiente:

- **`DatasetRegistry`**: registro declarativo de datasets (nombre, descripción,
  tamaño esperado, licencia, formatos, url oficial, estado, versiones).
  **Nunca se hardcodea PDMX**: PDMX es solo un `DatasetDescriptor` registrado.
- **`DatasetInstaller`**: descarga real vía Hugging Face Datasets con progreso,
  reanudación, verificación de hash, comprobación de espacio, cancelación,
  borrado y actualización. Nunca descarga automáticamente: solo bajo petición
  explícita del usuario.
- **`DatasetManager`**: fachada con `install/update/remove/list/status/verify/repair/location/info`.

### Resolución sin penalización

Cuando el resolver llega a un proveedor respaldado por un dataset **no
instalado**, no se produce un error ni una penalización:

```
pdmx   skipped   Dataset not installed
```

El sistema continúa con el resto de proveedores. La ausencia de un dataset es
como un disco duro externo que todavía no está conectado.

### Consulta eficiente

Toda consulta usa `Dataset.filter()/select()/map()/iter()` del motor. **Nunca**
`for item in dataset` para buscar obras.

## Consecuencias

- El dominio conoce `DatasetDescriptor`/`DatasetStatus` (declarativos), pero
  **nunca** Hugging Face.
- La librería `datasets` queda confinada a `infrastructure` (`HuggingFaceDatasetInstaller`).
- La resolución trata los datasets ausentes como *skipped*, no como error.
- `DatasetSettings` (cache_dir, streaming, num_proc, offline, download_mode,
  max_disk_usage) es configurable; nunca valores hardcodeados.
