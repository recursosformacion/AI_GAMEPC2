# Knowledge Mining — Diseño (V2.2.d)

> **Status: draft** (iteración 3 — se congelará antes de la implementación de V2.2.d).
>
> Parte de V2.2. Define cómo OSAP convierte la información que **ya produce** en
> **conocimiento reutilizable**. No se escribe código hasta congelar este diseño.
> No es minería de datos en el sentido de IA.

## Principio rector

> **Knowledge Mining nunca modifica el conocimiento del sistema. Solo transforma
> observaciones repetidas en sugerencias verificables.**

Es la misma filosofía de todas las versiones:

- Matcher **identifica**.
- Ranking **ordena**.
- Merge **consolida**.
- Evidence **explica**.
- Knowledge Mining **aprende, pero no decide**.

---

## 1. Objetivo

Hasta ahora el sistema sabe **cómo** canonizar, identificar, rankear, fusionar y
explicar — pero **olvida todo cuando termina la búsqueda**. Cada `WorkGroup`, cada
`MergedWorkDescriptor` y cada `EvidenceResult` es información descartada al acabar.

Knowledge Mining responde a la pregunta: **¿qué hemos aprendido después de miles de
búsquedas?**

Ejemplos:

- `"KV618"` aparece muchísimo → añadir alias canónico.
- IMSLP siempre usa `"Ave Verum Corpus K.618"` → aprender ese alias.
- Dos proveedores discrepan continuamente en cierto catálogo → registrar esa anomalía.
- El 95 % de las veces MusicBrainz tiene el catálogo correcto → aumentar su autoridad
  para ese campo.

**No modifica una búsqueda. Aprende de muchas.**

---

## 2. ¿Qué aprende OSAP?

No todo. **Solo hechos útiles.**

- **alias nuevos** — formas alternativas observadas con frecuencia;
- **autoridades observadas** — proveedores que aciertan en un campo con consistencia;
- **frecuencias** — cuánto aparece cada variante / valor;
- **discrepancias** — desacuerdos sistemáticos entre proveedores;
- **patrones** — regularidades que un humano podría convertir en regla.

Cada observación aislada es ruido; lo que aprende OSAP son **patrones repetidos** que se
convierten en **sugerencias verificables**.

---

## 3. ¿Qué nunca aprende?

**Muy importante.** Nunca aprende:

- **identidad** (nunca decide si dos obras son la misma);
- **reglas del Matcher**;
- **reglas del Ranking**;
- **políticas** (`MergePolicy`, preferencias...);
- **pesos** (del ranking, del merge...).

Porque eso **rompería el determinismo**. Si el sistema cambiara su propio
comportamiento, las mismas entradas dejarían de producir las mismas salidas. Knowledge
Mining es **observador pasivo**: lee, acumula y sugiere; jamás se altera a sí mismo.

---

## 4. ¿Dónde vive ese conocimiento?

**`KnowledgeBase` es un Value Object inmutable**, igual que `EvidenceSummary` o
`RankingContext`. Representa el **estado completo del conocimiento aprendido por OSAP en
un instante dado**, igual que `RankingResult` representa el resultado completo del
ranking. Expone exactamente tres colecciones:

```python
@dataclass(frozen=True)
class KnowledgeBase:
    observations: tuple[KnowledgeObservation, ...]
    facts: tuple[KnowledgeFact, ...]
    suggestions: tuple[KnowledgeSuggestion, ...]
```

Y los tres tipos que almacena:

- **`KnowledgeObservation`** — un hecho observado durante una ejecución
  (p. ej. `proveedor=IMSLP, campo=title, valor="K.618"`). Es **inmutable** y representa
  **un hecho observado**: **no un resumen, no una estadística**. Pertenece
  **exactamente a una ejecución** (una sola `execution_id`), propiedad que importará si
  algún día los Jobs pasan a ser distribuidos.
- **`KnowledgeFact`** — una observación **derivada** (frecuencias, consistencias,
  discrepancias) con su contexto. **Nunca aparece directamente desde un componente**:
  siempre nace del Collector/Miner. Un Fact siempre debe ser **reproducible**,
  **verificable** y **trazable** — los tres juntos.
- **`KnowledgeSuggestion`** — una propuesta **accionable y verificable** derivada de un
  conjunto de hechos. Es **reproducible**: re-ejecutar el Miner sobre la misma
  `KnowledgeBase` produce exactamente las mismas sugerencias (determinismo). **Nunca
  constituye conocimiento del sistema; únicamente propone una posible evolución del
  mismo** (no forma parte del dominio).

La `KnowledgeBase` es **acumulativa**: crece con las ejecuciones, nunca se sobreescribe
con una sola búsqueda.

---

## 5. ¿Quién produce conocimiento?

**No un módulo mágico: todos.** Cada componente del pipeline puede emitir
observaciones:

