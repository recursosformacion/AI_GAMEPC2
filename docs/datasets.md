# OSAP — Subsistema de Datasets

Los datasets (PDMX, OpenScore local, futuros) son **recursos gestionados
automáticamente** por OSAP. El usuario nunca los instala: OSAP decide cuándo
descargar, streamear o usar la caché de Hugging Face.

## Componentes

| Componente          | Responsabilidad                                                    |
|---------------------|--------------------------------------------------------------------|
| `DatasetRegistry`   | Registro declarativo de datasets (nombre, descripción, tamaño esperado, licencia, formatos, url, estado, versiones). Nunca hardcodea PDMX. |
| `DatasetInstaller`  | Descarga real vía Hugging Face (progreso, reanudar, verificar hash, espacio, cancelar, borrar, actualizar). Solo bajo petición explícita. |
| `DatasetManager`    | `install/update/remove/list/status/verify/repair/location/info`.    |
| `DatasetSettings`   | `cache_dir, streaming, num_proc, offline, download_mode, max_disk_usage`. |
| `DatasetVerifier`   | Verifica integridad/hash.                                            |
| `DatasetMetadata`   | Metadatos del dataset (tamaño, licencia, formatos, versiones).       |
| `DatasetHealth`/`Statistics` | Estado y métricas (tamaño, items, integridad).              |

## Flujo

`DatasetDescriptor` → `DatasetInstaller` (Hugging Face, bajo demanda) →
`DatasetRegistry` (estado) → `DatasetManager` (operaciones) → consulta vía
`Dataset.filter()/select()/map()/iter()` (nunca `for item in dataset`).

## CLI

```bash
osap dataset list
osap dataset info pdmx
osap dataset install pdmx      # bajo petición, con progreso
osap dataset verify pdmx
osap dataset repair pdmx
osap dataset location pdmx
osap dataset remove pdmx
```

## En la resolución

Un dataset no instalado se reporta como `SKIPPED / Dataset not installed` (sin
penalizar la puntuación). El sistema continúa con los demás proveedores.
