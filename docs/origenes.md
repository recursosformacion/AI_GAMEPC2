# Catálogo de Orígenes / Fuentes OSAP

> **Última actualización:** 2026-08-27  
> **Versión del contrato de proveedores:** 1.3  
> **Estado:** Fuentes registradas en la tabla `providers` de la BD operativa (dev) y como YAML en `providers/` (prod fallback).

---

## Proveedores Activos (wired = true)

| ID | Nombre | Tipo | Nivel | API / Protocolo | Formatos | Licencia predominante | Prioridad |
|----|--------|------|-------|-----------------|----------|----------------------|-----------|
| `local_library` | Biblioteca Local | Local | 1 | Filesystem | musicxml, mxl, pdf, midi | Usuario | 100 |
| `openscore` | OpenScore | GitHub | 2 | GitHub API (repos) | musicxml, mscz, pdf | CC0 / CC-BY | 90 |
| `cpdl` | ChoralWiki (CPDL) | MediaWiki | 2 | MediaWiki API | musicxml, pdf, midi | PD / CC-BY | 85 |
| `imslp` | IMSLP / Petrucci | MediaWiki | 2 | MediaWiki API (scraping) | pdf, musicxml, midi | PD / CC-BY | 80 |
| `openmusicrepository` | OMR (osap-storage) | REST | 1 | osap-storage API v1 | musicxml, pdf, midi, mei | PD / CC-BY | 75 |
| `mutopia` | Mutopia Project | Web/HTML | 2 | HTTP + FTP (scraping) | lilypond, musicxml, pdf, midi | PD / CC-BY | 70 |
| `musicbrainz` | MusicBrainz | REST | 1 | MusicBrainz API / Cover Art | — (metadatos) | PD / CC0 | 65 |
| `rism` | RISM Online | SRU/REST | 1 | RISM API / SRU | — (incipits, metadatos) | Académico | 60 |
| **`hymnary`** | **Hymnary.org** | **REST** | **1** | **REST JSON (`/api/tunes`)** | **musicxml, midi, pdf, txt** | **PD / CC-BY** | **80** |
| **`iiif`** | **IIIF Manifest (BNE, BnF, LoC, DIAMM, HathiTrust)** | **IIIF** | **2** | **IIIF Presentation API 3.0 + OAI-PMH** | **musicxml, mei, pdf, jp2, tiff** | **PD / CC-BY** | **70** |
| **`zenodo`** | **Zenodo (datasets MusicXML/MEI)** | **REST** | **1** | **REST JSON (`/api/records`)** | **musicxml, mei, mxl, xml, midi** | **CC0 / CC-BY** | **60** |

---

## Proveedores Deshabilitados / En Desarrollo (wired = false)

| ID | Nombre | Motivo |
|----|--------|--------|
| `musescore` | MuseScore.com | Requiere OAuth / API key de partner; rate limits estrictos |
| `freescores` | FreeScores.com | Sin API pública; solo scraping HTML frágil |
| `kernscores` | KernScores / humdrum | Datos en GitHub; ya cubiertos vía OpenScore |
| `musopen` | Musopen | API pública pero enfocada en grabaciones; partituras limitadas |

---

## Detalle de los 3 Nuevos Proveedores (2026-08-27)

### 1. Hymnary.org (`hymnary`)
- **URL base:** `https://hymnary.org`
- **API:** REST JSON nativa — `https://hymnary.org/api/tunes`
- **Endpoints usados:**
  - `GET /api/tunes?text={query}&page={page}&per_page={limit}&format=json` (search)
  - `GET /api/tunes/{id}?format=json` (resource)
  - `GET /api/tunes/{id}/musicxml?format=xml` (download MusicXML directo)
- **Autenticación:** Ninguna (pública)
- **Contenido:** ~1.2M himnos/melodías con MusicXML, MIDI, PDF, letras
- **Licencia:** Dominio público (obras >1923) + CC-BY (metadatos)
- **Nivel OSAP:** 1 (puro REST, sin fetcher custom)
- **Ficheros YAML:** `providers/hymnary/{provider,endpoints,mapping,resources}.yaml`

### 2. IIIF Manifest (`iiif`) — Genérico para BNE, BnF, LoC, DIAMM, HathiTrust
- **URL base:** Configurable por institución (`OSAP_IIIF_BASE_URL`)
  - BNE: `https://www.bne.es/iiif`
  - BnF (Gallica): `https://gallica.bnf.fr/iiif`
  - Library of Congress: `https://www.loc.gov/iiif`
  - DIAMM: `https://www.diamm.ac.uk/iiif`
  - HathiTrust: `https://www.hathitrust.org/iiif`
- **Protocolo:** IIIF Presentation API 3.0 + OAI-PMH (descubrimiento)
- **Endpoints usados:**
  - `GET /search?q={query}&page={page}&per_page={limit}` (search IIIF Search API / OAI-PMH)
  - `GET /manifests/{id}` (resource = manifest completo)
  - `GET /manifests/{id}/canvas/{canvas_id}/content` (download recurso individual)
- **Autenticación:** Ninguna (pública)
- **Contenido:** Decenas de miles de partituras digitalizadas (s. XVI–XX)
- **Licencia:** Dominio público (obras >70–100 años) + CC-BY (digitalizaciones)
- **Nivel OSAP:** 2 (fetcher custom `IIIFFetcher` para recorrido de manifests/canvases)
- **Ficheros YAML:** `providers/iiif/{provider,endpoints,mapping,resources}.yaml`
- **Fetcher:** `src/osap/infrastructure/providers/fetchers/iiif_fetcher.py`

