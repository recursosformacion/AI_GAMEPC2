# PDMX — Descarga individual de archivos (investigación)

## Conclusión

**No existe una URL oficial por archivo en la distribución de PDMX.**

PDMX distribuye los archivos exclusivamente en **tarballs**, y las rutas de
`PDMX.csv` apuntan a archivos dentro de esos tarballs. No hay un mirror oficial
que sirva cada `.mxl`/`.pdf`/`.mid` de forma individual por HTTP.

## Distribución oficial verificada

Registro **Zenodo 10.5281/zenodo.15571083** (referencia oficial del paper
arXiv 2409.10831):

| Archivo         | Tamaño   | Contenido                          |
|-----------------|----------|------------------------------------|
| `PDMX.csv`      | 225 MB   | Catálogo de metadatos (todas las obras) |
| `data.tar.gz`   | 2.2 GB   | `MusicRender` (JSON) por obra      |
| `mxl.tar.gz`    | 1.9 GB   | MusicXML comprimido por obra       |
| `pdf.tar.gz`    | 9.6 GB   | Partituras PDF                     |
| `mid.tar.gz`    | 214 MB   | MIDI                               |
| `metadata.tar.gz` | 159 MB | Metadata JSON por obra             |
| `subset_paths.tar.gz` | 29 MB | Listas de subsets (no_license_conflict, all_valid...) |

Las rutas de `PDMX.csv` (p. ej. `./mxl/1/11/Qmbb...mxl`) son **relativas al
directorio extraído** de los tarballs. Un `.mxl` individual solo es accesible
después de descargar y extraer `mxl.tar.gz` (1.9 GB).

## Otras fuentes comprobadas

| Fuente                | Estado                                             |
|-----------------------|----------------------------------------------------|
| HuggingFace `openmusic/pdmx` | Solo `PDMX.tar.gz` (1.5 GB, tarball de datos); no Arrow/WebDataset ni archivos individuales |
| GitHub `pnlong/PDMX`  | Repo de código/scripts; los datos se descargan de Zenodo |
| Scripts oficiales     | Usan rutas relativas al directorio PDMX extraído; no descargan archivos sueltos |
| Mirrors públicos      | No hay mirror oficial por archivo                 |

## Implicación para OSAP

- **Búsqueda**: correcta — sobre el índice local de `PDMX.csv` (rápida, sin tarballs).
- **Descarga individual**: **no disponible en la distribución oficial**. Para
  descargar un `.mxl` sin los 1.9 GB completos hace falta un **espejo propio**
  (`download_base`) que haya extraído los tarballs una vez y sirva la estructura
  `/mxl/0/0/0/...` por HTTP.

El proveedor lo comunica explícitamente:

```
Descarga individual no disponible en la distribución oficial.
Configure download_base apuntando a un espejo que sirva la estructura /mxl/0/0/0/...
```
