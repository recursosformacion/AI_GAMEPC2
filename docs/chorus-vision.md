# Visión y Arquitectura de Chorus Study Generator v2

> **Nota de estado (sept 2026):** este documento es la VISIÓN original. La implementación real del
> pipeline de adquisición/validación ha evolucionado. El circuito vigente en osap-api es:
>
> ```
> obra → POST /works/resolve → resolve_session() → AcquisitionService.run_until_terminal()
>   → BestRepresentationSelector.select() → ScoreValidationStage.execute()
>   → BasicValidator → MusicXmlValidator → Score + QualityReport + PipelineLog
>   → selection_json → complete
> ```
>
> `PipelineEngine` fue eliminado por estar huérfano (no participaba en el circuito). `IScoreProvider`,
> `CapabilityAnalyzer`, `ScoreSelector` y `MusicXmlProvider` descritos abajo son componentes
> **previstos en la visión**, no implementados ni necesarios para el circuito actual.
>
> **Documentos de estado actual:** `docs/chorus-product.md` (definición de producto/MVP),
> `docs/chorus-separation.md` (frontera OSAP ≠ Chorus, decisión de monorepo) y
> `docs/chorus-web.md` (propuesta de web independiente y primer vertical slice).

## Objetivo del proyecto

Chorus Study Generator genera materiales de estudio para coros a partir de la mejor representación musical disponible para cada caso de uso. El sistema acepta documentos musicales en cualquier formato (PDF, imágenes, MusicXML, MEI, MIDI, etc.) y produce partituras reducidas, partes individuales, guías vocales y otros recursos pedagógicos listos para ensayo.

## Problemas que resuelve

- El usuario final no dispone habitualmente de MusicXML; suele poseer PDFs escaneados, PDFs vectoriales, imágenes o fotografías.
- La conversión a MusicXML es incierta: depende de OMRs de rendimiento variable, a veces no disponibles, a menudo de pago.
- No existe un sistema que orqueste de forma transparente múltiples fuentes y proveedores para obtener la mejor representación posible.
- Los directores y profesores necesitan materiales de estudio específicos (partes, guías) y no herramientas de edición generalistas.

## Problemas que NO intenta resolver

- Desarrollar un motor OMR propio. Chorus consume resultados de OMR, no los genera.
- Reemplazar editores de partituras profesionales como MuseScore, Sibelius o Dorico.
- Ser una librería de bajo nivel de procesamiento musical. Chorus es una aplicación orientada a materiales de estudio coral.
- Garantizar resultados perfectos en entradas de muy baja calidad. El sistema puede solicitar intervención humana cuando ningún proveedor produce un resultado aceptable.

## Arquitectura de alto nivel

### Dos proyectos independientes

```
┌────────────────────────────────────────────┐
│     Open Score Acquisition Platform        │
│                                            │
│  MusicalDocument                           │
│      ↓                                     │
│  Capability Analyzer                       │
│      ↓                                     │
│  Providers                                 │
│      ↓                                     │
│  Validation                                │
│      ↓                                     │
│  Score                                     │
└────────────────────────────────────────────┘
                │
                ▼
┌────────────────────────────────────────────┐
│        Chorus Study Generator              │
│                                            │
│  Score                                     │
│      ↓                                     │
│  Study Material Generator                  │
│      ↓                                     │
│  Audio / Karaoke / PDF / Exercises         │
└────────────────────────────────────────────┘
```

OSAP es una plataforma abierta, independiente y reutilizable para obtener una representación musical fiable desde cualquier fuente. Chorus es una aplicación especializada que utiliza OSAP para generar materiales de estudio coral.

### Objetos de dominio centrales

El núcleo de OSAP no es MusicXML ni ningún formato intermedio. El núcleo son objetos de dominio inmutables.

```
Documento musical (PDF, imagen, MusicXML, MEI, MIDI, etc.)
        │
        ▼
MusicalDocument
        │
        ▼
Score Acquisition Pipeline
        │
        ▼
MusicalSource (resultado de un proveedor, con confianza y diagnostics)
        │
        ▼
Validation
        │
        ▼
Score (objeto de dominio validado, solo si supera umbral)
```

#### MusicalDocument

Representa exactamente lo que entrega el usuario. Puede ser:

- PDF (escaneado o vectorial)
- Imagen
- MusicXML
- MEI
- MIDI

Nada más. No supone que exista información musical estructurada.

#### MusicalSource

Representa el resultado de intentar interpretar el documento. Por ejemplo:

- MusicXML obtenido por Audiveris, confianza 0.72
- MusicXML corregido por IA, confianza 0.94

Todavía no es un `Score`. Puede contener errores.

#### Score

Representa una obra musical completa, independiente de cómo haya sido obtenida. Solo existe cuando el sistema considera que la representación ya es suficientemente fiable. Todo Chorus trabaja exclusivamente con este objeto.

#### AcquisitionResult

Amplía el concepto de confianza. No es solo un número:

```text
AcquisitionResult
├── source        (MusicalSource)
├── confidence    (numérico)
├── provider      (proveedor que lo generó)
├── processing_time
├── warnings
└── diagnostics
```

Esto permite al sistema decidir mejor qué hacer con cada resultado.

### Motor de decisión

No se ejecutan estrategias en orden de preferencia. Se utiliza un motor de decisión:

```
Documento musical
        │
        ▼
Capability Analyzer
¿Qué proveedores pueden trabajar con esto?
        │
        ▼
Ejecución (en paralelo o secuencial, según estrategia)
        │
        ▼
Resultados (colección de AcquisitionResult)
        │
        ▼
Selector
Escoge el mejor resultado según confianza, costo, tiempo, etc.
        │
        ▼
Validación
        │
        ▼
Score (si supera umbral) o Fallback humano
```

