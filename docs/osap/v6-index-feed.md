# Feed de índice V6 y estabilidad de URLs

`osap-storage` expone `GET /api/v6/index/works?cursor=&limit=` como feed canónico
para reconstruir el índice de OSAP sin cambiar la identidad pública de las obras.

## Contrato

```json
{
  "items": [
    {
      "work_id": "index-1",
      "title": "I shall be no stranger there",
      "song_name": "I shall be no stranger there",
      "catalogue": "K. 525",
      "composer": "William James Kirkpatrick",
      "resources": [
        {"id": 131072, "kind": "score", "source_system": "legacy",
         "external_id": null, "external_url": null, "file_ids": [624]}
      ]
    }
  ],
  "next_cursor": 1
}
```

- `work_id` ya es `index-<works.id>`; el consumidor **no debe** recalcularlo.
- El slug se deriva del título con `work_canonical_slug(works_title)`.
- `limit` máximo 500; `next_cursor` es el último id de la página.

## Invariante Google

- No se modifican `works.id` ni `works_title` durante el mapeo V6.
- Cambiar un título o un slug exige tabla de correspondencia `id_anterior → id_nuevo`
  y un 301 para cada URL antigua antes de reindexar.
- Los slugs históricos del sitemap con el **mismo `work_id`** pueden diferir del
  canónico actual; deben seguir devolviendo 200 y no se consideran un fallo del feed.

## Previsualización

```powershell
python script/v6_index_preview.py --feed var/v6-feed.json --sitemap var/works-1.xml
python script/v6_index_preview.py --feed-url http://127.0.0.1:8000/api/v6/index/works --sitemap var/works-1.xml
```

No escribe el índice. Compara los documentos del feed con las URLs del sitemap y
distingue coincidencia canónica, slug histórico, obra ausente y URL mal formada.

Resultado de la muestra real (2026-11-12, 500 URLs): 500 documentos, 0 ausentes,
166 coincidencias canónicas, 334 slugs históricos (200) y 0 malformadas.
## Deriva de títulos entre índice actual y feed V6

Comparación de 500 Works presentes en `index_works`:

- 275 títulos distintos entre el índice actual y `works_title` de Storage.
- 246 slugs distintos.
- Ejemplos: `Humours of Lissadell` vs `The Humours Of Lissadell`; `Allegro. RDO.35` vs
  `Allegro`; `Little Bag of Potatoes` vs `The Little Bag of Potatoes`.
- Causa: el índice conserva títulos de una construcción anterior; Storage tiene títulos
  más limpios. Es deriva previa a V6, no del mapeo.

**Regla de corte**: para Works ya indexadas se conservan `public_id`, título y slug del
índice actual; el feed V6 aporta Resources/Files y sirve para Works nuevas. La limpieza de
títulos se hará con tabla de correspondencia + 301, nunca sobrescribiendo el índice en el
corte.

`script/v6_index_preview.py --index --stage-db ...` escribe el staging con
`title_source=index` para los IDs existentes (500/500 en la muestra) y deja constancia de
la deriva.
