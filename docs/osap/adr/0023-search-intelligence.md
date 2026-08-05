# ADR-0023 – Search Intelligence (cierre de V2.1)

## Estado

Aceptado. Cierre del hito **V2.1** (`v2.1.0`).

## Motivación

Separar en componentes independientes las tres responsabilidades de la búsqueda
inteligente: **normalización**, **identidad** y **ranking**. Evitar el "diccionario
mágico" (un solo componente que clasifica, normaliza, compara y ordena) y el defecto
del "ranking que corrige al matcher".

## Decisión

Pipeline de Search Intelligence, cada flecha es un contrato tipado:

```
Canonicalizer
     ↓
WorkMatcher
     ↓
WorkGrouping
     ↓
Ranking
```

- **Canonicalizer** → normaliza (conceptos canónicos, no cadenas).
- **WorkMatcher** → decide si dos obras son la misma (`MatchLevel`).
- **WorkGrouping** → agrupa representaciones en obras (`WorkGroup`).
- **Ranking** → ordena las obras; **nunca cambia la identidad**.

Todos son componentes **puros, deterministas, explicables y sin IA**, con contratos
tipados (`*Config`, `*Context`, `*Reason`, `*Result`, `*Criterion`).

## Consecuencias

- **Componentes reutilizables**: cada uno puede sustituirse sin romper los demás.
- **Explicabilidad**: cada componente devuelve razones tipadas (no texto).
- **Determinismo**: misma entrada → misma salida.
- **Tests independientes** por componente + **pipeline de integración del dominio**
  validado de extremo a extremo (aislado de infraestructura).
- **Contratos congelados**: `domain/` y `ports/` se consideran **API pública**; a partir
  de aquí, cambiar un contrato requiere un nuevo ADR.
