# Personas: reglas de limpieza y re-enlace OMR (diseño)

Fecha: 2026-09-21. Dos trabajos independientes, en este orden.

## A) Re-enlace OMR↔obra (prioridad 1: es la base de todo)

### Medido
- Auditoría de 300 obras OMR abriendo su MusicXML: **241 desajustes (80 %)**.
- El emparejamiento obra↔fichero viene mal **desde el origen**: `osap-storage_v1` y
  `osap-storage` coinciden (f_v2 == f_v1), así que **no es una regresión de la v2**.
- **No hay desplazamiento constante** (probado offsets 0, ±1, ±2, ±5, ±20, ±100 → sin patrón).
- El MusicXML **no contiene el id OMR** (solo música y, a veces, `<work-title>`); ejemplo:
  obra "Ffidl Ffadl" (id 9) → fichero 632 → contenido real "Diferion Arian".

### Plan (estructural)
1. **Auditar todo el corpus OMR** con `script/audit_omr_titles.py` (una lectura de R2/CDN por
   representación) y guardar `index_representations.xml_title` / `xml_composer`.
   Ya implementado y reanudable (`xml_title IS NULL`).
2. **Re-emparejar** (storage): construir el índice inverso `xml_title → file_id` y, para cada
   obra cuyo `xml_title` no coincida, apuntar `works_resources` al fichero cuyo contenido sí
   coincide (mismo título normalizado). Determinista y reversible (guardar el mapping previo).
   - Las obras cuyo fichero **no trae metadatos** quedan marcadas como "no verificable".
3. **Reconstruir el índice** (20 min) y volver a auditar: el desajuste debe caer a ~0 en las
   verificables.
4. Solo entonces tiene sentido atribuir compositores/títulos: hoy parte de las conclusiones
   se apoyan en fichas cuyo fichero no corresponde.

Alternativa (cosmética, no recomendada como primera): renombrar cada obra con el título
interno de su fichero (auto-consistencia sin re-enlazar). Útil solo si el punto 2 no es viable.

## B) Limpieza genérica de `persons` (reglas, no casos)

Reglas efectivas y generales a aplicar en una pasada:

1. **Parseo y saneado del nombre**: quitar caracteres extraños (`:`, `!!`, `?`, `*`, `#`,
   comillas, saltos de línea, mojibake) y espacios múltiples; conservar apóstrofes y guiones
   legítimos (`O'Neill`, `Saint-Saëns`).
2. **Rellenar campos** de cada persona:
   - `persons_givenname`, `persons_familyname`, `persons_sortname`.
   - `persons_birth_year` / `persons_death_year`: extraer de **años entre paréntesis**
     (`(1815-1852)`, `(1815)`, `(*1815 †1852)`) y de sufijos `n. 1815 – m. 1852`.
3. **Nombres compuestos**: al partir por separadores (`;`, `&`, ` y `, `,`) comprobar que cada
   parte **no exista ya** como `persons_name` ni en `persons_aliases`; si existe, **reutilizar**
   esa persona (no crear duplicado); si no, crear candidata y registrar el alias original.
4. **Trazabilidad**: cualquier cambio de persona en una obra se refleja en
   `works_person_roles` (insert/replace del rol 1) y se audita en
   `works_person_roles_history` (operation, batch_id). Nunca dejar roles huérfanos.
5. **Nombres irrepresentables** (los que no se pueden mostrar: `?No 12?`, `By James Knight a
   Blindman…`, `?No 17?`):
   1. ir a su obra → su MusicXML; leer `<work-title>` y `<creator>`;
   2. si hay título → **corregir `works.works_title`**;
   3. si hay compositor → comprobar si ya existe (`persons`/`persons_aliases`):
      - si existe: re-apuntar `works_person_roles` al existente y **borrar** la persona basura;
      - si no existe: usar el registro para dar de alta el nombre correcto (con alias del
        original).
   4. Si el XML no aporta nada: dejar la persona en cuarentena (`review_reason='indescifrable'`)
      y la obra sin rol 1, para revisión manual.

### Hallazgo aparte (listado de compositores)
Buscando "MOZART" en compositores aparecen entradas que no son compositores (anónimo atribuido,
"arr.", apologie…). Causa: el rol que se pinta proviene de `works_person_roles` (incluye rol 1
asignado a arreglistas/atribuciones dudosas) y los **nombres no están limpiados**. Regla:
el listado de compositores debe exigir **rol 1 (compositor) con nombre saneado** y excluir
`anónimo/tradicional/arr./atribuido` a roles distintos (arreglista=3, etc.).
