# WorkMatcher — Diseño (V2.1.2)

> **Status: frozen (V2.1.2)** — contrato congelado e implementado.
>
> Parte del Search Intelligence (V2.1). Define **qué significa** que dos
> `WorkDescriptor` representen la misma obra y **cómo** se puntúa, con un
> `MatchResult` estructurado y explicable.

> **El WorkMatcher compara conceptos canónicos, no cadenas.** No compara texto, no
> compara palabras: compara **identidad**.

## 1. Posición en el pipeline

```
texto → Tokenizer → Lexicon → Canonicalizer → WorkMatcher → WorkGroup → Ranking → Evidence
```

```
texto
  ↓
concepto
  ↓
identidad
  ↓
comparación
```

El WorkMatcher recibe **objetos ya canonicalizados** (`WorkDescriptor`). Nunca
normaliza texto, nunca consulta proveedores, nunca agrupa: **solo compara** dos
identidades.

**El WorkMatcher nunca modifica un `WorkDescriptor`.** Solo devuelve una **evaluación
de similitud** (`MatchResult`). Los `WorkDescriptor` de entrada son inmutables e
inalterados.

## 2. Contrato

```python
class IWorkMatcher(ABC):
    def match(self, first: WorkDescriptor, second: WorkDescriptor) -> MatchResult: ...
```

El contrato responde a **"¿cómo comparo?"**, no a **"¿qué pesos uso?"**. La
configuración (`MatchingConfig`) **no forma parte del contrato**: es política y se
inyecta al construir el componente, igual que un `RankingEngine`.

```python
matcher = DefaultWorkMatcher(config)  # o WorkMatcher(config)
result = matcher.match(first, second)
```

Componente **puro, determinista, explicable y sin IA**: la misma entrada produce
siempre el mismo `MatchResult`, independiente de cómo se configure.

## 3. Tipos del contrato

### `MatchField` — campo comparado (enumerado, no `str`)

```python
class MatchField(Enum):
    CATALOGUE = "catalogue"
    OPUS = "opus"
    COMPOSER = "composer"
    TITLE = "title"
    KEY = "key"
    MOVEMENT = "movement"
    CREATION_YEAR = "creation_year"
    GENRES = "genres"
    INSTRUMENTATION = "instrumentation"
    WORK_AUTHORITY = "work_authority"
    PERSON_AUTHORITY = "person_authority"
```

Evita errores (`catalogue`/`catalog`/`catalog_number`/`Catalog`/`CATALOGUE`) y hace
todo el sistema **tipado**.

### `Authority` y `AuthorityIdentifier` — identificadores de autoridad

```python
class Authority(Enum):
    WIKIDATA = "wikidata"
    MUSICBRAINZ_WORK = "musicbrainz_work"
    IMSLP = "imslp"
    OMR = "omr"
    OPENSCORE = "openscore"
    RISM = "rism"
    ISWC = "iswc"
    VIAF = "viaf"
    ISNI = "isni"
    LOC = "loc"
    BNF = "bnf"
    UNKNOWN = "unknown"
    CUSTOM = "custom"
```

```python
@dataclass(frozen=True)
class AuthorityIdentifier:
    authority: Authority  # tipado: evita errores de escritura
    value: str
```

```python
AuthorityIdentifier(authority=Authority.WIKIDATA, value="Q12345")
AuthorityIdentifier(authority=Authority.IMSLP, value="123456")
```

`UNKNOWN`/`CUSTOM` dejan el enum abierto a autoridades futuras sin romper el contrato.

### `MatchLevel` — tres estados

```python
class MatchLevel(Enum):
    SAME = "same"          # misma obra → mismo WorkGroup
    POSSIBLE = "possible"  # no claramente igual ni distinta → revisión / Knowledge Mining
    DIFFERENT = "different"  # obras distintas
```

### `FieldComparison` — estado de comparación por campo

```python
class FieldComparison(Enum):
    SKIPPED = "skipped"  # campo no comparado (ausente en un lado); no se penaliza
```

En vez de devolver `None`, cada campo devuelve `FieldComparison.SKIPPED` de forma
explícita.

### `MatchReason` — razón tipada por campo

```python
@dataclass(frozen=True)
class MatchReason:
    field: MatchField
    field_score: float    # puntuación continua del campo (0..1)
    left: str | None = None
    right: str | None = None
```

`field_score` es **continuo** (no booleano). Ejemplos: catálogo/compositor exactos
`1.0`, título exacto `1.0`, título parcial `0.6`, título distinto `0.0`.

### `MatchResult`

