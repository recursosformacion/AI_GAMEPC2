# Modelo canónico de formaciones vocales (`ensembles`) y su uso en `representations`

Estado: propuesta de referencia (una sola fuente de verdad). Sustituye las dos
canonicalizaciones históricas (`osap-storage/_externo/audit_ensembles.py` y
`osap_normalize/`) por **una función de dominio** reutilizable por el importador, el
auditor de `ensembles` y la barra de búsqueda.

## 1. Problema

Hoy `ensembles.ensembles_code` mezcla:

- formaciones vocales reales (`SATB`, `SSAATTBB`, `TTBAR`, `SATB.SATB`),
- descriptores de ejecución (`SOLO`, `DIVISI`, `A CAPPELLA`),
- coros especiales (`CHILDREN`, `TREBLE`, `UNISON`),
- ruido no vocal (`C-A'`, `F4`, `BC`, `&NDASH 5`),
- y variantes de formato del mismo conjunto (`SA T B` == `SATB`).

Sin una identificación unívoca no se puede (a) deduplicar el catálogo, (b) reconstruir la
formación a partir de un `representation`, ni (c) interpretar lo que pide el usuario.

## 2. Función canónica (contrato)

```
canonical_ensemble(text: str) -> CanonicalEnsemble
```

- **Entrada**: cualquier cadena (`ensembles_name`, `ensembles_code`, texto del buscador).
- **Salida** (`CanonicalEnsemble`, `frozen dataclass`):

| campo | tipo | significado |
|---|---|---|
| `id_canonico` | `str` | Identificador unívoco de la formación (§3). |
| `segments` | `tuple[str, ...]` | Un id por bloque independiente (multi-coro). |
| `voice_counts` | `Mapping[str, int]` | Recuento por voz canónica (S, MZ, A, CT, T, BAR, B). |
| `total_voices` | `int` | Suma de voces (0 si no vocal). |
| `family` | `str` | Familia/orientación (MIXED/FEMALE/MALE/UNISON/...). |
| `kind` | `str` | `VOICES` \| `SPECIAL` \| `INVALID` \| `UNKNOWN`. |
| `description` | `str` | Texto humano reconstruible (p. ej. «Coro mixto a 4 voces: S A T B»). |
| `notes` | `tuple[str, ...]` | Traza de reglas aplicadas (auditable). |

- **Determinismo**: mismo texto → mismo id. **Idempotencia**: `canonical_ensemble(id)` devuelve
  el mismo `id_canonico`.

## 3. Especificación de `id_canonico`

**Alfabeto y orden canónico de voces** (de agudo a grave):

```
S (soprano), MZ (mezzo), A (alto), CT (contratenor/contralto), T (tenor), BAR (barítono), B (bajo)
```

Se conserva la distinción MZ vs A y BAR vs B de `osap_normalize` (relevante para repertorio);
un id se forma con **una aparición por voz efectiva**:

```
S2A2T2B2  ->  "SSAATTBB"
TTBARB    ->  "TTBARB"
```

**Gramática**:

```
id      := segment ("|" segment)*        # multi-coro/secciones (| separa bloques)
segment := voices | special | "INVALID_OR_INSTRUMENTAL" | "UNKNOWN" | "UNSPECIFIED"
voices  := letters-with-counts  |  voice "_SOLO_" voice   # coro con solista
special := "UNISON" ["_FEMALE"|"_MALE"|"_MIXED"] | "CHILDREN" | "TREBLE"
         | "DESCANT" | "INSTRUMENTAL_" sfx | ROLE
```

El separador de bloques es `|` (no `_`) para que el id sea **idempotente**: `_` ya se usa en
el infijo `_SOLO_` y en ids especiales (`UNISON_FEMALE`).

- Un modificador de ejecución (`SOLO`, `SOLI`, `DIVISI`, `A CAPPELLA`, `RIPIENI`…) **no** crea
  voz; solo `_SOLO_` cuando hay una voz de solista identificable.
