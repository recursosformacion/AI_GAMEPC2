# Normalización explicable (V2.1.1)

> **Status: draft** (parte del diseño de V2.1 — `docs/osap/v2/search-engine-design.md`).
>
> Complemento del Search Intelligence. Define **cómo** normaliza OSAP y exige que
> cada transformación sea **justificable, auditable y reproducible**, igual que el
> Evidence Engine justifica cada elección. Sin "caja negra".

## Principio estratégico

> El conocimiento musical de OSAP reside en **reglas declarativas versionadas e
> independientes de cualquier proveedor**. Cada nueva regla mejora **simultáneamente**
> todos los proveedores presentes y futuros sin modificar el núcleo de resolución.

## Separación de responsabilidades (ADR-0021)

No se mezclan clasificación y canonicalización, y dentro de la normalización se
distinguen **dos familias** de reglas:

- **Lexicon** → clasifica (`token → categoría`). Se mantiene exactamente como está.
- **Canonicalizer** → **alias → forma canónica** (misma "escritura" del concepto).
- **Translator / ConceptNormalizer** → **idioma → concepto** (palabras en idiomas
  distintos que representan el mismo concepto).
- **WorkMatcher** → compara **solo representaciones ya normalizadas**.
- **Knowledge Mining / Discovery** → observa el funcionamiento de OSAP y **genera
  propuestas** de conocimiento. Nunca modifica nada; solo escribe candidatos.

```
Tokenizer
   │
   ▼
Lexicon ── sinAsignar.yaml
   │
   ▼
Canonicalizer
   ├── composer_aliases.yaml
   ├── catalogue_aliases.yaml
   ├── language_aliases.yaml
   ├── work_aliases.yaml
   └── alias_candidates.yaml   ← generado por Knowledge Mining
   │
   ▼
WorkMatcher
```

## Tres repositorios de conocimiento

| Repositorio | Responsabilidad | Equivalente a |
|-------------|-----------------|---------------|
| **Lexicon** | Clasificación: ¿qué es este término? | `sinAsignar.yaml` |
| **Canonical Rules** | Normalización: ¿cuál es la forma canónica / el concepto? | reglas `*_aliases.yaml` |
| **Knowledge Mining** | Propuestas de conocimiento nuevo | `alias_candidates.yaml`, `unknown_*.yaml` |

No es "ampliar el Lexicon": son **tres** bases de conocimiento con responsabilidades
diferentes. Y falta la pieza que responde **de dónde** sale la verdad (ver abajo).

## Knowledge Sources — de dónde sale la verdad

Sabemos **cómo** aprender (Knowledge Mining), pero falta **de dónde**. Las fuentes
no se mezclan:

### 1. Observación del propio OSAP (empírica)

Ya existe: `sinAsignar.yaml`, `alias_candidates.yaml`, `unknown_catalogues.yaml`,
`unknown_languages.yaml`... Nace **solo de la experiencia de uso**. Tras cientos de
búsquedas, Knowledge Mining propone "creo que todo esto es lo mismo"; **nunca
modifica nada**, solo propone.

### 2. Fuentes oficiales

Aquí está la verdadera potencia. Generan **propuestas**, no reglas:

| Fuente | Aporta |
|--------|--------|
| **VIAF** | autoridades de nombres (`Mozart` / `Wolfgang Amadeus Mozart` / `W.A. Mozart`) |
| **Wikidata** | alias, idiomas, catálogos, obras + **IDs estables** |
| **IMSLP** | muchísimos alias usados por músicos |
| **MusicBrainz** | muy bueno para autores |
| **Library of Congress** | autoridades bibliográficas |
| **RISM** | música antigua |

### 3. Curación manual

Hay decisiones **editoriales** que nunca aparecerán automáticamente. Ej.:
`Nr.` / `No.` / `Number` / `Nº` / `Num.` → alguien debe decidir → `numbering.yaml`.

### Flujo: origen → propuesta → aprobación

