# Resolución de identidad de compositor (v1)

Operación **de resolución de identidad**, no una búsqueda genérica. El llamante entrega
el contexto que tiene de un compositor/obra; osap-api consulta las fuentes que conoce,
genera candidatos y devuelve una resolución con evidencia y confianza. **No modifica nada
en storage**: el llamante decide después qué hacer con el resultado.

## Endpoint

```
POST /api/v1/composers/resolve
```

No es una operación de administración. No envía ni recibe `composer_id`: el ID de storage
es interno al catálogo y no condiciona la resolución.

### Request

`work.title` es obligatorio (la obra es la señal principal). `composer.name` es opcional:
el nombre recibido es solo evidencia secundaria (puede estar corrupto), nunca un requisito.

```jsonc
{
  "work": { "title": "Song to the Auspicious Cloud - Second Version", "catalog": "192128", "year": 1921 },
  "composer": { "name": "ä æ R Z H çèª" },
  "source": { "provider": "pdmx", "source_work_id": "229680" },
  "representations": [ { "title": "...", "provider": "pdmx", "format": "musicxml" } ]
}
```

Válido también sin compositor:

```jsonc
{ "work": { "title": "Song to the Auspicious Cloud - Second Version" } }
```

`source` y `representations` son **solo contexto de procedencia del llamante**: OSAP nunca los usa
para elegir qué fuente consultar. El proveedor del llamante (p. ej. `pdmx`) puede que no
exista en OSAP; se llama al endpoint precisamente para averiguar quién es el compositor.
El motor consulta **sus propios resolvers** registrados (canonical, CPDL, …) y resuelve
aunque el proveedor del llamante sea desconocido.

### Response

```jsonc
{
  "status": "resolved|ambiguous|not_found",
  "composer": { "name": "...", "aliases": [], "external_ids": {} },
  "confidence": 0.0,
  "input_quality": "normal|suspicious|corrupt_or_suspicious",
  "candidates": [],
  "evidence": []
}
```

Estados:
- `resolved` — hay un candidato suficientemente fuerte (`confidence >= 0.8` y margen
  `>= 0.15` sobre el segundo).
- `ambiguous` — hay candidatos pero no se decide automáticamente.
- `not_found` — no hay evidencia suficiente.

API nunca inventa un compositor.

## Proceso (pipeline determinista)

1. **Resolver la obra primero** (cuando haya título): buscar la obra en las fuentes
   conocidas y extraer los compositores asociados. La obra es una unidad contextual mucho
   más rica que el nombre aislado.
2. **Resolver la identidad** de esos candidatos (aliases, external IDs).
3. **Normalización**: se conserva el original intacto y se generan formas normalizadas
   (NFKC, case-fold, puntuación) solo para buscar.
4. **`input_quality`**: se detecta si el nombre parece problemático (mojibake, sustitutos,
   demasiado corto, sospechoso). Un nombre corrupto recibe poco peso.
5. **Consultar resolvers** en paralelo; cada fuente devuelve evidencia, no "la verdad".
6. **Motor de decisión**: normaliza centralmente, fusiona candidatos por identidad canónica
   y decide `resolved|ambiguous|not_found`.

El nombre recibido (`composer.name`) nunca se convierte directamente en el nombre correcto
por una regla de limpieza; se conserva como `raw_input` y el resultado se basa en la obra y
las evidencias externas.

## Contrato del ResolverProvider (interno)

En `src/osap/ports/composer_resolver.py`. Es la única abstracción que conoce el endpoint:
añadir una fuente nueva (CPDL, MusicBrainz, Wikidata…) no toca el contrato de la API.

```python
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol


class ResolverCategory(StrEnum):
    CATALOG = "catalog"      # CPDL, IMSLP, ...: aportan work_match
    IDENTITY = "identity"    # MusicBrainz, Wikidata, VIAF: autoridad + IDs externos


@dataclass(frozen=True)
class ResolverQuery:                 # NUNCA lleva composer_id
    work_title: str | None = None
    composer: str | None = None
    work_catalog: str | None = None
    work_year: int | None = None
    source_provider: str | None = None
    source_work_id: str | None = None
    representations: tuple[dict[str, str], ...] = ()   # title/provider/format


@dataclass(frozen=True)
class ResolverEvidence:              # evidencia, no "verdad"
    kind: str                        # work_match | composer_match | external_id | alias
    confidence: float
    work_title: str | None = None
    work_catalog: str | None = None
    source_url: str | None = None


@dataclass(frozen=True)
class ResolverCandidate:             # lo que una fuente cree que es
    name: str
    confidence: float
    aliases: tuple[str, ...] = ()
    external_ids: dict[str, str] = field(default_factory=dict)
    evidence: tuple[ResolverEvidence, ...] = ()


@dataclass(frozen=True)
class ResolverResult:                # respuesta de UN resolver
    provider: str
    candidates: tuple[ResolverCandidate, ...]
    error: str | None = None


class IComposerResolver(Protocol):
    provider_id: str
    categories: frozenset[ResolverCategory]

    async def resolve(self, query: ResolverQuery) -> ResolverResult: ...
```

