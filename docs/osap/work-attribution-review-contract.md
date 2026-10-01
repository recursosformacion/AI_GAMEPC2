# Contrato de la revisión humana (atribuciones e identidades)

Fase posterior a `015`. El artefacto (`review_items` + `import_person_parse`) está **cerrado**: no se
modifica el generador salvo defecto sistemático descubierto por la propia revisión.

Regla de frontera: **ninguna decisión escribe en el catálogo** hasta que exista el aplicador de Fase 6.
Hasta entonces: `review_decisions` es solo el registro de decisiones humanas.

## 1. Unidades de decisión (lo que se revisa)

| Unidad (`item_type`) | Unidades en Prod | Obras | Qué decide el humano |
|---|---:|---:|---|
| `identity_cluster` | 25.789 | 121.784 | ¿Esta identidad es la persona correcta para todas las obras del clúster? |
| `ambiguous_identity` | 31 | 1.124 | Elegir entre candidatos del catálogo (o dejar sin resolver) |
| `work_attribution` | 12.569 | 12.569 | La atribución de la obra: `anonymous` / `traditional` / `unknown` / `identified` |
| `posible_artefacto` | 3.146 | 4.259 | ¿Es una persona real (investigar) o un artefacto textual (descartar)? |
| **conflicto persona ↔ atribución** | **119 obras** | — | Coherencia: no puede quedar `identificado` **y** `anónimo/tradicional` a la vez |

Los conflictos **no** son una cuarta tabla: son una **vista** sobre las obras que aparecen a la vez en
un `identity_cluster` y en una `work_attribution`. Se presentan juntos y requieren resolución explícita.

## 2. Tramos de riesgo (para trabajar por lotes, no fila a fila)

Medido en el artefacto: los clústeres de identidad se reparten así.

| Tramo | Clústeres | Obras | Evidencia disponible | Tratamiento propuesto |
|---|---:|---:|---|---|
| **A** resuelto con ancla (VIAF/MBID/ISNI) | 859 | 13.826 | Fuerte (ancla tipada) | Decisión **por lote**, con muestra revisada y registrada |
| **B** resuelto sin ancla | 20.559 | 89.679 | Nombre canónico + candidato | Sublotes por evidencia (p. ej. candidato con muchas obras y nombre inequívoco) + cola de excepciones |
| **C** con saneamiento | 457 | 7.114 | Nombre corregido (`flags`) | Revisión **individual** asistida (mostrar texto de origen y flags) |
| **D** ficha destino contaminada | 299 | 1.964 | Candidato con nombre sucio | Revisión **individual**: mapear a la identidad real o descartar |
| **E** persona nueva | 3.581 | 7.278 | Sin coincidencia en catálogo | Decisión binaria: `create_person` o `not_a_person` |
| **F** ambiguo | 30 | 1.923 | Varios candidatos | Elegir candidato (`map_to_existing`) o `leave_unresolved` |
| Artefactos | 3.146 | 4.259 | Motivo (`posible_titulo`, `concatenacion`, …) | `descartar` o `conservar_para_investigacion` |
| Atribuciones | 12.569 | 12.569 | Contexto completo por obra | Decisión por obra; agrupable por patrón coherente (`attr_type`/nota) |
| Conflictos (plan incompleto) | 119 | — | Ambas propuestas | `persona_gana` / `atribucion_gana` / `revisar_manual` |

## 3. Contrato de `review_decisions`

Claves **lógicas, sin UUID ni ids locales** (aplicables idénticamente en Dev y Prod):

- `work_key` = `PDMX:<works_key>` | `CPDL:<origin_id>`
- `person_key` = ancla tipada (`viaf:…`, `musicbrainz:…`, `mbid:…`, `isni:…`) o `name:<normalizado>`
- `role_key` = clave canónica (composer, arranger, adapter, transcriber, librettist, editor, orchestrator)
- Único por `decision_key` = (`decision_type`, `work_key`, `person_key`, `role_key`)

### Vocabulario por `decision_type`

