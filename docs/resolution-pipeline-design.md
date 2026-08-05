# Diseño Técnico — Pipeline de Resolución de Obras y Representaciones

> **Estado:** propuesta (a implementar tras aprobación).
> **Objetivo:** rediseñar el modelo de resolución para que la unidad de búsqueda
> sean **obras**, cada obra conserve **todas sus representaciones** con su
> información íntegra, el usuario vea siempre **títulos originales/canónicos**
> (nunca salida del normalizador), y la fusión sea un **matching con puntuación
> explicable**, no una cadena concatenada ni heurísticas de expresiones
> regulares añadidas al normalizador.

---

## 1. Diagnóstico de la salida real

Síntomas observados en `osap resolve` y su causa raíz (arquitectura, no un bug
local):

| Síntoma real | Causa raíz en el diseño actual |
|---|---|
| "Ave Verum Corpus" aparece 4 veces | La clave de fusión es una **cadena concatenada** del título modificado; variantes con/sin catálogo o con mayúsculas distintas no coinciden exactamente. |
| El normalizador genera "[D ies]", "[K omm]", "[D ances]" | El **título mostrado se deriva del normalizador** (`clean_title`/`work_key`), que recorta tokens de catálogo y fragmenta el título. Ese fragmento se expone al usuario. |
| "Se destruyen títulos ('Per Questa Bella Mano ()')" | El normalizador manipula el título original (quita paréntesis, catálogo, ruido) y ese resultado se usa como display. |
| "Se pierde información de catálogo" | El catálogo se extrae y **se elimina** del título durante la limpieza; no se conserva como dato aparte. |
| "El usuario ve títulos derivados del normalizador" | No hay separación entre **comparar** y **mostrar**: `WorkDescriptor.title` es el producto del normalizador. |

**Conclusión:** el pipeline mezcla cuatro responsabilidades en una sola cadena de
funciones (`MetadataNormalizer.clean_title`, `work_key`, `WorkMergeService._canonical`):
importar, extraer, normalizar y mostrar. Hay que **separarlas en fases** con
objetos intermedios inmutables.

---

## 2. Principios de diseño

1. **Inmutabilidad de los datos originales.** Lo que un proveedor devuelve
   (título, compositor, catálogo, URL, licencia…) se importa **verbatim** y nunca
   se modifica.
2. **Separación de fases** con objetos intermedios que no se mezclan:
   `RawWork` → `ExtractedMetadata` → `NormalizedMetadata` → `Work`.
3. **El normalizador solo compara, nunca muestra.** `NormalizedMetadata` existe
   únicamente para el matching; jamás llega a la UI.
4. **El usuario ve títulos originales/canónicos.** El título canónico se elige
   entre los títulos originales disponibles, con una métrica de calidad, nunca
   desde el normalizador.
5. **Fusión por scoring explicable.** Dos representaciones se fusionan si su
   grado de acuerdo (compositor + título + catálogo + número + tonalidad +
   aliases + confianza) supera un umbral; el sistema puede explicar el porqué.
6. **Nada se pierde.** Cada obra conserva todas sus representaciones y todos sus
   campos.

---

## 3. Flujo de fases (pipeline)

```
 Proveedores
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ FASE 1 · Importación (ICatalogProvider.search)              │
│   → CandidateRepresentation                                  │
│   work_descriptor = RAW (verbatim)                          │
│   + provider, format, url, license, confidence, remote_id…  │
│   "título original" NUNCA se toca                            │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ FASE 2 · Extracción (metadata_parser.extract_metadata)       │
│   título original → {catalogue, number, key, opus}          │
│   Solo LEE el título; no lo modifica                         │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ FASE 3 · NormalizedMetadata (SOLO para comparar)             │
│   normalized_title / composer / catalog / number / key      │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ FASE 4 · Matching/Fusión (WorkMatcher)                       │
│   scoring por campo → MergeDecision (score + razón)          │
│   → WorkGroup (work + todas las representaciones)            │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ FASE 5 · Título canónico (TitleSelector)                     │
│   se elige entre los títulos ORIGINALES                       │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ FASE 6 · Enriquecimiento (CanonicalWork)                     │
│   work + representaciones completas para la UI              │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
 CLI (resolve) / API REST (/search, /works, /preview) → obras, nunca reps sueltas
```

---

## 4. Modelo de datos

