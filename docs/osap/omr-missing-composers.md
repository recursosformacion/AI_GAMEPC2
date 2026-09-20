# Compositores que faltan en OMR — cómo conseguirlos

Medido el 2026-09-20 sobre la BD nueva (`osap-storage`) y el índice (`osap-api`).

## Situación
| Dato | Valor |
|---|---|
| Obras en `works` | 310.455 |
| Obras **con** compositor (`works_person_roles` rol 1) | 135.315 (43,6%) |
| Obras **sin** compositor | **175.140** (56,4%) |
| Obras de índice con rep OMR | 150.679 |
| … sin `composer_id` en el índice | 147.648 |
| Obras con `works_attribution_note` | 10.484 |
| Títulos con `" - "` (posible compositor embebido) | 68.047 |
| Personas activas (`persons`) | 45.207 |
| **`works_person_import`** | **386.004 filas** (staging de atribución) |

## La fuente principal ya existe: `works_person_import`
Ese staging trae atribuciones importadas por obra, con rol y estado:

| `resolved` | `role` | filas |
|---|---|---|
| 2 | artist | 160.319 |
| 1 | composer | 145.387 |
| 1 | artist | 77.766 |
| 2 | composer | 1.985 |
| 0 | artist | 547 |

**Cobertura:** de las 175.140 obras sin compositor, **170.911 (97,6 %) tienen filas en
`works_person_import`**. Es decir, el trabajo ya está hecho: falta **promover** esas
atribuciones a `works_person_roles` (rol 1) resolviéndolas contra `persons`
(`persons_name` / `persons_aliases.person_aliases_normalized_alias`) y marcando
`works_person_import_resolved`.

> Ojo: `persons` está en `utf8mb4_general_ci` y `works` en `utf8mb4_unicode_ci`; los JOIN
> por nombre necesitan `COLLATE` explícito (MySQL da error 1267 si no).

## Plan propuesto (en capas, todo dentro de osap-storage salvo el índice)
1. **Promoción del staging (mayor impacto, ~170k obras).**
   - Para cada `works_person_import` con `role='composer'` y `resolved` en (0,1):
     resolver `works_person_import_name` → `persons_id` (nombre exacto, alias normalizado,
     o `persons_identity`), insertar en `works_person_roles` (rol 1, `order` por antigüedad)
     y marcar `works_person_import_resolved = 1`.
   - Idempotente: no duplicar si ya existe (work, person, role).
   - Los que no resuelvan persona se quedan como `candidates` para revisión (no inventar).
2. **Fallback por título (`" - Composer"`, 68.047 obras).** Extraer el sufijo y casarlo
   contra `persons` + `persons_aliases` (mismo `COLLATE`). Añade donde el staging no llegue.
3. **Fallback por el propio fichero (MusicXML).** El auditor (`script/audit_omr_titles.py`)
   ya guarda `xml_composer` del `<creator>`; para los MXL con metadato sirve como tercera
   fuente y como verificación cruzada.
4. **Autoridades externas.** El corpus **RISM local** (1,5 M de fuentes con compositor y
   signatura) permite confirmar/atribuir obras del mismo título; CPDL e IMSLP como contraste.
5. **Índice (`osap-api`).** Ya reconstruye OMR desde `works + works_person_roles +
   works_resources + work_genres`, así que **cada promoción en storage se refleja al
   reconstruir**; no hay que mantener un mapeo paralelo.

## Qué NO hacer
- No atribuir por similitud de título sin anclaje (evita fusiones falsas: el matcher ya veta
  título genérico sin número/catálogo).
- No rellenar `Anonymous`/`NA` como si fuera compositor: se tratan como "sin atribución".

## Medición de éxito
- % de obras OMR con rol 1 (objetivo: +55 pts, hasta ~99 % con staging + título + XML).
- % de fichas del índice OMR con `composer_name` no vacío/no anónimo.