- **Canonicalizer** — alias observados, formas canónicas frecuentes.
- **Matcher** — coincidencias y desacuerdos por campo.
- **Ranking** — qué criterios decidieron de forma consistente.
- **Merge** — valores enriquecidos y conflictos repetidos.
- **Evidence** — hechos estructurados ya producidos.

Cada uno **puede** emitir **`KnowledgeObservation`** sin cambiar su comportamiento
actual: es una **salida adicional** del proceso, no una mutación.

---

## 6. ¿Quién decide aceptarlas?

**No el propio componente.** Hay dos roles **claramente separados**:

```
Emitter
      │
      ▼
KnowledgeCollector
      │
KnowledgeObservation
      │
      ▼
KnowledgeMiner
      │
KnowledgeFact
      │
      ▼
KnowledgeSuggestion
```

- **`KnowledgeCollector`** — **no piensa, solo recoge.** Acumula y normaliza lo emitido
  por los componentes en `KnowledgeObservation`.
- **`KnowledgeMiner`** — **analiza.** Agrega observaciones en `KnowledgeFact` y deriva
  `KnowledgeSuggestion`.

El componente emisor no decide nada: solo reporta. La decisión de qué es útil vive en el
collector/miner, separada de la producción.

---

## 7. Puertos

Como toda la V2, Knowledge Mining expone **puertos**. Solo el contrato, nada más:

- **`IKnowledgeCollector`** — recoge observaciones emitidas por los componentes
  (no piensa, solo recoge).
- **`IKnowledgeMiner`** — analiza: agrega observaciones en hechos y deriva sugerencias
  (reproducible).

La implementación concreta (y su ejecución) queda para la fase de implementación.

---

## 8. ¿Quién modifica el sistema?

**Nadie.** Knowledge Mining **nunca cambia el comportamiento** del sistema. Solo genera
**sugerencias**. La aplicación de una sugerencia es siempre **una decisión humana**, fuera
del pipeline.

```
Suggestion
  Añadir alias:
  "Ave Verum K618"
        ↓
  Canonical title:
  "Ave Verum Corpus KV 618"
        ↓
  (un humano decide)
```

> Este apartado merece un **ADR propio**: *Knowledge Mining nunca modifica el sistema,
> solo propone; la decisión es siempre humana.* Es un principio que probablemente
> sobrevivirá hasta V4.

---

## 9. Flujo de una sugerencia

```
Ejecución → componentes emiten KnowledgeObservation
        ↓
KnowledgeCollector → agrega → KnowledgeFact (frecuencias, consistencias)
        ↓
KnowledgeMiner → KnowledgeSuggestion (accionable, verificable)
        ↓
humano revisa y decide (sí / no / revisar)
```

Una sugerencia debe poder **verificarse**: referencia los hechos y observaciones que la
sustentan (procedencia), igual que Merge expone `provenance`.

---

## 10. Invariantes

- **No mutación**: Knowledge Mining jamás altera contratos congelados, resultados ni
  comportamiento.
- **Determinismo**: acumular observaciones no cambia ninguna búsqueda presente ni futura
  hasta que un humano decide.
- **Procedencia**: cada hecho y sugerencia referencia sus observaciones de origen.
- **Acumulación**: las observaciones se agregan; ninguna búsqueda aislada se vuelve regla.
- **Desacople**: los emisores no deciden; el collector/miner no emite; nadie aplica.
- **Monotonicidad**: la incorporación de nuevas observaciones **nunca invalida** las
  observaciones anteriores; únicamente puede producir nuevos Facts o nuevas Suggestions.

---

## 11. Criterios de aceptación (V2.2.d)

- **contratos congelados** antes de implementar;
- Knowledge Mining **no modifica** el comportamiento del sistema;
- tipos `KnowledgeObservation`, `KnowledgeFact`, `KnowledgeSuggestion` y `KnowledgeBase`
  definidos e inmutables;
- emisores en Canonicalizer, Matcher, Ranking, Merge y Evidence;
- collector/miner que consolida y agrega;
- toda sugerencia es **verificable** (con procedencia);
- la aplicación de sugerencias es **siempre humana**;
- tests **deterministas**;
- **sin modificar el núcleo** V2.0 / V2.1 / V2.2 (a, b ni c).

---

## Nota de alcance

Este documento se mantiene **centrado en contratos, responsabilidades e invariantes**,
sin entrar todavía en **algoritmos ni persistencia** (qué frecuencias, qué umbrales, cómo
se almacena `KnowledgeBase`). Ese detalle se decidirá en la fase de implementación, una
vez congelado este diseño.

Con Knowledge Mining implementado, el **núcleo funcional del dominio de OSAP queda
completo** antes de pasar a la API y a la interfaz web.

> **Knowledge Mining es el único componente del dominio cuyo objetivo no es resolver una
> búsqueda, sino mejorar el conocimiento disponible para futuras versiones del sistema.**
