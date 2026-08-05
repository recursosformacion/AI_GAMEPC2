# OSAP — Pipeline de resolución

El `WorkResolutionEngine` es la fachada que resuelve una petición musical.

## Pipeline

```
   ResolveRequest (texto, título, compositor, voces, formato, online/offline, ...)
        │
        ▼
   WorkResolver ──► WorkDescriptor (identidad normalizada)
        │
        ▼
   ResourceManager  ── ¿existe/instalado/actualizado el recurso del catálogo?
        │            ── ¿descargar? ¿streaming? ¿copia local? (transparente)
        │            ── aprobación solo si es enorme / sin red / licencia / conflicto
        │
        ▼
   CatalogManager ──► ICatalogProvider (search)  ──► CandidateRepresentation[]
        │            (IMSLP online; OpenScore/CPDL/PDMX/Local offline)
        │
        ▼
   RankingEngine  ── ordena por formato, licencia, dominio público, calidad,
        │            confianza, proveedor, idioma, disponibilidad local, preferencias
        │
        ▼
   Selección  ──► CandidateRepresentation elegida
        │
        ▼
   (opcional) Download ──► AcquisitionResult ──► guardar en biblioteca
        │
        ▼
   ResolveResult (obra, elegida, ranking completo, proveedores usados,
                  tiempo, diagnóstico de por qué se eligió y qué faltó)
```

## Etapas y responsabilidades

| Etapa             | Servicio / Puerto          | Decisión / acción                                         |
|-------------------|----------------------------|-----------------------------------------------------------|
| Identidad         | `IWorkResolver`            | Normaliza/fusiona la identidad de la obra                 |
| Recursos          | `ResourceManager`          | Asegura los recursos de cada catálogo (instala si falta)  |
| Catálogos         | `ICatalogProvider`         | Responde búsquedas musicales sobre su fuente              |
| Ranking           | `IRankingEngine`           | Ordena candidatos por criterios configurables             |
| Selección         | `WorkResolutionEngine`     | Elige el mejor candidato                                  |
| Descarga          | `ICatalogProvider.download`| Obtiene la representación elegida (opcional)              |
| Resultado         | `ResolveResult`            | Explica la elección y la trazabilidad                     |

## ResourceManager: instalación bajo demanda

```
resolve()
  │
  ▼
¿Recurso del catálogo instalado? ──NO──► ¿Es necesario? ──NO──► skip (diagnóstico)
  │ SÍ                                         │SÍ
  ▼                                            ▼
  usar                                        ¿Puede descargarse?
                                              │
                                     ┌────────┴─────────┐
                                     │SÍ                │NO (sin red / no impl)
                                     ▼                  ▼
                              descargar auto       aprobación / skip
                              (o INDEX_ONLY)
```

Solo se pregunta al usuario cuando: el tamaño supera un umbral configurable, no
hay conexión, la licencia requiere aceptación o hay conflicto de versiones. En
cualquier otro caso la descarga es transparente.

## Notas

- `CatalogProvider` **nunca** instala recursos: solo responde preguntas musicales.
- `ResourceManager` es responsable exclusivo de la instalación/lifecycle.
- `ResolveResult` incluye diagnósticos de las fuentes no disponibles, de modo
  que el sistema explica por qué eligió (o no pudo elegir) una representación.
