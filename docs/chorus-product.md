# Chorus — Definición de producto

> Documento vivo del producto Chorus. Complementa `docs/chorus-vision.md` (visión) y
> `docs/chorus-separation.md` (frontera arquitectónica OSAP ≠ Chorus). Aquí se fija qué
> es Chorus, a quién sirve, qué hace hoy y qué hará (y qué no hará).

## 1. Núcleo del producto

**Chorus es la aplicación con la que se trabaja la música: se estudia, se analiza, se
practica y se generan materiales de estudio (partituras reducidas, partes, guías
vocales, ejercicios, audio).**

OSAP resuelve el problema de *encontrar y adquirir* una representación musical fiable.
Chorus resuelve el problema *posterior*: convertir esa obra en algo que un coro o un
estudiante puede usar para trabajar.

```text
OSAP   → descubrir, buscar, localizar fuentes, resolver/adquirir, catálogo
Chorus → abrir una obra, comprenderla, analizarla, generar material, estudiarla/practicarla
```

Chorus **no** adquiere ni resuelve obras: recibe un `Score` (contrato OSAP) y produce
materiales a partir de él. Chorus **no** implementa OMR ni procesa formatos de bajo
nivel (ADR-0000, ADR-0002, ADR-0004): trabaja con objetos de dominio.

## 2. Usuarios

Perfiles justificados por el propósito del producto (material de estudio coral):

- **Cantante / miembro de coro**: necesita su parte o una guía vocal para estudiar en casa.
- **Director/a de coro**: prepara el ensayo; necesita partitura reducida, partes por cuerda,
  análisis y ejercicios para el grupo.
- **Profesor/a de música (vocal)**: genera materiales para clase a partir de una obra.

Sin evidencia adicional, no se asume hoy como objetivo prioritario a instrumentistas
solistas, compositores o investigadores: sus necesidades pueden cubrirse en fases
posteriores si el producto lo justifica.

## 3. Casos de uso principales

Flujo de trabajo natural (confirmado contra el circuito actual `Score → StudyMaterial`):

```text
recibir/abrir una obra (Score)
        ↓
comprenderla (resumen estructural real, no inventado)
        ↓
analizarla (forma, textura, voces, texto)         [siguientes fases]
        ↓
generar material (reducida / parte / guía / ejercicio)  [hoy: ejercicio]
        ↓
estudiarla/practicarla (entregar el material)     [web futura]
```

El circuito actualmente demostrado cubre el tramo: `Score` → `ExerciseGenerator` →
`StudyMaterial` (contenido estructural real del Score, sin inventar información musical).

## 4. Catálogo de funcionalidades

### MVP (producto pequeño pero real)
- Recibir un `Score` de OSAP (contrato; hoy en-proceso, mañana vía contrato estable).
- Generar un material de tipo `EXERCISE` (resumen estructural: título, compositor, partes,
  compases, notas, voces, letra, `QualityLevel`, `QualityReport`).
- Entregar el `StudyMaterial` generado por el caso de uso `GenerateMaterialsUseCase`.
- CLI/web mínima que muestre el material generado.
- Conocer la calidad del `Score` para no generar materiales sobre basura
  (`QualityLevel.UNREADABLE` no produce materiales útiles).

### Próximas fases
- `REDUCED_SCORE` (partitura reducida) y `INDIVIDUAL_PART` (parte por voz) como materiales.
- `VOCAL_GUIDE` (guía vocal con apoyo rítmico/melódico).
- Interfaz web independiente que reciba la obra, muestre el material y permita generarlo.

### Futuro
- `PDFGenerator` / `PDFExporter` (exportación a PDF real del material).
- `AudioGenerator` (audio de apoyo/estudio por voz).
- `KARAOKE` (seguimiento vocal sincronizado).
- Persistencia propia de materiales/sesiones.

### Fuera de alcance (hoy)
- OMR, adquisición, resolución o búsqueda de obras (responsabilidad de OSAP).
- Procesar formatos musicales internamente (MusicXML/MEI) en el dominio de Chorus.
- Consumir proveedores externos directamente (ADR-0008).
- Pagos, cuentas, membresía (decisión documentada en la familia `docs/osap/support-*`).
- Consumir la API de `resolve` de OSAP o cualquier servicio externo de OSAP.

## 5. Relación con el estado real

Lo que está **funcional hoy** (incremento cerrado):

```text
MXL real → BasicValidator/MusicXmlValidator (OSAP) → Score → ExerciseGenerator
         → StudyMaterial (MaterialType.EXERCISE) → CLI `osap chorus-generate` (demo)
```

- `StudyMaterial`, `MaterialType`, `IStudyMaterialGenerator`, `ExerciseGenerator`,
  `GenerateMaterialsUseCase`, `Container` y `wire` de Chorus: funcionales y probados.
- `PDFGenerator`, `AudioGenerator`, `PDFExporter`: **no** cableados (funcionalidad futura).
- No existe integración HTTP OSAP → Chorus; el `Score` se entrega en-proceso.

Ver `docs/chorus-separation.md` para el detalle de frontera y dependencias reales.
