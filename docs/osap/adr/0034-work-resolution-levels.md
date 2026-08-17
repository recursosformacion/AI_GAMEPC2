# ADR-0034 – Niveles de resolución de obra: `resolved` y `resolved_auth`

## Estado

Aceptado (definición conceptual).

## Contexto

Para decidir si CISAC es un requisito imprescindible del producto o solo el enriquecimiento
de máxima autoridad, necesitamos definir qué significa **"obra resuelta"** sin ISWC/IPI.
Las fuentes abiertas (Wikidata, MusicBrainz, VIAF/ISNI/LCCN) permiten acumular evidencia e
identificar obras/compositores, pero **ninguna** sustituye el registro ISWC/IPI que CISAC
publica (y que no expone por API pública).

Además se separan tres responsabilidades:

- **osap-api** — dueño de la interfaz externa. Orquesta y expone; **no** accede a BD, **no**
  implementa repositories, **no** decide autoridad. Solicita operaciones a storage.
- **osap-storage** — dueño del estado (`works`, `composers`, `work_person`,
  `authority_identifiers`). Expone ports/repositorios de lectura y escritura.
- **Enrichment** — dueño de la obtención de evidencia (Wikidata, MusicBrainz, VIAF, ISNI,
  CISAC, OMR). Produce snapshots y solicita su materialización; **no** conoce SQL.

Regla: *quien posee el estado, provee la operación de lectura/escritura sobre ese estado.*

## Decisión

Se definen **dos niveles** de resolución de obra, medibles por separado:

### `resolved`

Una obra está `resolved` cuando se dispone de:

- **identidad de obra suficientemente estable**;
- **evidencia persistente y trazable** (≥1 identificador estable materializado en
  `authority_identifiers`: `wikidata_work`, `musicbrainz_work`, o título+catálogo con
  coincidencia en ≥2 proveedores);
- **compositor/persona identificado** (con ≥1 identificador persistente: `isni`, `viaf`,
  `wikidata`, `musicbrainz`, `lccn`), o determinado explícitamente *desconocido* por
  identidad de la **obra** (no por defecto);
- **ausencia de ambigüedad material** entre candidatos.

**No requiere ISWC/IPI.**

### `resolved_auth`

Una obra `resolved` pasa además a `resolved_auth` cuando dispone de un **identificador
autoritativo adecuado**:

- **ISWC** para la obra;
- **IPI** para los titulares/autores, cuando corresponda.

```
candidate → identidad estable → resolved → ISWC/IPI disponibles → resolved_auth
```

CISAC queda así en su sitio: **no bloquea el desarrollo**, pero tampoco se rebajan sus
identificadores.

### Regla de correspondencia ISWC ↔ identidad

Que exista un ISWC **no implica automáticamente** `resolved_auth`. Se requiere además una
**correspondencia fiable** entre el ISWC y nuestra identidad de obra. El identificador es
**evidencia de autoridad**, no una varita mágica que resuelve un mal matching.

### Atribución: OSAP nunca infiere Anonymous/Traditional

`Anonymous`, `Anon`, `Traditional`, `Trad` **no son estados que OSAP pueda inferir**: son
**atribuciones proporcionadas por una fuente**. Por tanto:

- `composer = None` → **UNKNOWN** (compositor desconocido/no proporcionado). **Nunca**
  `Anonymous` ni `Traditional`.
- Si un proveedor dice explícitamente `composer = "Anonymous"` → `anonymous`.
- Si un proveedor dice explícitamente `composer = "Traditional"` → `traditional`.
- Un valor de atribución (persona o `Anonymous`/`Traditional`) es evidencia igual que
  `Mozart`, `Arne`, `Carey`, `Attwood`…; la diferencia es que el valor identifica la
  **naturaleza** de la atribución, no una persona.

La canonicalización `anon/anonymous/trad/traditional → anonymous` sirve **exclusivamente**
para **comparar atribuciones explícitas de proveedores**; **no autoriza al motor a generar**
una de ellas desde la ausencia de compositor. Se conserva el valor original del proveedor
(no se pierde `Traditional` vs `Anonymous`).

**Impacto en `resolved`:** una obra con `composer=None` **no** queda `resolved` por parecer
tradicional. Y **`composer_explicit` ≠ `resolved`**: que un proveedor proporcione
`composer="J.S. Skinner"` es **evidencia de atribución de fuente**, no prueba por sí mismo
que la identidad de la obra esté resuelta.

Separación de niveles (lo que `resolution_confidence` debe aprender):
- **Evidencia de proveedor** (dato): `OMR dice title=..., composer=...`.
- **Decisión de OSAP** (decisión): ¿tengo evidencia suficiente para afirmar que esta
  identidad de obra está resuelta?

Reglas:
- `composer=None` → no hay atribución → **compositor desconocido** (nunca Anonymous/Traditional).
- `composer` explícito → existe **evidencia de atribución** → **no implica automáticamente** `resolved`.
- `resolved` → identidad de obra suficientemente estable + atribución/evidencia suficiente + sin ambigüedad material.
- `resolved_auth` → `resolved` + autoridad ISWC/IPI fiable y correspondencia demostrada.

`composer` es una **señal de `resolution_confidence`**, no la regla que determina
`expected_resolution`. Se conservan por separado `composer_explicit`, `composer_value` y
`composer_traditional` (este último **solo** true si una fuente lo identifica explícitamente
como tradicional/anónimo; nunca inferido).

## Consecuencias

- **Métricas separadas**: p. ej. `resolved 78%` y `resolved_auth 23%`, sin que el segundo
  contamine la evaluación del matcher.
  - `resolved` mide la resolución de identidad realizada por OSAP.
  - `resolved_auth` mide esa misma identidad respaldada además por identificadores de
    autoridad de alto nivel (ISWC/IPI).
- **La ausencia de ISWC/IPI no invalida una obra `resolved`.**
- **CISAC**: esperamos su respuesta. Si concede acceso, ISWC/IPI pasan a ser una fuente más
  de autoridad (`resolved_auth`). Si no, quedan explícitamente *"no disponibles desde
  nuestras fuentes"* y el sistema sigue resolviendo identidad con el resto de fuentes.
- `authority_identifiers` acumula toda la evidencia (Wikidata, MusicBrainz, VIAF, ISNI,
  LCCN, ISWC, IPI) con su `source`/`confidence`/`metadata_json`, sin imponer unicidad de
  `scheme+value` mientras no decidamos la política de conflictos de autoridad.