| `decision_type` | `decision` | `target_person_key` | Semántica / efecto para el aplicador |
|---|---|---|---|
| `identity` | `accept` | — | La resolución del clúster es correcta → se aplican sus relaciones (obra×rol) |
| `identity` | `map_to_existing` | sí | La identidad correcta es otra ficha → se aplican sus relaciones contra ese destino |
| `identity` | `create_person` | — (nombre+evidencia) | Crear persona nueva en cada entorno y aplicar sus relaciones |
| `identity` | `not_a_person` | — | No es persona → no se aplica nada (se registra el descarte) |
| `identity` | `leave_unresolved` | — | No se decide ahora → no se aplica |
| `relation` | `accept` \| `reject` \| `uncertain` | — | Excepción por obra×persona×rol (override del clúster) |
| `attribution` | `anonymous` \| `traditional` \| `unknown` \| `identified` | — | Atribución de la obra (con `attr_type`/nota cuando aplique) |
| `artefacto` | `descartar` \| `conservar_para_investigacion` | — | No escribe en catálogo; descarta el registro o lo encola para investigación. El motivo va en evidencia, no en el estado |
| `conflict` | `persona_gana` \| `atribucion_gana` \| `revisar_manual` | — | Resuelve la coherencia de la obra |

Campos: `item_key` (trazabilidad al item), `evidence_json` (texto de origen, muestra, motivo),
`notes`, `decided_by`, `decided_at`, `batch`.

**Vocabulario de artefactos**: `descartar` / `conservar_para_investigacion` (no `reject`/`keep`:
expresan qué se decide sobre el **registro**, no un rechazo a una persona). Los motivos
(`posible_titulo`, `concatenacion`, `texto_truncado`, `prefijo_atribucion`) **no son estados**:
viajan en `evidence.artifact_reason`.

**`works_attr_type` nunca es efecto de una decisión `identity`.** Solo una decisión `attribution`
puede desembocar en escribir `works.works_attr_type` / `works_attribution_note`, y **solo** cuando el
conflicto de esa obra esté resuelto. En particular, `persona + traditional` **no** se convierte
automáticamente en `traditional`: una obra tradicional puede tener arreglista, transcriptor o editor.

### Lotes explícitos (mecanismo de creación, no sustituto de decisiones)
Un **lote** no sustituye las decisiones: es un mecanismo para **generarlas**.

```
acción humana → batch explícito → N unidades seleccionadas → una decisión por unidad
                (evidence.decision_mode = "bulk:<tramo>", evidence.sample registrada)
```

- **Tramo A** (ancla tipada, evidencia fuerte): se permiten **lotes grandes**.
- **Tramo B**: **nunca** un “aceptar todo B” global. Solo **sublotes homogéneos por evidencia**, con
  la forma `B / person_key / role / patrón de evidencia`, y cada sublote debe mostrar **antes** de
  aplicarlo: número de obras, identidad candidata, anclas disponibles, nombres observados,
  fuentes/patrones, una muestra representativa y las excepciones detectadas.
- Cada resolución queda **materializada y auditable como decisión individual** en `review_decisions`.

## 4. Separación decisión ↔ ejecución, y plan final por obra

La **decisión humana** (arriba) y la **ejecución** (Fase 6, aún sin construir) son planos distintos:
`review_decisions` registra qué decidió una persona; el aplicador decide **cuándo** y **cómo** el
catálogo pasa a un estado coherente.

**Regla de coherencia**: *una obra no se aplica hasta que todas las decisiones que afectan a su estado
final sean coherentes*. Los 119 conflictos no son un caso especial del SQL: son simplemente **obras
cuyo plan todavía está incompleto**.

El aplicador no ejecuta decisiones aisladas; construye un **plan final por obra**:

```
obra
 ├── identidad/personas aprobadas
 ├── relaciones aprobadas (persona × rol)
 ├── attribución final
 └── conflicto resuelto
          ↓
      una transacción
```

1. Resolver `work_key` → `works.id` y `person_key` → `persons_id` **por entorno**.
2. Componer el plan por obra a partir de las decisiones (incluidas las excepciones `relation`).
3. **Bloquear** la obra si su plan no es coherente (p. ej. identidad aprobada + atribución
   `anonymous`/`traditional` sin decisión de `conflict`).
4. Escribir en una transacción: `works_person_roles` + `work_attribution_audit` (ligado a la decisión)
   y, solo desde una decisión `attribution`, `works.works_attr_type` / `works_attribution_note`.
5. **`set_attribution` no se invoca directamente desde cada decisión** de revisión: el aplicador
   determina primero el estado coherente de la obra y ejecuta la modificación necesaria. Así se evita
   que borre relaciones de persona recién aprobadas.
6. Idempotente y reversible: el historial liga relación ↔ decisión.
7. `create_person` es el **único** camino que crea personas.