```python
@dataclass(frozen=True)
class MatchResult:
    level: MatchLevel                 # SAME / POSSIBLE / DIFFERENT
    match_score: float                # puntuación agregada (0..1)
    compared_fields: tuple[MatchField, ...]   # qué se comparó de verdad
    matched_fields: tuple[MatchField, ...]    # campos con field_score == 1.0
    mismatched_fields: tuple[MatchField, ...] # campos comparados con field_score < 1.0
    reasons: tuple[MatchReason, ...]          # razones tipadas por campo
```

`SAME` → mismo `WorkGroup`. `POSSIBLE` → candidato para **revisión humana / Knowledge
Mining**. `DIFFERENT` → obras distintas.

`matched` se elimina del contrato: es derivable (`field_score == 1.0`).

`compared_fields` es relevante para el Knowledge Mining: permite detectar
"esta coincidencia solo se hizo por catálogo" o "nunca estamos comparando tonalidad".

## 4. Campos que participan (y cuáles no)

| Campo (`WorkDescriptor`) | Participa | Familia |
|--------------------------|-----------|---------|
| `catalogue_number` | Sí | Identidad (fuerte) |
| `opus` | Sí | Identidad (fuerte) |
| `composer` | Sí | Identidad (fuerte) |
| `title` | Sí | Identidad |
| `canonical_title` | Sí | Identidad (clave interna) |
| `key` | Sí | Soporte (transposición no rompe) |
| `movement` / `movement_number` | Sí | Subnivel |
| `creation_year` | Sí | Soporte |
| `genres` | Sí | Descriptivo |
| `instrumentation` / `voices` | Sí | Descriptivo |
| `work_authority_identifiers` | Sí | **Coincidencia segura** |
| `person_authority_identifiers` | Sí (compositor) | Ayudan al compositor |
| `aliases` | Sí | Refuerzo |
| `subtitle` | Parcial | Soporte |
| `work_id` | **No** | No es identidad musical |
| `arranger` / `lyricist` | **No** | No definen la obra |
| `language` | No decide | Un título puede estar en varios idiomas |
| `metadata` | **No** | No es identidad |

Principio: la identidad la dan **catálogo, compositor y título**; el resto son señales
de soporte. `work_id` y `metadata` nunca participan.

### Identificadores de autoridad: personas ≠ obras

- **`person_authority_identifiers`** (VIAF, ISNI, LOC, BNF...) identifican **personas**:
  ayudan al **compositor**, no a la obra.
- **`work_authority_identifiers`** (Wikidata `Q…`, MusicBrainz Work, IMSLP Work ID,
  OpenScore ID, OMR ID, RISM, ISWC...) identifican la **obra**. Si dos identidades
  comparten un `work_authority_identifier`, es **coincidencia segura** → `SAME`.

Todos son `AuthorityIdentifier(authority, value)`: extensibles sin cambiar el contrato.

## 5. Puntuación por campo y reglas (en `MatchingConfig`)

El contrato define **qué** campos se pueden comparar; **no** define los pesos ni las
reglas. Esos son **política** y viven en un `MatchingConfig` (igual que `RankingConfig`),
**inyectado al construir** el matcher. El matcher **itera `config.weights`**: un campo se
puede desactivar sin tocar código (quitándolo de `weights` o con peso 0).

```python
@dataclass(frozen=True)
class MatchingConfig:
    same_threshold: float = 0.70
    possible_threshold: float = 0.40
    weights: dict[MatchField, float] = field(default_factory=lambda: {
        MatchField.CATALOGUE: 0.35,
        MatchField.OPUS: 0.20,
        MatchField.COMPOSER: 0.30,
        MatchField.TITLE: 0.25,
        MatchField.KEY: 0.05,
        MatchField.MOVEMENT: 0.05,
        MatchField.CREATION_YEAR: 0.05,
        MatchField.GENRES: 0.03,
        MatchField.INSTRUMENTATION: 0.03,
        MatchField.WORK_AUTHORITY: 1.0,
        MatchField.PERSON_AUTHORITY: 0.10,
    })
    # Campos que fuerzan DIFFERENT si están presentes en ambos y difieren.
    vetoes: tuple[MatchField, ...] = (MatchField.CATALOGUE,)
    # Campos que fuerzan SAME si están presentes en ambos y coinciden (coincidencia segura).
    safe_match_fields: tuple[MatchField, ...] = (MatchField.WORK_AUTHORITY,)
```

`match_score = Σ (weights[field] × field_score[field])`, normalizado al rango de pesos
**presentes** (no se penaliza por campos ausentes).

```
match_score
    ↓
MatchLevel
```

Reglas (política, no código):
- **Veto**: si un campo en `vetoes` está presente en ambos lados y difiere → `DIFFERENT`
  (ej. catálogo contradictorio `KV 618` vs `KV 620`).
