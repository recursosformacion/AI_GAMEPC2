# OSAP — Responsabilidades de los componentes

## Dominio

| Objeto                    | Responsabilidad                                                  |
|---------------------------|------------------------------------------------------------------|
| `WorkDescriptor`          | Identidad pura de una obra (título, compositor, movimiento, géneros, instrumentación esperada); **sin formatos ni archivos** |
| `CandidateRepresentation` | Forma concreta de una obra (formato, proveedor, calidad, licencia, confianza, ruta local, origen, tamaño, checksum) |
| `ResolveRequest`          | Petición rica e inmutable (texto, título, compositor, voces, formato, min_quality, online/offline, proveedores permitidos/excluidos) |
| `ResolveResult`           | Resultado: obra, elegida, ranking completo, proveedores usados, tiempo, diagnósticos, descargas, ruta local |
| `Resource`                | Cualquier recurso externo (dataset, catálogo, modelo, caché, knowledge base, diccionario) con estado/versión/licencia |
| `CatalogCapabilities`     | Qué puede hacer un catálogo (búsqueda, descarga, streaming, offline, formatos, dominio público, auth) |
| `CatalogInfo` / `CatalogStatus` | Descripción/estado de un catálogo                    |
| Value Objects             | IDs, `Confidence`, `Duration`, `WorkIdentifier`, `ResourceId`, etc. |

## Puertos

| Puerto                   | Responsabilidad                                          |
|--------------------------|----------------------------------------------------------|
| `ICatalogProvider`       | Responde preguntas musicales (search/resolve/download/metadata/capabilities) y declara qué recursos necesita |
| `IResourceProvider`      | Gestiona la instalación de un recurso (install/update/remove/exists/status/metadata) |
| `IRankingEngine`         | Ordena candidatos por criterios configurables            |
| `IWorkResolver`          | Normaliza la identidad de una obra y detecta equivalencias |
| `IScoreValidator`, `IScoreExporter`, `ILibraryProvider`, `IKnowledgeBase` | Validar, exportar, almacenar, aprender |

## Aplicación

| Componente               | Responsabilidad                                          |
|--------------------------|----------------------------------------------------------|
| `WorkResolutionEngine`   | Fachada: ResolveRequest → recursos → catálogos → ranking → selección → ResolveResult |
| `CatalogManager`         | Registra proveedores de catálogo; listar, capacidades, info; nunca conoce HF/GitHub |
| `ResourceManager`        | Decide/instala/actualiza recursos automáticamente; solo pide aprobación cuando es estrictamente necesario |
| `WorkResolver`           | Construye y normaliza `WorkDescriptor`                   |
| `DefaultRankingEngine`   | Ordena por formato, licencia, calidad, confianza, proveedor, idioma, disponibilidad local |
| `ExportManager` / `LibraryManager` | Despacho de formatos y bibliotecas            |

## Infraestructura

| Adaptador                    | Puerto              | Nota                                   |
|------------------------------|---------------------|----------------------------------------|
| `catalogs/imslp`             | `ICatalogProvider`  | Proveedor real (online)                |
| `catalogs/huggingface` (en `hf/`) | `ICatalogProvider` | Única capa con `datasets` (lazy)   |
| `catalogs/{openscore,cpdl,local,filesystem}` | `ICatalogProvider` | Esqueletos        |
| `resources/hf`               | `IResourceProvider` | Gestiona datasets HF (PDMX, OpenScore) |
| `rankings/DefaultRankingEngine` | `IRankingEngine`  | Criterios ponderados configurables     |
| `export/*`, `library/local`, `validation`, `http` | —  | Adaptadores de soporte     |

## Bootstrap

| Componente     | Responsabilidad                                          |
|----------------|----------------------------------------------------------|
| `Configuration`| Parámetros (incl. umbral de descarga automática, conectividad, rutas) |
| `Container`    | Registro de catálogos, recursos, ranking, validadores, bibliotecas |
| `wiring`       | Composición: IMSLP, OpenScore, HuggingFace (PDMX), Local; recursos HF; umbral de aprobación |

## Reglas de dependencia

- El dominio nunca importa de infraestructura ni conoce librerías externas.
- `datasets` solo aparece en `infrastructure.hf`.
- `CatalogProvider` nunca instala recursos; `ResourceProvider` nunca responde preguntas musicales.
- La aplicación depende solo de puertos y de otros servicios de aplicación.
- Objetos de dominio inmutables; DI en todo el sistema.
