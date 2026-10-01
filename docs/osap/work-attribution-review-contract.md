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
| Atribuciones | 12.569 | 12.569 | Contexto completo por obra | Decisión por obra, agrupable por patrón (`attr_type`/nota ya coherentes) |
| Conflictos | 119 | — | Ambas propuestas | `persona_gana` / `atribucion_gana` / `revisar_manual` |

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
| `artefacto` | `descartar` \| `conservar_para_investigacion` | — | No escribe en catálogo; descarta o encola investigación |
| `conflict` | `persona_gana` \| `atribucion_gana` \| `revisar_manual` | — | Resuelve la coherencia de la obra |

Campos: `item_key` (trazabilidad al item), `evidence_json` (texto de origen, muestra, motivo),
`notes`, `decided_by`, `decided_at`, `batch`.

### Decisiones por lote (sin cambiar el esquema)
Una acción humana sobre un lote (p. ej. “aceptar el tramo A”) se materializa como **una decisión por
unidad** con el mismo `batch` y `evidence.decision_mode = "bulk:<tramo>"` + `evidence.sample_ref`.
Así el artefacto sigue teniendo una fila por unidad (auditable) y la UI puede crearlas en bloque.

## 4. Cómo lo consumirá el aplicador (Fase 6, sin construir aún)

1. Resolver `work_key` → `works.id` y `person_key` → `persons_id` **por entorno**.
2. Construir el plan por obra: relaciones (`persona×rol`) + atribución decidida.
3. **Coherencia obligatoria**: si una obra tiene `identity=accept|map_to_existing|create_person` **y**
   `attribution=anonymous|traditional`, no se aplica hasta que exista una decisión `conflict`.
4. Escribir en una transacción: `works_person_roles` + `work_attribution_audit` (con `proposal_id`/
   decision) y, si procede, `works.works_attr_type`/`works_attribution_note`.
5. Idempotente y reversible: el historial liga relación ↔ decisión.
6. `create_person` es el **único** camino que crea personas.

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
