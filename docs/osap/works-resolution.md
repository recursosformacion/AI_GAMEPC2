# Resolución de obras en lote (v1) — Propuesta

Servicio que recibe **works** y devuelve cada obra **resuelta y limpia**: candidatos de
obra/compositor + normalización + evidencia + confianza + estado. API **no modifica
storage**; el llamante (storage) solicita las obras progresivamente y decide qué aceptar.

## Endpoint

```
POST /api/v1/works/resolve
```

No es administración. No envía `work_id` interno de storage (es la identidad lo que se
resuelve). No modifica nada.

### Request

```jsonc
{
  "works": [
    { "id": "w1",
      "composer": { "name": "ä æ R Z H çèª" },
      "work": { "title": "Song to the Auspicious Cloud - Second Version", "catalog": "192128", "year": 1921 },
      "source": { "provider": "pdmx", "source_work_id": "229680" } },
    { "id": "w2", "work": { "title": "Ave Verum Corpus, K. 618" } }
  ],
  "concurrency": 4
}
```

- `works[].id` (opcional): eco del llamante para correlacionar.
- `concurrency`: límite de resoluciones simultáneas (bajo al principio, p. ej. 4).
- Cada obra se resuelve de forma independiente; una fallida no aborta el lote.

### Response

```jsonc
{
  "results": [
    {
      "id": "w1",
      "status": "resolved | ambiguous | not_found",
      "normalized": {
        "title_raw": "Song to the Auspicious Cloud - Second Version",
        "title": "song to the auspicious cloud second version",
        "composer_raw": "ä æ R Z H çèª",
        "composer": "ä æ r z h çèª",
        "catalog": "192128"
      },
      "resolved": {
        "work": { "title": "Song to the Auspicious Cloud", "catalog": "192128" },
        "composer": { "name": "Xiao Youmei", "aliases": [], "external_ids": { "musicbrainz": "..." } }
      },
      "confidence": 0.94,
      "input_quality": "corrupt_or_suspicious",
      "candidates": [],
      "evidence": [
        { "provider": "imslp", "kind": "work_match", "confidence": 0.95, "work_title": "..." },
        { "provider": "wikidata", "kind": "external_id", "confidence": 0.85 }
      ]
    }
  ],
  "summary": { "total": 250, "resolved": 180, "ambiguous": 40, "not_found": 30 }
}
```

- `composer` puede ser `null`: la **obra** puede estar resuelta aunque **no se haya podido
  determinar el compositor** con confianza suficiente (obra resuelta y compositor resuelto
  son dos resultados conceptualmente diferentes).
- `normalized` = transformación **determinista** del texto recibido (`*_raw` conservados).
- `resolved` = **conclusión** obtenida mediante fuentes/evidencias (no es normalización).
- Los datos de entrada y salida son los **works**; en salida se añade el grupo
  `normalized + resolved` por obra, sin alterar el original.

## Pipeline (por obra)

1. **Preparar entrada**: se conservan los originales y se generan formas comparables
   (`title_raw`, `title`, `composer_raw`, `composer`, `catalog`).
2. **Resolver la obra**: título + catálogo + compositor (si existe) a través del
   `WorkResolutionEngine` existente → candidatos de obra.
3. **Obtener compositores candidatos** de la obra encontrada.
4. **Resolver identidad de compositor**: `WikidataIdentityResolver` (+ canónico) →
   external IDs/aliases.
5. **Combinar evidencias**.
6. **Decidir estado**: `resolved|ambiguous|not_found`.
7. **Devolver resultado** (`normalized` + `resolved`).

Un compositor corrupto (`input_quality != normal`, p. ej. `"ä æ R Z H çèª"`) **no es una
restricción fuerte**: se resuelve la obra y se obtiene el compositor candidato de ahí,
no del nombre corrupto.

## Qué se reutiliza (ya escrito)

- `WorkResolutionEngine` / `WorkComposerMatcher` → fase **work_match** (IMSLP, OMR, Mutopia, MusicBrainz).
- `ComposerResolutionEngine` + `ResolveComposerUseCase` → motor de decisión por obra.
- `WikidataIdentityResolver` → identidad + external IDs.
- `MetadataNormalizer` (canonical_composer, comparison_title) → normalización.

## Componentes nuevos

1. `WorksResolveUseCase` — itera las obras con un semáforo (`concurrency`) y agrupa resultados.
2. Contratos `WorksResolveRequest/Response` + DTO de resultado por obra.
3. Endpoint `POST /api/v1/works/resolve`.
4. `summary` (resolved/ambiguous/not_found) para la primera prueba.

## Prueba inicial (250 obras)

- `concurrency: 4`, midiendo `resolved/ambiguous/not_found` y la **calidad real** de las
  resoluciones (muestreo manual).
- Los resultados servirán para decidir si el concepto correcto es **Work Resolution**
  (frente al `composer/resolve` actual) antes de cerrar contratos.
- Se mantiene `composer/resolve` sin cambios mientras tanto.
- `/works/resolve` **no escribe** en storage: el flujo es storage → API → resolver →
  resultado → storage decide. La escritura/aceptación sería una segunda fase.

### Cómo ejecutar el experimento

```bash
python script/works_resolve_experiment.py <works.json> --base https://app.openmusicrepository.com/api/v1 --concurrency 4
```

`works.json` = `{ "works": [ { "id": "...", "composer": {"name": "..."}, "work": {"title": "...", "catalog": "..."} } ] }`.

Mide: `resolved` / `ambiguous` / `not_found`, `composer null` (obra sin autor),
`input_quality = corrupt_or_suspicious`, y proveedores que aportan evidencia, además de
una muestra por estado para revisión manual. Ejemplo de muestra:
`script/works_resolve_sample.json`.

### Hallazgos iniciales (muestra de 10)

- Muchas obras bien conocidas quedan `ambiguous` con `composer: null`: el `work_match`
  devuelve varios compositores a **confianza plana 0.9**, sin margen → no decide el autor.
  Falta gradar la confianza por la calidad del emparejamiento (fase posterior).
- Un `resolved` puede ser **incorrecto** (Bach BWV 565 → BWV 862): revisar manualmente
  cada `resolved` es imprescindible; un `resolved` erróneo es peor que un `ambiguous`.
- El caso pdmx ("Song to the Auspicious Cloud") da `not_found`: no está en los catálogos
  actuales (honesto, no inventa).
