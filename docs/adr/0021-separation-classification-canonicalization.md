# ADR-0021 – Separation of Classification and Canonicalization

## Estado

Aceptado.

## Contexto

El `Lexicon` actual es un **clasificador**: responde a *"¿qué es este término?"*
(`"sonata" → form`, `"SATB" → instrumentation`, `"BWV" → catalogue`). No responde a
*"¿cuál es la forma canónica de este concepto?"*. Si el Lexicon creciera hasta
clasificar, normalizar y comparar a la vez, acabaría siendo un "diccionario mágico"
con demasiadas responsabilidades.

## Decisión

Separar dos responsabilidades distintas, **sin mezclarlas**:

- **Lexicon** → clasifica. Pipeline: `token → categoría`. Se mantiene **exactamente
  como está**.
- **Canonicalizer** (o `Normalizer`) → transforma alias en **forma canónica** mediante
  **reglas declarativas**, no algoritmos:
  ```yaml
  canonical: "KV"
  aliases:
    - K
    - K.
    - KV
    - Köchel
  ```
  ```yaml
  canonical: "Wolfgang Amadeus Mozart"
  aliases:
    - Mozart
    - W.A. Mozart
    - W A Mozart
    - Wolfgang A Mozart
  ```
- **WorkMatcher** → compara **solo representaciones ya normalizadas**.

Pipeline resultante:

```
texto → Tokenizer → Lexicon → Categorías → Canonicalizer → Forma normalizada → WorkMatcher
```

### Principio

> Lexicon clasifica términos.
> Canonicalizer transforma alias en representaciones canónicas.
> WorkMatcher solo compara representaciones ya normalizadas.

## Consecuencias

- Cada componente tiene **una única responsabilidad**.
- Cambiar la forma canónica (p. ej. `KV 618` → `Köchel 618`) **no toca** el Lexicon,
  el Matcher ni el Search Engine: solo el Canonicalizer.
- El Canonicalizer es **determinista y auditable** (reglas declarativas, sin caja negra),
  coherente con la filosofía del Evidence Engine.
- La normalización no depende de proveedores: es inversión permanente para IMSLP, OMR,
  MuseScore, CPDL o YouTube.
- El Lexicon no se convierte en un diccionario multiuso.