- **Letra suelta = voz solo con evidencia contextual** (otra voz en el bloque, un calificador
  tipo SOLO/VERSE/DIVISI, un conector, o que el resto del texto sea funcional). Sin evidencia
  no se interpreta: `A GLÄUBIGE SEELE`, `T EVANGELISTA` o `B JESUS` no son formaciones.
- Si no hay voz identificable:
  - `INVALID_OR_INSTRUMENTAL` — notación instrumental/no vocal.
  - `UNKNOWN` — **material vocal no interpretable** (p. ej. BAR/BARB pegados: `TBARBARB`,
    `ATBARBARB`). No se inventa una segmentación «válida».
  - `UNSPECIFIED` — el texto **no da** formación concreta (`MIXED`, `DIV`, `VOICE`, `PARTSONG`…);
    categoría distinta de `UNKNOWN`.
  Nunca se descarta por «ser letras»: una cadena de voces válida siempre se reconoce.
- La descripción (§2) se deriva del id de forma determinista, para no depender de textos libres.

## 4. Qué debe representar una fila de `ensembles`

- **Una fila = una formación canónica**, identificada por `ensembles_code = id_canonico`
  (único, ya existe `uq_ensembles_code`).
- `ensembles_name`: etiqueta humana estable («Coro mixto a 4 voces»).
- `ensembles_description`: descripción reconstruida por la función («Soprano, Alto, Tenor, Bajo»).
- `ensemble_voices`: descomposición (voz + cantidad) — **la fuente de reconstrucción**.
- Los códigos crudos que colapsan en el mismo id se conservan como **alias**
  (nueva tabla `ensembles_aliases(raw_code UNIQUE → ensembles_id)`), para no perder trazabilidad
  y para resolver búsquedas por el texto original.
- Invariante: para toda fila, `canonical_ensemble(ensembles_code).id_canonico == ensembles_code`.

Así, «entender `ensembles`» = (1) canonicalizar cada fila, (2) agrupar por id, (3) fusionar los
alias en su fila canónica y registrar los que difieran.

## 5. Qué debe guardar una `representation`

`representations` describe una forma concreta de una obra (edición/arreglo). Debe poder
**reconstruirse la formación** sin releer texto libre, así que almacena el id canónico:

- `representations.ensemble_code VARCHAR(64) NULL` — `id_canonico` (o `NULL` si no vocal).
  Indexado (`idx_representations_ensemble_code`).
- Opcional (denormalización para el índice/búsqueda): `voice_signature VARCHAR(64) NULL` con
  la firma de frecuencias (p. ej. `S2A2T2B2`), derivable de `voice_counts`.
- **Origen del valor**: en el import, el campo de formación de cada proveedor (CPDL `voicing`,
  PDMX, etc.) pasa por `canonical_ensemble(...)`; nunca se guarda el texto crudo como id.
- Reconstrucción completa de una `representation`: `ensemble_code` (id) → fila `ensembles` →
  `ensemble_voices` (voces + cantidades) → descripción/nombre. Si `ensemble_code` es un id
  especial (`UNISON`, `CHILDREN`, `INVALID_OR_INSTRUMENTAL`…), la fila `ensembles`
  correspondiente describe el caso.

## 6. Uso inmediato

1. **Entender `ensembles`** (auditoría read-only): aplicar la función a las 1374 filas,
   agrupar por `id_canonico`, listar alias, colisiones y `INVALID/UNKNOWN` para revisión;
   produce el CSV `id_canonico,ensemble_id,ensembles_code,name,kind,family,notas`.
2. **Barra de búsqueda**: `canonical_ensemble(query)` extrae la formación pedida; si da una
   firma, filtra por `ensemble_code`/`voice_signature` y se combina con la intención de
   compositor/obra ya existente.

## 7. Decisiones abiertas

- **Profundidad del alfabeto**: se adopta S/MZ/A/CT/T/BAR/B (la de `osap_normalize`). Alternativa
  colapsada (S/A/T/B/C) de `_externo` si se quiere un id más corto; perdería MZ≠A y BAR≠B.
- **Alias**: tabla `ensembles_aliases` vs reutilizar `ensembles_name`/descripción.
- **Denormalización** de `voice_signature` en `representations` (rendimiento) vs calcular al vuelo.