## 5. Orden de revisión propuesto (eficiencia)

1. **Conflictos (119 obras)** — pequeños y bloquean la aplicación.
2. **Tramo A (859)** — por lote con muestra.
3. **Clústeres de mayor impacto** (los 60 de >50 obras y los siguientes tramos) — una decisión resuelve
   cientos de obras.
4. **F (30) + D (299) + C (457)** — individuales, requieren contexto.
5. **Artefactos (3.146)** — por motivo, en bloque (descartar/conservar).
6. **E (3.581)** — `create_person` / `not_a_person`, agrupable por patrón de nombre.
7. **B (20.559)** — sublotes por evidencia + cola de excepciones.
8. **Atribuciones (12.569)** — por patrón y luego individuales.

Objetivo: que la mayoría de las 121.784 obras se resuelvan con **pocas decisiones de alto impacto**,
sin convertir la revisión en 41.535 pulsaciones.

## 6. Guardarraíles
- Nada se aplica al catálogo hasta que exista el aplicador.
- `review_decisions` = 0 mientras no empiece la revisión.
- El generador no se toca salvo defecto sistemático demostrado por la revisión.
- Toda decisión es trazable (quién, cuándo, con qué evidencia) y reproducible en Dev y Prod.

## 7. Hallazgos de la revisión (y pendientes anotados)

### 7.1 Corregido
- **Conflicto ≠ “hay persona y atribución”**: solo hay conflicto si la persona propuesta es **compositor/a**
  **en esa obra**. Una obra tradicional puede tener arreglista, transcriptor o editor sin contradicción.
  Efecto: los conflictos pasan de **119 a 36** (34 `traditional` + 2 `anonymous`; en los 36 la relación en
  conflicto es la de **compositor**).
- **El conflicto es por (obra × persona × rol)**, no por persona agregada: la misma persona puede aparecer
  como **arreglista** en una obra tradicional (correcto) y como **compositor** en otra (conflicto). La vista
  y la decisión **nunca** mezclan roles: la decisión `conflict` afecta **solo a la hipótesis de compositor**
  de esa obra; las relaciones de arreglista/transcriptor/editor de esa persona quedan intactas.
- **Vocabulario**: el idioma interno (`attribution_status`, inglés minúscula) y el del catálogo
  (`works.attr_type`, castellano mayúscula) son el mismo concepto — `traditional` ≡ `TRADICIONAL`,
  `anonymous` ≡ `ANONIMA`. La vista muestra ambos.

### 7.2 Pendientes (parser / catálogo / proceso)
1. **Parser — cortar en marcadores sin “by”**: `transcribed`, `arranged`, `adapted`, `composed`, `edited`,
   `orchestrated` (hoy solo se corta en `… by`). Ejemplo: `English Traditional arr. Hardy Oliver Urbank
   transcribed T. Potten` extrae hoy el arranger como “Hardy Oliver Urbank transcribed T. Potten”.
2. **Catálogo — rol “Traductor/a”** (id 17, clave `translator`) + marcadores `translated by`, `translation by`,
   `traducido por`, `traducción de`, `traductor`. Sin él, `translated by X` pierde la persona. **Nunca** usar
   “trad.” a secas como marcador (colisiona con `Traditional`).
3. **Catálogo/alias — usuarios digitales**: `EFPIANIST` es el nombre de usuario del pianista Eduardo Fernández;
   mapearlo a la persona real es tarea de **alias**, no del parser (el parser respeta lo que dice la fuente).
4. **Proceso — corrección de decisiones**: hoy `DecisionExistenteDistinta` impide sobrescribir una decisión
   humana; falta definir el mecanismo explícito de revisión/corrección **con historial** antes de que la
   revisión sea prolongada.
5. **Operativo — Prod**: re-ejecutar el generador en Producción para que sus conflictos pasen de 119 a 36
   (backup → `build_review_items --apply` → controles), antes de revisar.

### 7.3 Glosario de la fuente
- `Traditional English carol` = **Villancico tradicional inglés** (descriptor de género; no es una persona).
- `Trad. ed. X` = tradicional + **editor/a** (rol 6). Confirmar si en algún contexto `ed.` significa traducción.
- `arr.` / `arranged by` = arreglista (rol 3) · `transcribed by` = transcriptor (rol 5) · `adap.` = adaptador (rol 16).