- **Coincidencia segura**: si un campo en `safe_match_fields` está presente en ambos y
  coincide → `SAME` (ej. un `work_authority_identifier` compartido). No se quema en
  código: añadir una regla nueva (catálogo compartido, ISWC compartido) es solo añadirla
  a `safe_match_fields`.

Si no aplican reglas, `level` se obtiene del `match_score` por umbrales configurables:
`>= same_threshold` → `SAME`; `>= possible_threshold` → `POSSIBLE`; si no → `DIFFERENT`.

`field_score` por campo es continuo: catálogo/compositor exactos `1.0`, título exacto
`1.0`, título parcial `0.6`, título distinto `0.0`, solapamiento de géneros/instrumentos
`1.0`/`0.0`.

`reasons` acumula un `MatchReason` por campo comparado (tipado, no texto), con
`field_score`; los campos ausentes devuelven `FieldComparison.SKIPPED` y no generan
razón.

### Evolución futura (diseñada, no implementada)

- **`FieldComparator`** — cada `MatchField` delegará en un comparador propio (evitará
  que `_field_value`/`_field_score` crezcan a cientos de `if`).
- **`MatchExplanationRenderer`** — transformará `MatchReason` (tipado) en texto, JSON,
  HTML o `Evidence`, sin atar el dominio al lenguaje natural.

## 6. Casos especiales

1. **Obra sin catálogo**: el campo se **ignora** (peso 0), no penaliza. Mucha música
   (obras sin número) se decide por compositor + título.
2. **Títulos ambiguos**: un título genérico (p. ej. "Sonata") solo no basta; hace
   falta compositor y/o catálogo para superar el umbral.
3. **Distintos idiomas**: el Canonicalizer ya resuelve los conceptos (Symphony/Sinfonía
   → `sinfonia`). El WorkMatcher compara **conceptos canónicos**, no cadenas.
4. **Alias ya resueltos**: `Ave Verum` vs `Ave Verum Corpus` — si el Canonicalizer los
   llevó al mismo `canonical_title`/alias, `SAME`; si no, título parcial → probablemente
   `POSSIBLE` (candidato para revisión / Knowledge Mining).
5. **Transposición**: misma obra en distinta tonalidad → `key` difiere pero no rompe
   (peso bajo); compositor+catálogo deciden.
6. **Identificador de obra**: si ambos comparten un `work_authority_identifier`
   (Wikidata `Q…`, MusicBrainz Work, IMSLP Work ID...), es **coincidencia segura** →
   `SAME`.
7. **Movimiento vs obra completa**: se compara a nivel de obra; el movimiento es un
   subnivel (sube/baja ligeramente el `match_score`).

## 7. Invariantes del WorkMatcher

Función **pura**:

- **Simétrico**: `match(A, B) == match(B, A)`.
- **Determinista**: misma entrada → mismo `MatchResult`.
- **No modifica** ninguno de los `WorkDescriptor` de entrada.
- **No depende del proveedor**.
- **No realiza I/O**: no consulta red ni accede al sistema de ficheros.
- **No usa estado interno mutable**.
- **Sin IA**: sin modelos, embeddings ni búsqueda semántica.

Si en dos años se reemplaza el algoritmo por otro (más rápido, basado en índices, o
asistido por IA), mientras siga devolviendo el mismo `MatchResult` y respetando estas
invariantes, el resto de OSAP no tiene por qué enterarse.

## 8. Qué NO hace el WorkMatcher

- **Nunca modifica un `WorkDescriptor`** — solo devuelve una evaluación de similitud.
- No normaliza texto (eso es el Lexicon + Canonicalizer).
- No consulta proveedores ni orquesta (eso es el Orchestrator).
- No agrupa ni fusiona (eso es el Aggregator / WorkGroup).
- No usa IA, embeddings ni modelos.
- No modifica el núcleo congelado de V2.0.

## 9. Criterios de aceptación (V2.1.2)

- Documento congelado antes de implementar.
- `match()` puro y determinista, devuelve `MatchResult` tipado (`MatchLevel`,
  `MatchField`, `MatchReason`, `AuthorityIdentifier`).
- `compared_fields` refleja exactamente qué se comparó.
- Coincidencia segura por catálogo/compositor o `work_authority_identifier`; sin falsos
  positivos por títulos genéricos solos.
- `POSSIBLE` para casos ambiguos (revisión / Knowledge Mining).
- Los pesos viven en `MatchingConfig`, no en el contrato.
- `match_score` → `MatchLevel`; `reasons` tipados, renderizables a texto/JSON/HTML.
- Tests: mismo catálogo, mismo compositor+título, obra sin catálogo, títulos
  ambiguos → `POSSIBLE`, transposición, alias resueltos por Canonicalizer,
  identificador de obra → `SAME`, no-misma-obra → `DIFFERENT`, y **simetría**
  (`match(A,B) == match(B,A)`).