### 4.1 Representación candidata (Fase 1) — `CandidateRepresentation`
Se mantiene como el **registro crudo** del proveedor. Se añaden/consolidan
campos de primera clase (sin dependencia de `metadata`):

- `work_descriptor` → contiene el título/compositor **originales**.
- `provider`, `format`, `download_url`, `license`, `confidence`, `rating`,
  `remote_id`, `local_path`, `notes`, `downloadable`, `manual_download`.
- Nuevo campo `original: RawWork` que congela título/compositor/catálogo tal y
  como llegaron (para que nunca se pierdan ni se confundan con derivados).

### 4.2 Metadatos extraídos (Fase 2) — `ExtractedMetadata` (ya existe)
- `catalogue`, `catalogue_raw`, `work_number`, `key`, `opus`.
- Nunca modifica el título.

### 4.3 Metadatos normalizados (Fase 3) — `NormalizedMetadata` (NUEVO)
Objeto inmutable de **comparación exclusiva**:

```
@dataclass(frozen=True)
class NormalizedMetadata:
    normalized_title: str       # minúsculas, unicode NFKC, colapsa espacios
    normalized_composer: str
    normalized_catalog: str | None
    normalized_number: str | None
    normalized_key: str | None
```

Se construye a partir del título original + `ExtractedMetadata`. **No se expone
nunca en la UI.** Se usa solo como entrada del `WorkMatcher`.

### 4.4 Obra fusionada (Fases 4-6) — `Work`
Agregado de primer nivel que **siempre** devuelve el pipeline:

```
@dataclass(frozen=True)
class Work:
    work_id: WorkId                # estable
    title: str                     # título CANÓNICO (original elegido en F5)
    composer: str | None
    catalogue: str | None          # mostrado aparte
    number: str | None
    key: str | None
    public_domain: bool | None
    genre: str | None
    ...
    representations: tuple[Representation, ...]   # TODAS, íntegras
```

`Representation` es una vista estable de `CandidateRepresentation` + datos
extraídos/normalizados + info de descarga (manual/URL), para que la UI/API nunca
pierda un campo.

### 4.5 Decisión de fusión (Fase 4) — `MergeDecision` (NUEVO)
Resultado explicable del matcher:

```
@dataclass(frozen=True)
class MergeDecision:
    merged: bool
    score: float                    # 0..1
    reason: tuple[str, ...]         # p.ej. ("catálogo K.618 coincide", "título coincide")
    confidence: float               # confianza agregada de la fusión
```

---

## 5. Clases nuevas

| Clase | Capa | Responsabilidad |
|---|---|---|
| `RawWork` | Dominio | Congela el título/compositor/catálogo originales del proveedor (verbatim). |
| `NormalizedMetadata` | Aplicación | Título/compositor/catálogo/número/clave normalizados, **solo comparación**. |
| `WorkMatcher` | Aplicación | Algoritmo de matching con puntuación entre representaciones. |
| `MergeDecision` | Aplicación | Resultado del matching: `score`, `reason`, `confidence`. |
| `Work` | Dominio | Agregado obra con metadatos canónicos + todas las representaciones. |
| `TitleSelector` | Aplicación | Elige el título canónico entre los títulos **originales**. |
| `NormalizedMetadataBuilder` | Aplicación | Fase 3: `RawWork + ExtractedMetadata → NormalizedMetadata`. |

---

## 6. Clases que desaparecen / se reemplazan

| Actual | Decisión | Motivo |
|---|---|---|
| `MetadataNormalizer.clean_title` | **Desaparece del pipeline** | Hace extracción + limpieza + display mezclados; destruye títulos. |
| `MetadataNormalizer.work_key` | **Desaparece del pipeline** | Clave por cadena concatenada del título modificado. |
| `MetadataNormalizer.catalogue` (regex sobre `No.`) | **Reemplazado** por `metadata_parser.extract_metadata` | Generaba "NO 9" / "[D ies]". |
| `WorkMergeService._canonical` (display derivado) | **Reemplazado** por `WorkMatcher` + `TitleSelector` | El título canónico debe ser un original, no salida del normalizador. |
| `work_merge_service._split` / `_representation_score` (heurísticas aisladas) | **Reemplazadas** por `WorkMatcher` con scoring | Heurísticas por-caso → algoritmo general reutilizable. |
| `metadata_parser.extract_metadata` | **Permanece** (evoluciona) | Ya es extracción pura (Fase 2). |