Reglas:
- El resolver recibe contexto (nombre + obra opcional) y devuelve **candidatos con su
  propia confianza y evidencia**. No decide; no ve `composer_id`.
- `categories` permite al orquestador consultar selectivamente: con obra → CATALOG
  (`work_match`); para autoridad/IDs → IDENTITY. Un proveedor puede estar en ambos.
- Los resolvers devuelven **nombres crudos**; la normalización canónica, la tabla de
  aliases y el merge de candidatos viven en el motor (central).

## Motor de decisión

- Corre los resolvers en paralelo (async).
- Normaliza centralmente con `MetadataNormalizer.canonical_composer` + tabla de aliases.
- Agrega confianzas por identidad canónica y decide:
  - `resolved`: top candidato `>= 0.8` y margen `>= 0.15` sobre el segundo.
  - `ambiguous`: `>= 2` candidatos y no se cumple lo anterior.
  - `not_found`: sin candidatos.
- `input_quality` lo calcula el caso de uso (mojibake/NFKC), no los resolvers.

## Roadmap

1. Contrato del resolver (este doc) + port `IComposerResolver` + DTOs.
2. Motor de decisión + caso de uso + endpoint `POST /api/v1/composers/resolve`.
3. Fase de obra implementada **reutilizando `WorkResolutionEngine`** (los catálogos
   existentes) para extraer los compositores asociados a la obra encontrada.
4. Fase de identidad: resolver canónico funcional (tabla de aliases); MusicBrainz/Wikidata/
   VIAF como stubs desactivados hasta disponer de fuente/credenciales.
5. (Siguiente paso, fuera de esta API) persistir `composer_review`.

## Integración para storage

### Llamada

```
POST https://app.openmusicrepository.com/api/v1/composers/resolve
Content-Type: application/json
```

El endpoint es público (no requiere `storage:admin`). Si storage quiere autenticarse, puede
enviar su service token como `Authorization: Bearer <token>`; no es obligatorio.

### Request

```jsonc
{
  "work": { "title": "Song to the Auspicious Cloud - Second Version", "catalog": "192128", "year": 1921 },
  "composer": { "name": "ä æ R Z H çèª" },
  "source": { "provider": "pdmx", "source_work_id": "229680" },
  "representations": [ { "title": "...", "provider": "pdmx", "format": "musicxml" } ]
}
```

- `work.title` es **obligatorio**. `work.catalog` / `work.year` opcionales.
- `composer.name` opcional (evidencia secundaria). `source` y `representations` son solo
  contexto de procedencia y no condicionan la consulta.

### Response (200)

```jsonc
{
  "success": true,
  "request_id": "554f3b8c...",
  "data": {
    "status": "resolved",
    "composer": { "name": "Xiao Youmei", "aliases": ["萧友梅"], "external_ids": {} },
    "confidence": 0.94,
    "input_quality": "corrupt_or_suspicious",
    "candidates": [
      { "name": "Xiao Youmei", "confidence": 0.94, "aliases": [], "external_ids": {} }
    ],
    "evidence": [
      { "provider": "imslp", "type": "work_match", "confidence": 0.95, "work_title": "Song to the Auspicious Cloud - Second Version", "work_catalog": "192128" },
      { "provider": "canonical", "type": "alias", "confidence": 0.9, "work_title": null, "work_catalog": null }
    ]
  }
}
```

### Procesar la respuesta

- `status`:
  - `resolved` — `composer` es la identidad canónica (confianza ≥ 0.8 y margen ≥ 0.15
    sobre el segundo candidato). Storage puede guardar/mostrar directamente.
  - `ambiguous` — `composer: null`, hay `candidates`; requiere revisión humana.
  - `not_found` — `composer: null`, `candidates: []`; no se inventa un compositor.
- `confidence`: agregado (media) de las confianzas de las fuentes que convergen.
- `input_quality`: calidad del nombre recibido (`normal | suspicious | corrupt_or_suspicious`);
  un nombre corrupto no se convierte directamente en el canónico.
- `evidence`: lista con cada fuente (`provider`), tipo (`work_match | alias | external_id`)
  y confianza; útil para la futura pantalla de administración.
- `candidates`: candidatos ordenados por confianza (para `ambiguous`).

### Errores

- `422` — `work.title` ausente o body inválido (envelope `error.code = VALIDATION`).
- `500` — error interno. En `ambiguous`/`not_found` la API responde 200 con `status`
  correspondiente (no es error).
