# Enriquecimiento multifuente de personas y obras (OSAP)

Estado: **fase 1 implementada** (conector Wikidata + staging + CLI + IIIF como fuente); fases 2–5 propuestas. Fecha: 2026-11-19.

## 1. Objetivo

Dada una **persona** o una **obra**, completar el máximo de campos con evidencia de
cualquier fuente fiable: Wikidata/SPARQL, RISM, IIIF de bibliotecas, catálogos (IMSLP,
CPDL, VIAF/ISNI/GND/BnF/BNE/MusicBrainz) e IA (para normalizar/desambiguar, nunca como
verdad sin evidencia). Nunca inventar; nunca sobreescribir un dato verificado.

## 2. Principios

1. **Evidencia y procedencia**: cada valor guarda `fuente`, `url_evidencia`, `confianza`,
   `licencia` y `fecha`. La ficha puede mostrar de dónde sale cada dato.
2. **Rellenar, no pisar**: solo se escribe un campo vacío o de menor confianza. Los
   conflictos entre fuentes van a una **cola de revisión**, no se resuelven en silencio.
3. **Idempotencia** y **reanudación**: cada conector es re-ejecutable sin duplicar.
4. **Rate-limit y caché** por fuente; respetar términos/licencias de cada API.
5. **IA con freno**: la IA propone; para escribir exige corroboración (otra fuente) o
   revisión humana.

## 3. Fuentes y estado verificado (2026-11-19)

| Fuente | Tipo | Patrón base | Prueba | Estado |
|---|---|---|---|---|
| Wikidata Query (SPARQL) | SPARQL | `https://query.wikidata.org/sparql?query=...&format=json` | 200 `sparql-results+json` | **OK** |
| Wikidata EntityData | JSON | `https://www.wikidata.org/wiki/Special:EntityData/{QID}.json` | 200 JSON (Q1339) | **OK** |
| RISM Online | JSON-LD / MARCXML | `https://rism.online/{sources\|people}/{id}` con `Accept: application/ld+json` o `application/marcxml+xml` | 200 (JSON-LD/MARCXML) | **OK** |
| BSB München | IIIF v2 | `https://api.digitale-sammlungen.de/iiif/presentation/v2/{bsb}/manifest` | 200 manifest (bsb00000001) | **OK** |
| e-codices (CH) | IIIF v2 | `https://www.e-codices.unifr.ch/metadata/iiif/{id}/manifest.json` | 200 manifest (csg-0001) | **OK** |
| Gallica (BnF) | IIIF | `https://gallica.bnf.fr/iiif/ark:/12148/{ark}/manifest.json` | 403 con ark inválido | Requiere **ark real**; posible WAF |
| BNE (Hispana/BDH) | IIIF | `https://bdh-rd.bne.es/iiif/{id}/manifest` | 403 en base | Requiere **id válido** + cabeceras |
| Bodleian (Oxford) | IIIF | `https://iiif.bodleian.ox.ac.uk/iiif/manifest/{uuid}.json` (o `/metadata/manifest/…`) | 400 en base | Requiere **uuid real**; confirmar patrón |
| British Library | IIIF | `https://api.bl.uk/metadata/iiif/{id}/manifest` | conexión fallida | **No disponible** (revisar si retirado) |

Correcciones a las direcciones aportadas: `gallica.../iiif/ark:/1` está truncada; `bne.es/iiif/bimo]` tiene un `]` espurio y falta el id; el bloque de Bodleian/e-codices venía pegado y con placeholders (`[ID_OBRA]`, `[ID_CODICE]`).

Nota: Gallica/BNE/Bodleian necesitan un **identificador real** del ítem; su base no es un
manifiesto. Los conectores deben obtener ese id (búsqueda de la institución o Wikidata).

## 4. Contrato de conector

```python
class EnrichmentSource(Protocol):
    id: str
    def lookup_person(self, person: PersonQuery) -> list[PersonCandidate]: ...
    def lookup_work(self, work: WorkQuery) -> list[WorkCandidate]: ...
```

`PersonCandidate`/`WorkCandidate`: campos propuestos + `source`, `evidence_url`,
`confidence` (0–1), `license`, `fetched_at`. Los conectores no escriben en las tablas de
dominio; solo producen candidatos.

## 5. Persistencia (staging) y aplicación

Tabla `enrichment_candidates`:
`entity_type(person|work)`, `entity_id`, `field`, `value`, `source`, `evidence_url`,
`confidence`, `license`, `fetched_at`, `status(new|accepted|rejected|conflict)`.

Aplicación (`apply_enrichment.py`): por campo, escribe solo si el destino está vacío o el
candidato tiene mayor confianza y `status=accepted`; registra procedencia. Conflictos →
`status=conflict` para revisión.

## 6. Orquestación

- CLI `enrich_entity.py --person ID | --work ID` (vertical, con evidencia).
- Cola de trabajo: entidades con campos vacíos (p. ej. `works_year IS NULL`,
  `instrumentation IS NULL`, `person_id IS NULL`).
- Timer (systemd) que procesa lotes pequeños, con backoff y rate-limit por fuente.
- Caché de respuestas por URL/hash para no repetir llamadas.
- Integración con `merge_service`/`MergeProvenance`, `canonical_metadata`, `index_works` y
  las fichas (mostrar fuente por campo).

## 7. Prioridad de fuentes por campo

- **Persona**: Wikidata (fechas, aliases, nacionalidad, ISNI/VIAF/GND/LCCN/BnF/BNE/MB),
  VIAF/ISNI, RISM persons, MusicBrainz.
- **Obra**: Wikidata (compositor P86, fecha P577, tonalidad P826, instrumentación P870,
  catálogo), RISM (título uniforme, incipits, fecha/medio vía MARCXML 240/260), IMSLP/CPDL,
  IIIF (manuscrito: fecha, signatura, compositor, incipit), IA (normalización/idiomas).

## 8. Plan por fases

1. **Wikidata** (mayor ROI, ya verificado): conector SPARQL + EntityData → rellenar fechas,
   identificadores externos, compositor/fecha/tonalidad/instrumentación de obras.
2. **RISM**: usar el corpus ya importado (`rism_sources`/`rism_persons`) y, si falta,
   content-negotiation MARCXML por fuente para año/medio.
3. **IIIF**: empezar por BSB y e-codices (verificados); Gallica/BNE/Bodleian cuando se
   confirme el patrón/ID; BL pendiente de disponibilidad.
4. **IA**: normalización/desambiguación con corroboración; cola de revisión.
5. **Scheduler + UI de revisión + procedencia visible** en fichas.

## 9. Riesgos

- Licencias/ToS por institución (IIIF suele ser consulta de metadatos; el contenido puede
  tener restricciones). Respetar `robots`/rate-limit y no redistribuir imágenes sin licencia.
- Calidad: no todos los registros RISM/IIIF son del mismo repertorio ni nivel; exigir
  confianza y evidencia.
- Coste: SPARQL y APIs externas; cachear y procesar por prioridad.