---

## 7. Clases que permanecen

- `CandidateRepresentation` (como registro crudo, Fase 1).
- `ResolveRequest`, `ResolveRequestBuilder`.
- `ICatalogProvider` y los proveedores (IMSLP, PDMX, OpenScore, Local, HF).
- `WorkResolutionEngine` (orquestación; el download se restringe a la obra elegida).
- `canonical_metadata.MetadataEnricher` (ajustado para leer el título canónico y
  las representaciones íntegras).
- API `dto.py` / `app.py` (se ajusta el shape de salida, no el contrato de rutas).
- CLI `main.py` (se ajusta el renderizado de obras/representaciones).
- `ResolveResult`.

---

## 8. Algoritmo de matching (Fase 4)

El matcher compara dos representaciones (o una representación contra el
prototipo de la obra) y produce un `MergeDecision`. No es una cadena: es una
**suma ponderada de acuerdos por campo**, cada uno con una razón legible.

### 8.1 Comparadores por campo

Cada comparador devuelve `(coincide: bool, peso, razón)`:

| Campo | Comparador | Peso | Razón ejemplo |
|---|---|---|---|
| Compositor | `normalized_composer` igual | **0.35** | "compositor coincide (mozart)" |
| Título (núcleo) | solapamiento de tokens de `normalized_title` | **0.30** | "título coincide (ave verum corpus)" |
| Catálogo | `normalized_catalog` igual | **0.20** (si ambos presentes) | "catálogo K.618 coincide" |
| Número | `normalized_number` igual | **0.15** (si ambos presentes) | "No.16 coincide" |
| Tonalidad | `normalized_key` igual | **0.10** (si ambos presentes) | "clave C major coincide" |
| Aliases | cualquier alias igual | +bonus | "alias coincide" |

Reglas de precedencia:
- El catálogo **es un fuerte discriminador**: si ambas tienen catálogo y difieren
  → penaliza fuerte (no fusionar), p.ej. Sonata 11 vs Sonata 12.
- Si **solo una** tiene catálogo → el catálogo **no divide** (se permite fusionar
  "Ave Verum Corpus" con "Ave Verum Corpus K.618"), pero la que tiene catálogo
  gana peso como representante canónico.
- Núcleo de título (sin catálogo/número/clave) siempre se compara.

### 8.2 Umbral y decisión

```
score = Σ(acuerdos × peso) normalizado a [0,1]
merged = score >= UMBRAL  (U.merge ≈ 0.6; ajustable)
```

La agrupación es incremental:
1. Se ordenan los candidatos por confianza descendente.
2. El de mayor confianza inicializa una obra (prototipo).
3. Cada candidato siguiente se compara contra cada obra; se fusiona con la de
   mayor `score` si supera el umbral; si no, crea obra nueva.

Esto **no depende del título exacto** ni de mayúsculas: depende de acuerdos
ponderados, y es reutilizable para cualquier compositor.

### 8.3 Explicación

Cada `MergeDecision.reason` recoge las razones de los campos que coincidieron:
```
score=0.87, reason=("compositor coincide", "título coincide", "catálogo K.618 coincide")
```
La UI/CLI/API pueden exponer `reason` para que el usuario entienda el merge.

---

## 9. Cálculo de confianza

- **Confianza de representación** (ya existe): la del proveedor (`confidence`,
  `rating`), normalizada a [0,1].
- **Confianza de fusión** (`MergeDecision.confidence`): mezcla
  - el `score` del matching (grado de acuerdo), y
  - la confianza media de las representaciones fusionadas.
- **Confianza de la obra canónica**: la de su representación primaria
  (mejor orden de preferencia) más un bonus si varias representaciones
  coinciden (acuerdo múltiple = más fiable).

---

## 10. Selección del título canónico (Fase 5) — `TitleSelector`

Se elige **entre los títulos originales** de las representaciones de la obra,
con una métrica de calidad (`quality(title)`):

1. Se descartan sufijos de compositor y catálogo incrustados **solo para
   puntuar**, no para mostrarlos: la base a evaluar es el título sin
   "(compositor)", ", KV 618", "- Mozart", etc.
2. Métrica: penaliza fragmentos vacíos, comas sueltas, "()", paréntesis rotos,
   repetición; premia el título más completo pero limpio.
3. Se selecciona el título de mayor `quality` **dentro de la representación de
   mayor confianza**; si hay empate, el de mayor longitud de contenido.