### 3. Zenodo (`zenodo`) — Datasets MusicXML/MEI de investigación
- **URL base:** `https://zenodo.org`
- **API:** REST JSON — `https://zenodo.org/api/records`
- **Endpoints usados:**
  - `GET /api/records?q=musicxml+OR+mei+OR+kern&type=dataset&page={page}&size={limit}` (search)
  - `GET /api/records/{id}` (resource = record metadata + files)
  - `GET /api/records/{id}/files/{file_key}/content` (download archivo individual)
- **Autenticación:** Ninguna (pública; token opcional para rate limit mayor)
- **Contenido:** Datasets curados (ej. "Bach chorales MusicXML", "Beethoven string quartets MEI", "Choral public domain corpus")
- **Licencia:** CC0 / CC-BY / CC-BY-SA (mayoría abierta)
- **Nivel OSAP:** 1 (puro REST, sin fetcher custom)
- **Ficheros YAML:** `providers/zenodo/{provider,endpoints,mapping,resources}.yaml`

---

## Cómo Añadir / Activar un Proveedor

### En Desarrollo (BD operativa)
1. Crear YAMLs en `providers/{id}/` (source of truth).
2. Poblar tabla `providers`:
   ```sql
   INSERT INTO providers (provider_id, name, kind, base_url, wired, config, endpoints, mapping, resources, transforms)
   VALUES ('{id}', '{Nombre}', 'dynamic', '{base_url}', 1,
     '{"provider": {...}}', '{"search": {...}}', '{"work": {...}}', '{"work": {...}}', '{}');
   ```
3. Reiniciar osap-api (o recargar wiring).

### En Producción (YAML fallback)
1. Los YAMLs en `providers/{id}/` son la única fuente.
2. El wiring los carga con `load_definition(fallback_path)`.
3. No requiere BD operativa sembrada.

---

## Configuración Requerida por Proveedor

| Proveedor | Variable de entorno | Descripción |
|-----------|---------------------|-------------|
| `hymnary` | *(ninguna)* | Totalmente público |
| `iiif` | `OSAP_IIIF_BASE_URL` | Base URL de la institución IIIF (ej. `https://gallica.bnf.fr/iiif`) |
| `zenodo` | *(ninguna)* | Público; opcional `ZENODO_TOKEN` para rate limit 100 req/min |

---

## Fuentes Candidatas Futuras (Investigadas, No Implementadas)

| Fuente | Tipo | API | Licencia | Bloqueador |
|--------|------|-----|----------|------------|
| Sheet Music Direct | Comercial (Hal Leonard) | API privada (partners) | Copyright / DRM | Requiere contrato comercial |
| FullPartituras | Comunitario/Comercial | Sin API pública | Mezcla copyright | Scraping frágil + legal |
| MiPartitura | Comunitario/Comercial | Sin API pública | Mezcla copyright | Scraping frágil + legal |
| BNE (directo) | Institucional | IIIF (ya cubierto por `iiif`) | PD / CC-BY | — |
| BnF Gallica (directo) | Institucional | IIIF (ya cubierto por `iiif`) | PD / CC-BY | — |
| Library of Congress | Institucional | IIIF (ya cubierto por `iiif`) | PD / US Gov | — |
| HathiTrust | Archivo masivo | IIIF + API | PD variable | Requiere filtro PD |
| Internet Archive | Archivo masivo | IIIF + API | PD variable | Requiere filtro PD |
| RISM (extendido) | Musicología | API REST (parcial) | Académico | Ya implementado base |
| DOI/Figshare | Repositorios datos | REST + OAI-PMH | CC0 / CC-BY | Similar a Zenodo |

---

## Notas de Arquitectura

- **Contrato v1.3:** Todos los proveedores devuelven `ProviderWork` (Identity + Metadata + Statistics + Resources).
- **Level 1:** REST puro → JSON directo → mapping YAML → `ProviderWork`.
- **Level 2:** Protocolo no-REST (MediaWiki, IIIF, GitHub) → fetcher custom → JSON normalizado → mismo mapping.
- **Persistencia:** En dev, la BD operativa (`osap-api` DB, tabla `providers`) tiene precedencia sobre YAML. En prod, solo YAML.
- **Registro:** `wiring.py` → `RemoteCatalogProvider(definition, fetcher?)` → `CatalogManager`.
- **Índice híbrido:** `IndexCatalogProvider` consulta `index_works`/`index_representations` primero; providers indexados se omiten en vivo.

---

## Comandos Útiles

```bash
# Listar providers registrados en BD (dev)
python -c "
from osap.infrastructure.state.op_store import build_op_store
store = build_op_store('127.0.0.1', 'osap2027', '2027osapdb', 'osap-api')
for p in store.list_providers():
    print(f'{p[\"provider_id\"]}: {p[\"name\"]} wired={p[\"wired\"]}')
"

# Probar búsqueda Hymnary
curl "https://hymnary.org/api/tunes?text=amazing%20grace&per_page=5&format=json"

# Probar búsqueda Zenodo
curl "https://zenodo.org/api/records?q=musicxml&type=dataset&size=5"

# Probar IIIF (BnF Gallica)
curl "https://gallica.bnf.fr/iiif/search?q=bach&page=1&per_page=5"
```

---

*Documento generado automáticamente. Para añadir fuentes, editar YAMLs en `providers/` y poblar BD operativa.*