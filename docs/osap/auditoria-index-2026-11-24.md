# Auditoría de asociación de representaciones del índice

**Fecha:** 2026-11-24.  
**Estado:** incidencia confirmada en una ficha pública; causa de los datos persistidos pendiente de traza SQL de solo lectura.  
**Producción:** no se han ejecutado escrituras, reconstrucciones ni migraciones.

## 1. Caso reproducible

La ficha pública consultada para **Violin Concerto No.3 in B-flat major**, de Dieudonné-Pascal Pieltain, muestra dos representaciones IMSLP:

- Violin Concerto No.3 in B-flat major.
- Violin Concerto No.1 in F major.

IMSLP identifica la primera como **IDP 3** y la segunda como **IDP 2**. Son obras diferentes del mismo compositor; no son dos ediciones de una misma obra.

La ficha pública inspeccionada fue la ruta heredada `/obras/index-533295`, que actualmente muestra el identificador de índice `index-376284cace625701f1ef`. La discrepancia entre la ruta solicitada y el ID mostrado también debe conservarse en la investigación de alias/redirects; no se debe corregir a mano sin revisar el mapa de IDs.

## 2. Recorrido de código comprobado

1. `SeoMixin.seo_work()` obtiene la ficha mediante `IndexCatalogProvider.get_work_with_representations()`.
2. `get_work_with_representations()` lee `index_works` por `public_id` y recupera las filas de `index_representations` con `WHERE work_id = %s`.
3. La ficha muestra `title_provider` (o `xml_title`) de esas filas. No vuelve a validar que el título de cada representación sea compatible con el número de obra de la fila padre.

Por tanto, la asociación incorrecta ya está presente en el índice persistido o en la fuente que lo alimentó; la plantilla HTML no inventa el título de la segunda representación.

## 3. Segundo problema detectado y corregido en código

El enriquecimiento de resultados de búsqueda tenía una ruta adicional de asociación:

- `MetadataNormalizer.comparison_title()` elimina número, catálogo y tonalidad para comparar ediciones.
- `_title_core_match()` comparaba únicamente la superposición de tokens.
- `_focused_representations()` podía considerar equivalentes dos obras numeradas distintas si compartían un núcleo genérico, por ejemplo “Violin Concerto”.

Se ha corregido para que, cuando ambos títulos declaran un número de obra, los números deban coincidir. Se han añadido pruebas para No.1 frente a No.3, para conservar ediciones del mismo número y para no alterar la coincidencia de títulos sin numeración.

Commits:
- `44a852b` — rechazo de números incompatibles en el helper.
- `14f736d` — aplicación de la referencia original en el enriquecimiento.
- `8928d2d` — pruebas de regresión.

**Pruebas:** se han añadido tres pruebas nuevas, pero no se han ejecutado en el entorno de esta revisión. El estado de CI del commit no devolvió resultados; hay que ejecutar la suite local antes de considerar validada la corrección.

Esta corrección evita nuevas asociaciones de este tipo en el recorrido de enriquecimiento, pero **no repara las filas que ya están almacenadas en `index_representations`**.

## 4. Diagnóstico de solo lectura disponible

Se ha añadido `script/audit_index_associations.py`. Consulta una única Work, abre una transacción `READ ONLY`, compara los números explícitos del título padre y de cada representación y no contiene ninguna operación de escritura.

En desarrollo, con el `osap.toml` correcto:

```powershell
python script/audit_index_associations.py --confirm-database <nombre-exacto-de-bd>
```

Para producción requiere además `--allow-production-read`, y solo debe utilizarse tras autorizar expresamente esa consulta. El argumento `--confirm-database` debe coincidir exactamente con la base configurada. El script no muestra credenciales ni las modifica.

## 5. Investigación de datos pendiente

Antes de escribir en ninguna base de datos:

1. Consultar en solo lectura la fila `index_works` del ID actual y todas sus `index_representations`.
2. Obtener los `source_rep_id`, `resource_id`, `title_provider`, `xml_title`, `catalogue`, `download_url` y proveedor de cada fila.
3. Comparar los IDs de origen y catálogos IMSLP (IDP 2 / IDP 3) con la fuente original.
4. Rastrear si la asociación se creó en `script/index_works.py`, en una ejecución anterior del indexador o en una fusión posterior.
5. Ejecutar un rebuild seguro en una base de desarrollo y comparar obras, representaciones, fuentes, IDs públicos y aliases.
6. Proponer una reparación con backup, transacción, invariantes y rollback. No aplicarla en producción sin revisión y autorización explícitas.

No borrar la representación ni separar la Work basándose solo en el título mostrado: primero hay que confirmar la identidad nativa y la fila exacta.

## 5. Criterio de aceptación

- La ficha de IDP 3 solo muestra materiales que pertenecen a IDP 3 o que se han verificado como ediciones/arreglos de esa misma obra.
- IDP 2 aparece en su propia Work.
- La búsqueda no vuelve a unir obras con números explícitos distintos.
- Los IDs públicos antiguos continúan resolviendo al destino correcto, sin colisiones ni redirecciones a obras ajenas.
- El rebuild y la reparación son idempotentes y no pierden representaciones legítimas.