Ejemplo esperado:
```
Entradas originales:
  "Ave Verum Corpus"
  "Ave Verum Corpus -- KV 618"
  "Ave Verum Corpus - Wolfgang Amadeus Mozart"
Canónico → "Ave Verum Corpus"   (catálogo "K.618" se muestra aparte)
```

Nunca se muestra `normalized_title`. El catálogo, número y clave se muestran
como campos separados.

---

## 11. Por qué esto resuelve cada síntoma

| Síntoma | Solución en el nuevo diseño |
|---|---|
| "Ave Verum Corpus" x4 | `WorkMatcher` fusiona por acuerdos ponderados (título+compositor+catálogo), no por cadena exacta → **1 obra**. |
| "[D ies]", "[K omm]", "[D ances]" | `normalized_title` **nunca se muestra**; el display usa títulos originales/canónicos. |
| "Per Questa Bella Mano ()" | Fase 1 importa verbatim; Fase 5 puntúa limpieza pero **no reescribe** el título; se elige un original sano. |
| Catálogo perdido | `ExtractedMetadata.catalogue` se guarda aparte en Fase 2 y se muestra como campo; nunca se borra del raw. |
| Usuario ve salida del normalizador | Separación estricta: `NormalizedMetadata` es comparación-only; `TitleSelector` elige entre originales. |
| Fusión no reutilizable | `WorkMatcher` es un algoritmo general (scoring + umbral), sin heurísticas por obra. |

---

## 12. Contrato de salida (CLI y API idénticos)

**Lista de obras** (nunca representaciones sueltas):

```
Obra
  Ave Verum Corpus
  Catálogo: K.618
  Compositor: Wolfgang Amadeus Mozart
  Representaciones:
    ✓ MusicXML · PDMX
    ⚠ PDF · IMSLP · URL manual: https://imslp.org/wiki/...
```

**API `GET /api/v1/search`** → `items: [Work]` donde cada `Work` incluye
`representations: [Representation]` con todos los campos
(`provider, format, downloadable, manual_download, download_url, license,
confidence, rating, local_path, remote_id, notes, reason`).

**Selección automática** (requisito): el motor elige la mejor representación por
orden de preferencia (Local MusicXML → Local MEI → PDMX MusicXML → OpenScore
MusicXML → MusicXML → PDF → Manual); si la mejor es manual, informa y ofrece la
URL.

---

## 13. Plan de implementación (tras aprobación)

1. **Dominio**: añadir `RawWork` y el agregado `Work`; ajustar
   `CandidateRepresentation`.
2. **Aplicación**: `NormalizedMetadata` + `NormalizedMetadataBuilder` (Fase 3).
3. **Aplicación**: `WorkMatcher` + `MergeDecision` (Fase 4); reemplazar la
   agrupación actual.
4. **Aplicación**: `TitleSelector` (Fase 5).
5. **Aplicación**: integrar en `WorkResolutionEngine` (orquestación de fases,
   descarga restringida a la obra elegida).
6. **Enriquecimiento**: `MetadataEnricher` lee `Work` + representaciones íntegras.
7. **API/CLI**: ajustar shapes de salida y renderizado (obras + reps completas).
8. **Pruebas**: casos de merge (Mozart/Bach/Beethoven/Schubert/Palestrina/
   Victoria), variantes "Ave Verum", preservación de campos, descarga manual,
   paridad CLI/API, y verificación con `osap resolve` real.

---

## 14. Riesgos y casos límite

- **Obras homónimas del mismo compositor** (p.ej. dos "Ave Maria" de Schubert):
  el umbral + discriminador de catálogo/número evita fusión indebida; si no hay
  catálogo, se separan por núcleo de título + tonalidad cuando difieren.
- **Títulos genéricos** ("Piano Sonata No.11" vs "No.12"): el número y el
  catálogo pesan para separarlos; el núcleo "piano sonata" no los fusiona.
- **Solo una representación**: se forma obra de un solo miembro, sin pérdida.
- **Catálogo inconsistente entre fuentes** (KV vs Köchel vs K.): el
  `normalized_catalog` los unifica (Fase 3) para comparar; el original se
  conserva para mostrar.
- **Rendimiento**: el matching es cuadrático sobre candidatos; se limita con
  bucketing inicial por compositor+núcleo (reducción de pares), manteniendo el
  scoring como verificación fina.
