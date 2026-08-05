# ADR-0009 – OSAP resuelve obras musicales, no solo convierte documentos

## Estado

Aceptado.

## Contexto

La visión original de OSAP modelaba la plataforma como un conversor de
documentos (p. ej. PDF a MusicXML). Esto obligaba a que toda petición partiera
de un documento y acoplaba el núcleo a formatos concretos.

En la práctica el usuario no siempre dispone de una partitura: puede tener solo
el título y el compositor, una fotografía, un MIDI, una URL o un identificador.

## Decisión

OSAP ya no es una plataforma de conversión de documentos. Es una plataforma que
**resuelve una obra musical**, obteniendo la mejor representación disponible a
partir de cualquier tipo de entrada.

- Todo parte de un nuevo objeto de dominio inmutable: `MusicalRequest`.
- El pipeline pasa a ser un **motor de resolución** (`ScoreResolutionEngine`)
  en lugar de una secuencia de conversión.
- Se introducen **dos familias de proveedores**: `lookup` (localizan una
  representación existente) y `acquisition` (construyen una representación).
- El `StrategyPlanner` decide qué estrategias ejecutar (`SEARCH`, `CONVERT`,
  `ASK`, `COMBINE`), nunca las ejecuta.
- La salida se exporta al formato pedido (`IScoreExporter`) y se almacena en la
  biblioteca elegida (`ILibraryProvider`).

## Consecuencias

- El dominio solo conoce `MusicalRequest`, `Score`, `AcquisitionResult`,
  `QualityLevel` y `PipelineLog`. Nunca conoce PDF, MusicXML, Audiveris, PDMX,
  IMSLP ni MuseScore.
- Añadir un buscador, un OMR, IA, OCR, reconocimiento por audio o una biblioteca
  nueva no exige modificar el núcleo: solo registrar un nuevo adaptador que
  implemente un puerto (principio Open/Closed).
- El `SourcePreferencePolicy` permite expresar criterios de selección
  (dominio público, formatos preferidos, offline, repositorios permitidos, etc.)
  sin tocar el motor.
- La `KnowledgeBase` registra cada resolución para mejorar decisiones futuras.

---

## ADR-0010 – Dos familias de proveedores: lookup y acquisition

### Decisión

Se distinguen formalmente dos tipos de proveedores:

- **`IScoreLookupProvider`**: busca y descarga representaciones ya existentes
  (`search`, `download`, `capabilities`). No genera partituras.
- **`IScoreAcquisitionProvider`**: construye una representación musical a partir
  de la petición (`acquire`, `capabilities`).

### Motivación

Separar "encontrar lo que ya existe" de "construir lo que no existe" mantiene el
núcleo estable y permite que `StrategyPlanner` componga estrategias de ambas
familias (por ejemplo, buscar en IMSLP y, si no se encuentra, OMR sobre un PDF).

### Consecuencias

- El `CapabilityAnalyzer` evalúa la viabilidad de ambas familias por separado.
- Un proveedor concreto pertenece a una sola familia y solo implementa su puerto.
- El `ScoreResolutionEngine` despacha a la familia correspondiente según la
  estrategia planificada.

---

## ADR-0011 – Strategy Planner como componente de planificación

### Decisión

`IStrategyPlanner` decide únicamente la secuencia de estrategias
(`SEARCH`, `CONVERT`, `ASK`, `COMBINE`) y el proveedor objetivo de cada una.
Nunca ejecuta el trabajo.

### Motivación

Cumplir SOLID (responsabilidad única) y permitir evolucionar el criterio de
decisión sin acoplar el motor a una lista fija de proveedores.

### Consecuencias

- `StrategyPlanner` consume un `CapabilityAnalysis` producido por
  `ICapabilityAnalyzer`.
- La `SourcePreferencePolicy` condiciona la planificación sin entrar en el motor.
- El motor solo interpreta la lista de estrategias resultante.

---

## ADR-0012 – Exportación y almacenamiento mediante fachadas

### Decisión

El `Score` se exporta mediante `ExportManager`, que despacha a adaptadores
`IScoreExporter` (MusicXML, MEI, MIDI, PDF, JSON, Score). El resultado se
almacena mediante `LibraryManager`, que despacha a adaptadores `ILibraryProvider`
(local, git, NAS, cloud, dataset).

### Motivación

El usuario puede pedir el resultado en un formato y guardarlo en una biblioteca
concreta sin que el motor conozca los detalles de cada formato o repositorio.

### Consecuencias

- Añadir un formato de exportación o una biblioteca nueva solo exige registrar un
  adaptador.
- El `Score` es la representación canónica interna; todas las conversiones de
  formato ocurren en la capa de infraestructura.
