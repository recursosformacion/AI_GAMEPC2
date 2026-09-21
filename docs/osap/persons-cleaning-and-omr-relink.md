# Personas: reglas de limpieza y re-enlace OMR (diseño)

Fecha: 2026-09-21. Dos trabajos independientes, en este orden.

## A) OMR: RETRACTADO — producción está BIEN; el fallo era del entorno local

### Corrección (2026-09-21, verificado)
Mi auditoría daba 80 % de desajustes **midiendo el entorno local**, y concluí mal que el
enlace obra↔fichero venía roto del origen. **Es falso**: en producción el emparejamiento es
correcto (el `<work-title>` del fichero coincide con el título anunciado; probado con
"Ffidl Ffadl", "Ave Verum", "Sussex Carol").

### Causa real (dev): `/api/download/{id}` resuelve ids **ambiguos**
En el modelo nuevo, el handler de storage
(`api/routes/provider.py` → `/api/download/{resource_id}`) resuelve el id contra
**representaciones**, **archive entries** y **ficheros**. Con ids numéricos colisionan:

```
GET /api/download/632      → 302 /api/v1/files/1255/content   (entry 632 → file 1255)
GET /api/v1/files/242077/content → "FfidFfadl" (correcto)
GET /api/v1/files/242700/content → "Garech's Wedding"
GET /api/v1/files/1255/content   → "Diferion Arian"
```
Es decir: el índice guarda `download_url = {storage}/api/download/{file_id}`, pero en local
ese id también existe como *archive entry* (u otra entidad) y storage sirve **otro fichero**.
En producción el endpoint mantiene la semántica antigua (id = fichero) y por eso funciona.

### Acción
1. **storage (su repo)**: desambiguar `/api/download/{id}` — p. ej., resolver primero
   `files` (con `available`) y/o exigir el prefijo `res-` que ya usa `_resource_id()`, o
   devolver 409 si el id existe en varias entidades.
2. **Local**: no volver a auditar títulos hasta arreglarlo (los resultados no son válidos).
3. La auditoría completa de OMR queda **cancelada** (no hay nada que re-enlazar en el catálogo).

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
