# Compositores que faltan en OMR — cómo conseguirlos

Medido el 2026-09-20. **Auditoría autoritativa**: `osap-storage/scripts/analyze_missing_composers.py`
(read-only) sobre la BD nueva (`osap-storage`).

## Situación (dato corregido)
| Dato | Valor |
|---|---|
| Obras en `works` | 310.455 |
| **Sin compositor** (sin rol 1 en `works_person_roles`) | **175.140** (56%) |
| … con patrón de anonimato/tradicional | 5.980 |

### Desglose por evidencia interna (auditor de storage)
| Categoría | Obras | ¿Recuperable? |
|---|---|---|
| `ninguna_evidencia` | **135.762** | No por metadatos: corpus folk PDMX sin atribución en ninguna parte |
| `titulo_contexto` | 19.608 | **Sí**: el título trae contexto/compositor |
| `catalogo_titulo_hermana` | 9.026 | **Sí, seguro**: obra hermana con el mismo catálogo tiene compositor |
| `anonimo_esperado` | 5.980 | Correcto como anónimo/tradicional |
| `varias_posibilidades` | 4.675 | Requiere desambiguación |
| `metadatos` / `otra_relacion` / `catalogo_hermano` | 65 / 22 / 2 | Marginal |

## La tubería de staging YA se ejecutó
`works_person_import` (386.004 filas) ya está procesado:
- `link_works_person_import.py` y `populate_persons_from_import.py` seleccionan
  `works_person_import_resolved = 0` y **no queda ninguna fila de rol `composer`** en ese estado.
- De las filas `resolved=1` cuyo trabajo sigue sin rol 1 (10.252), los nombres son
  **ruido o anónimos** ("anon.", "Traditional", mojibake de PDMX) → no aportan.

**Conclusión:** lo recuperable por el staging ya está materializado. El hueco restante es
mayoritariamente folk sin atribución, y hay **~28.600 obras** con evidencia aprovechable
(9.026 por catálogo hermano + 19.608 por contexto de título).

## Plan por orden de seguridad y valor
1. **Hermana por catálogo (9.028).** Copiar rol 1 desde otra obra con el mismo
   `works_catalogue` (mismo título normalizado o catálogo idéntico). Regla determinista, sin
   inventar: si el catálogo coincide y hay **un único** compositor entre las hermanas, se asigna.
2. **Contexto de título (19.608).** Extraer el nombre embebido (`"Título - Compositor"`,
   68.047 títulos con `" - "`) y casarlo contra `persons` + `persons_aliases`
   (`COLLATE utf8mb4_unicode_ci`, hay colación distinta). Solo con match único.
3. **`<creator>` del MusicXML.** El auditor de osap-api
   (`script/audit_omr_titles.py`) ya guarda `xml_composer` al abrir cada MXL: tercera fuente
   y verificación cruzada para las que tengan metadato interno.
4. **RISM local (1,5 M fuentes).** `scripts/propose_rism_composers.py` /
   `apply_rism_attributions.py` (ya existen) para confirmar/atribuir por título y signatura.
5. **`varias_posibilidades` (4.675).** Dejar propuestas para revisión; no auto-asignar.

## Índice (osap-api)
Ya reconstruye OMR desde `works` + `works_person_roles` + `works_resources` + `work_genres`,
así que cada promoción en storage se refleja al reconstruir; no hay mapeo paralelo. Los
anónimos se quedan sin `composer_name` (no se fuerza `Anonymous`).

## Qué NO hacer
- No atribuir por similitud de título sin anclaje (riesgo de fusiones falsas).
- No rellenar `Anonymous`/`NA` como compositor; se tratan como "sin atribución".