Esto permite incorporar nuevos proveedores sin modificar el pipeline.

### Knowledge Base

Cada conversión alimenta una base de conocimiento:

- Documento de entrada
- Proveedores ejecutados
- Resultados obtenidos y su confianza
- Intervenciones humanas
- Estrategia ganadora

La próxima vez que aparezca un documento similar, OSAP ya sabrá qué estrategia funcionó mejor. Puede empezar siendo una base de reglas y estadísticas, sin necesidad de aprendizaje automático complejo.

### Quality Model

Cada `Score` posee un nivel de calidad objetivo:

- Level 0: Unreadable
- Level 1: Partial structure
- Level 2: Basic melody
- Level 3: Full notation
- Level 4: Human validated

Chorus puede decidir qué materiales generar en función del nivel:

- Nivel 1: solo generar vista previa
- Nivel 2: generar audio
- Nivel 3: generar ejercicios
- Nivel 4: generar todos los materiales

### Proveedores como puertos

Todo acceso a herramientas externas (Audiveris, OMRs, librerías de parseo) se realiza mediante puertos/interfaces. No hay llamadas directas a ejecutables o APIs externas desde el núcleo.

- `IScoreProvider`: interfaz para producir un `MusicalSource` desde un `MusicalDocument`.
- `IScoreValidator`: interfaz para validar la integridad del `Score`.
- `IScoreRepository`: interfaz para persistir/cachear `Scores` y `MusicalSources` intermedios.
- `ICapabilityAnalyzer`: interfaz para determinar qué proveedores son compatibles con un `MusicalDocument`.
- `IScoreSelector`: interfaz para escoger el mejor `MusicalSource` entre múltiples resultados.

Esto permite incorporar nuevos proveedores sin modificar el núcleo: solo se registra una implementación nueva de `IScoreProvider` y se actualiza el `CapabilityAnalyzer`.

### Regla nº1

Ningún proveedor externo podrá ser utilizado directamente desde Chorus.

Siempre:

```
Puerto
    ↓
Adaptador
    ↓
Proveedor
```

Nunca:

```
Chorus
    ↓
Audiveris
```

Dentro de tres años agradecerás esa decisión.

### Trazabilidad

Cada decisión del pipeline se registra en un `PipelineLog`:

- Qué proveedores se intentaron.
- Resultados parciales y su `AcquisitionResult`.
- Motivo de selección o rechazo.
- Intervenciones humanas.

El log es parte del dominio y se expone para depuración y auditoría.

## Principios de diseño

- **SOLID**, **Clean Architecture**, **Hexagonal Architecture**, **DDD**.
- **Dependency Injection** en todo acceso a proveedores y almacenamiento.
- **Composition over Inheritance**: comportamientos mediante estrategias, no mediante jerarquías rígidas.
- **Independencia de formato**: el núcleo no conoce PDF, MusicXML ni ningún formato externo.
- **Chorus nunca procesa formatos. Procesa únicamente objetos de dominio.**

## Principio fundamental del proyecto

Chorus nunca debe asumir que existe una representación musical perfecta. El sistema trabaja siempre con representaciones de distinta calidad, procedentes de múltiples fuentes. Su responsabilidad no es producir un MusicXML perfecto, sino obtener la mejor representación posible de la obra, conocer el grado de confianza asociado a ella y generar materiales de estudio acordes con esa calidad.

Todo el diseño debe favorecer la incorporación de nuevos métodos de adquisición (OMR, IA, servicios externos o intervención humana) sin modificar el núcleo de Chorus.

## Separación de responsabilidades

Chorus Study Generator es el producto que usa el director de coro. Open Score Acquisition Platform es una plataforma reutilizable para cualquier aplicación que necesite obtener una representación musical fiable a partir de documentos heterogéneos. MusicScoreInspector queda como la herramienta de ingeniería para diagnosticar y validar los procesos de adquisición.

Es una separación muy limpia de responsabilidades y mucho más sostenible a largo plazo.

## Hoja de ruta

### Fase 1: Modelo de dominio

- `MusicalDocument`
- `MusicalSource`
- `Score`
- `AcquisitionResult`
- `PipelineLog`
- `QualityLevel`
- `KnowledgeBaseEntry`

### Fase 2: Score Acquisition Engine

- `CapabilityAnalyzer`
- `ScoreSelector`
- Motor de pipeline

### Fase 3: Proveedores

- `MusicXmlProvider`
- `HumanProvider`
- `AudiverisProvider`
- `IAProvider`

### Fase 4: Validación

- `IScoreValidator`
- Implementaciones de validación

### Fase 5: Chorus Processing Pipeline

- Modelo de materiales de estudio
- Motor de procesamiento

### Fase 6: Generación de materiales

- Partituras reducidas
- Partes individuales
- Guías vocales

## Conclusión

Si hace una semana me hubieras preguntado cuál era el proyecto, habría dicho:

"Un generador de materiales para coros."

Hoy ya no.

Hoy hay dos proyectos:

1. Open Score Acquisition Platform: una plataforma abierta, independiente y reutilizable para obtener una representación musical fiable desde cualquier fuente.
2. Chorus Study Generator: una aplicación especializada que utiliza OSAP para generar materiales de estudio coral.

La única recomendación antes de escribir una línea más de código: no cambiar más la arquitectura. Ya está suficientemente madura. A partir de ahora, dedicar el esfuerzo a implementar iteraciones pequeñas y verificables, manteniendo este documento como la referencia de diseño. Cada nueva funcionalidad debería poder justificarse diciendo en qué apartado de esta visión encaja. Si no encaja, probablemente pertenece a otro proyecto o requiere revisar la arquitectura antes de implementarla. Eso ayudará a que Chorus no vuelva a desviarse de su objetivo principal.