```
Usuario / Aggregator
        │
        ▼
Knowledge Mining
        │
        ▼
knowledge/proposals/*.yaml
        │
        ▼
Revisión humana
        │
        ▼
Canonical Rules (*.yaml) ──► Canonicalizer ──► Search Engine
```

Cada regla tiene un **origen**, una **propuesta** y una **aprobación** antes de ser
conocimiento canónico.

### El Aggregator también es fuente

No todo sale del Search Engine: también del **Aggregator**. Si en las últimas 5.000
búsquedas `Ave Verum Corpus` y `Ave Verum` siempre terminan en el mismo
`WorkDescriptor`, Knowledge Mining propone:

```yaml
id: work.ave-verum-corpus
canonical: "Ave Verum Corpus"
aliases:
  - "Ave Verum"
```

Esto es **más fiable** que aprender solo de lo que escriben los usuarios, porque se
basa en la **resolución efectiva** del sistema.

## Dos familias de reglas

### 1. Alias → canonicalización (`Canonicalizer`)

Son **alias** de la misma escritura del concepto:

```yaml
# catalogue_aliases.yaml
id: catalogue.kv
canonical: "KV"
aliases:
  - K
  - K.
  - KV
  - Köchel
  - Koechel
```

### 2. Idioma → concepto (`Translator / ConceptNormalizer`)

No son alias exactos, sino **palabras en idiomas distintos** del mismo concepto:

```yaml
# concept_forms.yaml
id: concept.form.sinfonia
canonical: "sinfonia"
languages:
  en: symphony
  es: sinfonía
  de: sinfonie
  fr: symphonie
```

Mañana aparecerán italiano, latín, ruso, japonés: un problema distinto al de los
alias, por eso se mantiene separado.

## Identificadores estables

Cada regla tiene un **`id` estable** (no "línea 83 del fichero"):

```yaml
id: catalogue.kv
canonical: "KV"
aliases:
  - K
  - K.
  - Köchel
```

La evidencia referenciará `rule = catalogue.kv`, no una ubicación de fichero.

## Las reglas devuelven evidencia

El `Canonicalizer`/`Translator` devuelve un `NormalizationResult`:

```python
NormalizationResult(
    input="K.618",
    output="KV 618",
    rule_id="catalogue.kv",
    confidence=1.0,
)
```

Así cada búsqueda es **completamente explicable**: se sabe qué entrada, qué salida,
qué regla y con qué confianza.

## Obras (work aliases) y el Tokenizer

Cuidado con las obras compuestas. En:

```
Ave Verum K618
```

hay **dos conceptos**: `título` ("Ave Verum") + `catálogo` ("KV618"). No es un alias.
El **Tokenizer** separa los componentes:

```
Ave Verum K618  →  title: "Ave Verum"   catalogue: "KV618"
```

y después cada componente se canonicaliza **por separado**. Esto hace el sistema mucho
más robusto que tratar `"Ave Verum K618"` como una única cadena.

## Cómo aprende el Canonicalizer (Knowledge Mining)

El Lexicon aprende **palabras** (`token → ¿qué es? → sinAsignar`). El Canonicalizer
aprende **equivalencias** (`¿esto ya lo conozco con otro nombre?`). La pregunta es
distinta y necesita otro "sinAsignar": las **propuestas organizadas**.

No hay un único `alias_candidates.yaml`: hay una **carpeta `knowledge/proposals/`**
con un fichero por familia:

```
knowledge/
  proposals/
    composer_aliases.yaml
    catalogue_aliases.yaml
    language_aliases.yaml
    work_aliases.yaml
    instrumentation_aliases.yaml
    numbering_aliases.yaml
    key_aliases.yaml
    publisher_aliases.yaml
    genre_aliases.yaml
```

Cuando OSAP encuentra una forma sin regla, **la registra y la propone**, nunca la
aplica automáticamente:

```yaml
# knowledge/proposals/catalogue_aliases.yaml  (generado por Knowledge Mining)
- family: catalogue
  seen: "KV-618"
  count: 18
  examples:
    - provider: IMSLP
    - provider: MuseScore
    - provider: OMR
```

