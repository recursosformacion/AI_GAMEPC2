# ADR-0022 – Separation of Identity, Matching and Ranking

## Estado

Aceptado.

## Contexto

En V2.1 conviven tres motores con responsabilidades aparentemente solapadas:
`Canonicalizer` (normalización), `WorkMatcher` (identidad/agrupación) y `WorkRanker`
(ordenación). Antes de conectar el pipeline completo es necesario congelar **por qué**
están separados, para que la integración no los vuelva a mezclar.

## Decisión

Tres responsabilidades distintas e independientes, en tres componentes puros:

1. **Identity** (`Lexicon` + `Canonicalizer`) — normaliza: convierte variantes en
   formas canónicas (conceptos, no cadenas).
2. **Matching** (`WorkMatcher`) — decide si A y B representan la **misma** obra.
3. **Ranking** (`WorkRanker`) — ordena las alternativas ya identificadas.

### Principios

- **El Matching decide identidad; el Ranking ordena.** El Ranking **nunca** cambia la
  identidad de una obra ni "corrige" decisiones del Matcher.
- **El Matching compara conceptos canónicos, no cadenas** (recibe salida del
  Canonicalizer).
- Cada componente es **puro, determinista, explicable y sin IA**; habla por contratos
  tipados.

## Consecuencias

- Cada componente puede sustituirse sin romper los demás (contratos bien definidos).
- Evita el "diccionario mágico" (clasificar + normalizar + comparar + ordenar a la vez)
  y el "ranking que corrige al matcher" (defecto común en buscadores).
- El pipeline queda: `Tokenizer → Lexicon → Canonicalizer → WorkMatcher → WorkGroup →
  Ranking → Evidence`. Cada flecha es un contrato.
- Añadir un criterio de ranking nuevo (V3) no toca el Ranker (objetos `Strategy`);
  añadir una regla de canonicalización no toca el Canonicalizer (reglas declarativas).
