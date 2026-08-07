# ADR-0031 – Descubrimiento e incorporación de fuentes musicales (V3.6.x)

## Estado

Aceptado. Congela el modelo de **incorporación y descubrimiento de fuentes musicales**
(V3.6.x).

## Principios

- **Toda fuente musical puede utilizarse inmediatamente por cualquier usuario**; su
  incorporación permanente depende de que el usuario decida **proponerla** y de la
  **aprobación posterior del administrador**.
- **El administrador no interviene en el uso normal de una fuente**: solo decide si una
  **propuesta** pasa a formar parte de OpenMusicRepository.
- **Connector ≠ Source ≠ Instance**: el conector define cómo acceder; la Source Definition
  define qué colección; la Session/Repository Instance es una **instancia de uso**, no un
  tipo distinto de fuente.
- **Session y Repository Instances usan exactamente el mismo pipeline** de resolución
  (Analyze → Collect → Normalize → Match → Merge → Evidence → Quality).
- El **análisis automático** siempre precede al uso de una fuente desconocida, y se
  **persiste** (analysis, quality, trust, last_analysis, last_sync).
- La API existente **no se modifica**; solo se **amplía**.
- No se modifica el dominio V2 ni la arquitectura V3.3.

## Contexto

V3.6 extiende la administración para permitir incorporar nuevas fuentes musicales. La
decisión clave es que el **uso inmediato** no requiera aprobación: OpenMusicRepository
favorece el descubrimiento libre, y la gobernanza solo afecta a la incorporación
permanente.

## Decisión

- **Modelo**: `Connector → Source Definition → (Session Instance | Repository Instance)`,
  con **Source Profile** (credenciales/rama) para reutilizar la definición.
- **Flujo normal**: crear fuente → analizar → usar inmediatamente (sin admin).
- **Flujo de propuesta** (voluntario e independiente): proponer → admin acepta/rechaza →
  solo así se crea una Repository Instance.
- **API ampliada** (`/api/v1/`), con flujo **separado** `create → analyze → use`:
  - uso: `POST /sources`, `POST /sources/{id}/analyze|use|sync|propose`, `GET
    /sources/{id}`, `DELETE /sources/{id}` (forget);
  - admin (solo propuestas): `/sources/proposals/*`;
  - descubrimiento: `GET /discover/sources`.
- **Análisis persistido** con **Quality Score** desglosado; **Capabilities** por conector;
  **Preview** antes de importar.
- **Origin** (Official/Community/Private/Generated/Mirrored) y **Trust**
  (Official/Verified/Community/Experimental) como ejes independientes.
- **Discover Sources**: usa/descarta/propone; nunca obliga a pasar por un administrador.
- Estado **DISABLED** (una aprobada que dejó de funcionar conserva su historial).

## Consecuencias

- El usuario **nunca espera una aprobación** para aprovechar una nueva fuente.
- El motor **no distingue** entre una fuente instalada y una recién descubierta (mismo
  pipeline), manteniendo el dominio limpio.
- El modelo es **extensible**: un plugin puede añadir conectores sin tocar el modelo.
- Los nuevos recursos de la API son **aditivos**; no se rompe ningún contrato existente.