Otro ejemplo:

```yaml
- family: composer
  seen: "Wolfg. A. Mozart"
  count: 54
```

Cuando un candidato aparece **muchas veces** (o co-ocurre siempre con otro alias de
la misma obra), es buena señal para crear una regla — pero **la propone**, no la crea.

### Descubrimiento automático (co-ocurrencia)

Si `K618`, `KV618`, `KV 618`, `K.618` acompañan **siempre** a `Ave Verum Corpus` /
`Mozart`, Knowledge Mining puede proponer:

> He observado 250 veces que `K618` aparece donde también aparece `KV618`.
> ¿Quieres crear una regla? → `catalogue.kv`

Lo mismo para compositores (`W. A. Mozart` / `W.A.Mozart` / `Wolfgang Amadeus Mozart`
/ `Mozart`), idiomas (formas que siempre describen las mismas obras) y **obras**: si
el Aggregator ya agrupa `Ave Verum` y `Ave Verum Corpus` en el mismo `WorkGroup`,
propone:

> Posible alias: `Ave Verum` → `Ave Verum Corpus` (634 coincidencias, proveedores:
> OMR, IMSLP, MuseScore). ¿Crear regla?

### Misión

Knowledge Mining **solo observa y propone**. Escribe `knowledge/proposals/*.yaml` y
`unknown_*.yaml`... Es el equivalente de `sinAsignar` para **conocimiento de alto
nivel**: OSAP mejora con datos reales, pero **nunca aprende de forma opaca**. Todo
conocimiento nuevo entra como una **propuesta revisable por un humano**. El humano
decide qué conocimiento pasa a ser oficial.

## Aplicación a V2.1.1 (pequeñas entregas)

| Entrega | Ejemplos | Familia | Regla (id) |
|---------|----------|---------|------------|
| 1. Compositores | `Mozart`, `W. A. Mozart`, `Wolfgang Amadeus Mozart`, `W.A.Mozart` | Alias | `composer.mozart` |
| 2. Catálogos | `KV618`, `K618`, `K.618`, `Köchel 618` | Alias | `catalogue.kv` |
| 3. Obras | `Ave Verum`, `Ave Verum Corpus`, `Ave verum` (Tokenizer separa el catálogo) | Alias | `work.ave-verum` |
| 4. Idiomas | `Symphony`, `Sinfonía`, `Sinfonie`, `Symphonie` | Concepto | `concept.form.sinfonia` |
| 5. Numeración | `No.`, `Nr.`, `Nº`, `Number`, `Num.` | Concepto | `concept.number` |
| 6. Tonalidades | `C major`, `Do Mayor`, `Ut majeur` | Concepto | `concept.key.c-major` |
| 7. Instrumentación | `SATB`, `Choir SATB`, `Mixed Choir`, `Coro mixto` | Concepto | `concept.instrumentation.satb` |

Estas reglas crecerán formando un **Lexicon enorme + Canonical Rules**, ambos
**independientes de cualquier proveedor**.

## Garantías

1. **Determinismo** — misma entrada → misma salida.
2. **Auditabilidad** — cada transformación referencia su `rule_id`.
3. **Reproducibilidad** — las reglas son datos versionados, no lógica ad-hoc.
4. **Reglas explícitas** — nada de modelos, redes ni "caja negra".
5. **Inversión permanente** — independiente de proveedores; mejora todos a la vez.
6. **Automatización trazable** — OSAP mejora con datos reales, pero **nunca aprende
   de forma opaca**: todo conocimiento nuevo entra como **propuesta revisable** por
   un humano (Knowledge Mining), igual que `sinAsignar`.
7. **Origen y aprobación** — cada regla tiene un **origen** (Knowledge Sources:
   observación, fuentes oficiales o curación manual), una **propuesta** y una
   **aprobación** antes de ser parte del conocimiento canónico.

## Qué NO es

- No es búsqueda semántica, embeddings, LLM ni vectores (V3).
- No depende de ningún proveedor.
- No cambia el núcleo congelado de V2.0.
