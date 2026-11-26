# Plan de enriquecimiento de fichas (personas y obras)

Estado a 2026-11-26. Este documento es la lista de continuidad: si se retoma el trabajo
semanas después, empezar por aquí.

## Hecho

- Sesión admin propia en storage/support (8 h, sin depender del service token de 5 min).
- Limpieza de 332 personas basura (vacías o solo signos) y fusión de `'A Reel'Abraham MacIntosh`.
- Abraham MacIntosh completado por investigación web con fuentes: 1769–1807, Escocia,
  resumen y referencias (IMSLP/Highland/HMS).
- 9.304 personas ocultas revisadas con datos promovidas a visibles. Compositores visibles:
  **29.411**. Backup: `osap-storage/var/hidden_persons_promote_20261126T181436Z.json`.
- Fichas SEO de compositor: introducción catalográfica si no hay biografía, autoridad
  (`sameAs`), referencias, imagen, OpenGraph y `lastmod` en sitemap.
- Fichas SEO de obra: “Sobre la obra”, descripción de respaldo, JSON-LD con
  descripción/género/tonalidad/fuente y OpenGraph.
- `resolve_persons.py` ya no crea personas con nombres vacíos, solo signos o títulos
  entrecomillados pegados al nombre.
- Scripts nuevos en `osap-storage/scripts/`:
  - `research_person_web.py` — fuentes + Groq con evidencias.
  - `report_hidden_persons.py` — clasificación, promoción y fusión exacta.
  - `enrich_works_imslp.py` — metadatos de obras desde el wikitext de IMSLP.
- Piloto IMSLP (2.000 obras, 81 s): 1.205 años, 1.907 instrumentaciones, 147 opus,
  1.969 épocas.
- Lote IMSLP de 20.000 obras completado el 2026-11-26 (11 min):
  13.116 años, 18.386 instrumentaciones, 1.464 opus, 300 tonalidades, 19.707 épocas.
  Cursor actual: **332.505**. Quedan ~244.546 obras IMSLP candidatas (~12 lotes).

## Siguiente paso técnico (orden obligatorio)

### 1. Terminar el barrido IMSLP

- [x] Primer lote de 20.000 completado (2026-11-26 18:31).
- [ ] Repetir lotes hasta agotar el cursor (hay uno de 20.000 en curso):
      `enrich_works_imslp.py --limit 20000 --sleep 0.4 --apply --allow-prod`
- [ ] Cursor: `osap-storage/var/imslp_works_cursor.txt`
- [ ] Revisar informes: `osap-storage/var/imslp_works_*.json`
- Criterio de aceptación: >90% de las 266k obras IMSLP con instrumentación y época;
      años cuando IMSLP los declare.

### 2. Extender el índice público de obras (bloqueante de SEO)

Problema: la ficha SEO lee de `index_works`, que **no** lleva descripción, géneros, opus,
tonalidad, fuente, licencia ni época. No se puede resolver consultando storage por id:
**los ids de `index_works` y `works` no coinciden**.

- [ ] Añadir a `index_works`: `description`, `genres`, `opus`, `musical_key`,
      `source_url`, `license`, `public_domain`, `epoch_title`, `duration`, `language`,
      `attribution_type`.
- [ ] Extender `script/index_works.py` para leer esos campos de storage al construir el
      registro e insertarlos/actualizarlos.
- [ ] Extender `IndexCatalogProvider.get_work_with_representations` para devolverlos.
- [ ] Reindexar (`osap-index-full`) y verificar una obra con descripción/género/fuente.
- Criterio de aceptación: una ficha de obra muestra “Sobre la obra” con texto real,
      género, instrumentación, época y enlace a IMSLP/CPDL, y el JSON-LD lleva
      `description`, `genre`, `musicalKey` y `sameAs`.

### 3. CPDL y PDMX

- [ ] `enrich_works_cpdl.py`: mismo patrón que IMSLP para las 57k obras CPDL.
- [ ] PDMX: localizar el dataset/XML original de las 254k obras y extraer
      título/creador/año/instrumentos; no hay URL de origen en `works`.
- [ ] Ejecutar en lotes con cursor y dry-run antes de aplicar.

### 4. Personas: investigación dirigida

No ejecutar `research_person_web.py` sobre las 36k: no es rentable (bloqueos, coste,
homónimos). Priorizar:

- [ ] Top 1.000–2.000 personas por número de obras sin fechas/nacionalidad/resumen.
- [ ] Personas con ID externo (VIAF/IMSLP/Wikidata) y campos vacíos: structured primero.
- [ ] Umbral: confianza ≥0,6 + al menos una fuente autoritativa; solo rellenar vacíos.
- [ ] Revisar muestras de `var/` antes de ampliar.
- Comando:
      `research_person_web.py --hidden-with-works --min-works 100 --limit 50`

### 5. Limpieza pendiente de personas ocultas

- [ ] 549 `parse_junk` (títulos/fechas pegados al nombre) → normalizar o fusionar.
- [ ] 50 placeholders (Anonymous/Trad/Various/Composer) → canónicos de anónimo/tradicional.
- [ ] 146 `duplicate_fuzzy` → revisión manual; no fusionar por similitud sin fechas/IDs.
- [ ] 26.699 ocultas con obras restantes: revisar las que tengan datos antes de promover.
- Informe: `report_hidden_persons.py --csv /tmp/hidden_persons.csv`.

### 6. Calidad y SEO continuo

- [x] El email diario de incidencias incluye un resumen “TRABAJO RECIENTE”
      (IMSLP acumulado/cursor/candidatas y personas visibles/promoción) y ya no marca
      `osap-ai-enrich` como caído por ser un oneshot.
- [ ] Informe semanal: personas ocultas con obras, obras sin compositor visible,
      sin año y sin instrumentación.
- [ ] Tras cada reindexación: purgar Cloudflare y reenviar sitemap.
- [ ] En Search Console, solicitar indexación de las 50 fichas con más obras/tráfico.
- [ ] Revisar “Rastreada: actualmente sin indexar” a 2–4 semanas.

## Comandos de referencia

```bash
# Producción
cd /home/ocw/openmusicrepository.com/osap-storage
OSAP_CONFIG=$PWD/config.yaml .venv/bin/python scripts/enrich_works_imslp.py --limit 20000 --sleep 0.4 --apply --allow-prod
OSAP_CONFIG=$PWD/config.yaml .venv/bin/python scripts/report_hidden_persons.py --promote
OSAP_CONFIG=$PWD/config.yaml .venv/bin/python scripts/research_person_web.py --person-id <uuid>
```

## Notas

- `research_person_web.py` prueba variantes Mac/Mc (MacIntosh/Mackintosh/McIntosh).
- Gemini está sin cuota; la extracción usa Groq `openai/gpt-oss-120b`.
- DuckDuckGo puede devolver 202/challenge; IMSLP/Wikipedia/Wikidata/Highland funcionan.
- No promover placeholders, ensembles ni duplicados fuzzy sin revisión.
