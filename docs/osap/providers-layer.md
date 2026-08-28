# Capa Provider — Arquitectura (Provider API v1.3)

> Documenta la nueva capa de adaptación de proveedores. Todos los proveedores devuelven
> el mismo contrato (`ProviderWork`); OSAP-API es el único que lo transforma al modelo
> interno. El núcleo (Canonicalizer, Matcher, Ranking, Work Resolution, Relationships,
> Knowledge Hub) nunca conoce cómo responde un proveedor.

> **Estado actual (2026-08-27):** las definiciones de proveedores viven en la **BD de osap-api**
> (tabla `providers`, cargadas en `wiring.py` vía `_provider_definition`). Los directorios
> `providers/{id}/` YAML son la **plantilla de origen** que se importó; la BD es la fuente
> de verdad. El `endpoints.yaml` de IMSLP (API.ISCR.php) es la definición Nivel 1 de
> reserva: **la búsqueda real de IMSLP la hace el `MediaWikiFetcher`** (`api.php?action=query
> &list=search`, índice completo, límite configurable), no `API.ISCR.php`.
>
> **Nuevos proveedores añadidos 2026-08-27:** `hymnary` (Hymnary.org, Nivel 1 REST), `iiif`
> (IIIF Manifest genérico para BNE/BnF/LoC/DIAMM/HathiTrust, Nivel 2 con `IIIFFetcher`),
> `zenodo` (Zenodo datasets MusicXML/MEI, Nivel 1 REST).
>
> **Modelo en BD (2026-08):** cada YAML del proveedor va a **su propia columna** en
> `providers` — `endpoints`, `mapping`, `resources`, `transforms` (más `config` monolítico
> por compatibilidad) — evitando duplicar datos en un único JSON. La **descripción**
> multi-idioma se guarda en `description` como JSON `{es, ca, fr, en, de}`; `GET
> /api/v1/providers` la expone localizada y la pantalla de administración la edita por
> fichas de idioma.

> **Búsqueda (2026-08):** `POST /api/v1/searches` es **asíncrono**: devuelve el recurso en
> `status=running` con `progress` (0..100) y completa en un hilo en background; `GET
> /api/v1/searches/{id}` devuelve progreso y resultados parciales. Las búsquedas repetidas
> se sirven desde una **cache local** (firma normalizada de la petición).

## Flujo completo

```
Provider
   │
   ▼
HTTP (ProviderHttpClient)
   │
   ▼
GenericProviderAdapter
   │   (aplica request mapping + response mapping)
   ▼
ProviderWork   (Identity · Metadata · Statistics · Resources)
   │
   ▼
ProviderAdapter (RemoteCatalogProvider → CandidateRepresentation)
   │
   ▼
Canonicalizer
   │
   ▼
Matcher
   │
   ▼
Ranking
   │
   ▼
Work Resolution
   │
   ▼
Relationships
   │
   ▼
Knowledge Hub
```

## Separación de responsabilidades

- **osap-storage** es el propietario de Works, Metadata, Representations, Statistics,
  URLs de descarga, CDN, tokens, buckets y hashes. Lo expone únicamente vía Provider API.
- **osap-api** es responsable exclusivamente de: resolver obras, fusionar proveedores,
  Matching Works, Work Resolution, Relationships, Ranking y Knowledge Hub. **Nunca**
  contiene lógica de almacenamiento, nunca construye URLs, nunca accede al CDN y nunca
  lee JSON de MuseScore.

## Estructura

```
src/osap/infrastructure/providers/
├── contracts.py               # ProviderWork, ProviderIdentity, ProviderMetadata,
│                              #   ProviderStatistics, ProviderResource, ProviderLinks
├── adapters/
│   └── generic_provider_adapter.py   # GenericProviderAdapter + ProviderHttpClient
│                                     #   + ProviderFetcher + load_definition
├── fetchers/
│   ├── github_fetcher.py      # OpenScore (Nivel 2)
│   ├── iiif_fetcher.py        # IIIF Manifest BNE/BnF/LoC (Nivel 2)
│   ├── mediawiki_fetcher.py   # IMSLP (Nivel 2)
│   └── ...
└── (definiciones por proveedor fuera del paquete, p. ej. providers/{omr,imslp,openscore}/)
    ├── provider.yaml          # id, name, base_url, authentication, protocol
    ├── endpoints.yaml         # bloques endpoint: lookup, search, resource, download
    ├── mapping.yaml           # bloque `work:` (target plano -> ruta del proveedor)
    ├── resources.yaml         # bloque `work:` con array/fields/links de recursos
    └── transforms.yaml        # (opcional) transformaciones de campos durante el mapping
```

## Definición declarativa

Cada proveedor es un directorio de ficheros YAML (sin código):

```yaml
# endpoints.yaml
lookup:   { method: GET, path: /api/lookup }        # autocompletado / búsqueda ligera
search:   { method: GET, path: /api/search }        # proveedor de Works completas
resource: { method: GET, path: /api/resource/{id} } # acceso directo a una Work conocida
download: { method: GET, path: /api/download/{resource_id} }

# request mapping (opcional): campo OSAP -> parámetro del proveedor
request_mapping:
  query: q
  composer: composer
  limit: per_page
```

```yaml
# mapping.yaml
# target (plano) -> ruta (punto) dentro de la Work devuelta por /api/search
work:
  id: work.id
  title: work.title
  composer: work.composer
  catalogue: work.catalogue
  subtitle: metadata.subtitle
  ...
  resources: resources

# por cada recurso dentro de `resources`
resource:
  id: id
  format: format
  links.download: links.download
  ...
```

Añadir un proveedor nuevo = crear un directorio de definición con: URL, endpoints,
request mapping y response mapping. **Sin modificar el núcleo.**

## Transformaciones de campos (`transforms.yaml`)

Si durante el mapping hay que **modificar el contenido de un campo** (limpiar un
compositor, normalizar un formato, aplicar una regex…), no hace falta código: se crea
un fichero `transforms.yaml` en la carpeta del proveedor. Se aplica a los campos **ya
mapeados**, en el orden declarado, con dos secciones: `fields` (Work) y `resources`
(recurso).

```yaml
fields:
  composer:
    - type: strip_parenthetical   # "W.A. Mozart (1756-1791)" -> "W.A. Mozart"
    - type: trim
  title:
    - type: trim
resources:
  format:
    - type: lower
```

Ops disponibles: `trim`, `lower`, `upper`, `empty_to_null` (""/"None" -> null),
`strip_parenthetical`, y `{type: regex, pattern: ..., replace: ...}`. El fichero es
opcional; si no existe, el mapping se aplica tal cual.

## Contrato v1.3: search devuelve Works completas

El pipeline de resolución usa **únicamente** `GET /api/search`, que devuelve en una sola
llamada una colección de Works completas (Identity + Metadata + Statistics + Resources).

```
search (1 llamada HTTP)
   ↓
Work[] completas
   ↓
work_mapping  (aplica el bloque `work`)
   ↓
ProviderWork[]
   ↓
Canonicalizer · Matcher · Ranking · Work Resolution
```

- **Queda prohibido el patrón Search → Resource(id)**: generar N+1 llamadas durante la
  resolución está fuera del contrato.
- `GET /api/lookup` es solo para autocompletado y búsquedas ligeras (id, title, composer,
  catalogue, confidence). Nunca entra en Matching/Ranking/Resolution.
- `GET /api/resource/{id}` es un servicio adicional de acceso directo a una Work ya
  conocida (compartir enlaces, abrir una obra, uso externo). No forma parte del pipeline.

## Arquitectura de 3 niveles

```
                    Provider
                       │
        ┌──────────────┴──────────────┐
        │                             │
Generic Adapter (N1)         Custom Adapter (N2)
        │                             │
        └─────────────┬───────────────┘
                      │
              JSON normalizado
                      │
                Mapping YAML
                      │
                 ProviderWork
                      │
             Canonicalizer · Matcher · Work Resolution
```

- **Nivel 1 — Declarativo (100% YAML):** proveedores REST que implementan el contrato
  v1.3 (osap-storage, etc.). `GenericProviderAdapter` + definición YAML. Sin código.
- **Nivel 2 — Adaptador ligero (`ProviderFetcher`):** la API es distinta (MediaWiki de
  IMSLP, GitHub de OpenScore). El fetcher solo se ocupa de autenticación, URLs, anti-bot
  y pequeñas transformaciones, y entrega un **JSON normalizado** que pasa por **el mismo
  mapping YAML**. ~95% del código común.
- **Nivel 3 — Proveedores especiales:** no hay API consultable (Local, Filesystem, CSV,
  ZIP, USB). Mantienen un adapter propio. No se fuerzan a parecer REST.

## GenericProviderAdapter

- Lee la `ProviderDefinition`.
- Nivel 1: aplica el **request mapping** (OSAP → proveedor) y llama a `/api/search`.
- Nivel 2: delega en el `ProviderFetcher`, que devuelve JSON normalizado del contrato.
- Mapea **cada Work devuelta directamente** a `ProviderWork` (no hay N+1 ni `resource(id)`).
- `lookup()` y `resource(id)` existen como servicios opcionales fuera del pipeline.
- **Nunca** construye URLs, ni usa `relative_path`, `hash` ni `source_url`: copia
  `links` tal cual.

## RemoteCatalogProvider (adapter de catálogo)

`RemoteCatalogProvider` es un `ICatalogProvider` genérico: lee un directorio YAML
(`provider.yaml` + `endpoints.yaml` + `mapping.yaml` + `resources.yaml`) y opcionalmente
un `ProviderFetcher` Nivel 2. Convierte `ProviderWork` → `CandidateRepresentation`.

**Nunca descarga ficheros.** Su única responsabilidad es traducir el JSON del proveedor
a objetos internos. La descarga la hace OSAP-API a través de `links.download` (302/proxy).
Los antiguos `IMSLPProvider.download()`, `OMRProvider.download()` y
`OpenScoreProvider.download()` desaparecen: esa lógica pertenece ahora al proveedor REST.

## Estado de los proveedores

| Proveedor | Nivel | Tipo | Formato nativo | Estado |
|---|---|---|---|---|
| `omr` | 2 | REST storage (`OmrStorageFetcher`, `/api/v1/search`) | MusicXML | **Activo** (wiring) |
| `imslp` | 2 | MediaWiki (`MediaWikiFetcher`) | PDF | **Activo** (wiring) |
| `openscore` | 2 | GitHub (`GitHubFetcher`) | MusicXML | **Activo** (wiring) |
| `local` | 3 | Ficheros | — | **Activo** (wiring) |
| `hymnary` | 1 | REST JSON (`/api/tunes`) | MusicXML, MIDI, PDF | **Activo** (wiring) |
| `iiif` | 2 | IIIF Presentation API 3.0 (`IIIFFetcher`) | MusicXML, MEI, PDF | **Activo** (wiring) |
| `zenodo` | 1 | REST JSON (`/api/records`) | MusicXML, MEI, MIDI | **Activo** (wiring) |
| `cpdl` | 2 | MediaWiki (`MediaWikiFetcher`) | PDF | **Definido, NO cableado** |
| `musescore` | 2/3 | Web + OAuth (fetcher propio) | MSCZ/MSCX/PDF | **Definido, NO cableado** |
| `mutopia` | 2 | HTML CGI (`MutopiaFetcher`, `make-table.cgi`) | LY/PDF/MIDI | **Activo** (wiring) |
| `kernscores` | 2 | Ficheros Humdrum (fetcher propio) | kern | **Definido, NO cableado** |
| `freescores` | 2/3 | Web/HTML (fetcher propio) | PDF/MusicXML | **Definido, NO cableado** |
| `musopen` | 2 | REST key-gated (fetcher propio) | PDF/MusicXML | **Definido, NO cableado** |

> **Sondeo de accesibilidad (2026-08-27):** de los proveedores adicionales **Mutopia, Hymnary, IIIF (BnF Gallica), Zenodo** son alcanzables y están **cableados**. El resto sigue **bloqueado o caído**: `cpdl`, `musescore` y `musopen` responden **HTTP 403 Cloudflare**; `kernscores` devuelve **503 / timeout**; `freescores.com` es una landing page de dominio, no un catálogo.
>
> **Descarga protegida:** no es un bloqueo. OSAP-API **facilita el `links.download`** del
> proveedor (y avisa al usuario). Si el usuario tiene cuenta en el destino, descarga; si no,
> no. Nunca se implementa un downloader propio: se usan las clases de descarga estándar
> (link → redirect/proxy), igual que en los proveedores activos.

> **Actualización 2026-08-27:** 3 nuevos proveedores **activos y cableados**: `hymnary` (Hymnary.org, Nivel 1 REST), `iiif` (BNE/BnF/LoC/DIAMM/HathiTrust, Nivel 2 IIIF), `zenodo` (datasets MusicXML/MEI, Nivel 1 REST). Los 5 restantes (`cpdl`, `musescore`, `kernscores`, `freescores`, `musopen`) siguen pendientes de desbloqueo/acceso.

## Proveedores adicionales (definidos, pendientes de cablear)

Los proveedores se añaden igual que los activos: directorio YAML + (si aplica) un
`ProviderFetcher` de Nivel 2 que normalice el JSON. Ninguno se registra hasta que esté
resuelto su bloqueo (acceso o conversión).

### MuseScore.com (`musescore`)

- Gran repositorio de partituras subidas por usuarios. Formato nativo **MSCZ** (zip que
  contiene el fuente **MSCX**, compatible con MusicXML) y PDF.
- **Bloqueado**: no hay endpoint REST público estable para buscar sin **OAuth / API key**
  y hay **rate limits**. Requiere un fetcher propio con autenticación.
- **Conversión**: para obtener MusicXML hay que descomprimir el `.mscz` y usar el `.mscx`
  (o extraerlo vía API). El formato nativo no es PDF/MusicXML directo.

### Mutopia Project (`mutopia`)

- Partituras en **PDF** y **LilyPond (LY)** de dominio público. No ofrece MusicXML directo.
- **Bloqueado**: sin API JSON consultable; los ficheros están en rutas `ftp/`. Requiere un
  fetcher que indexe y localice los `.ly`.
- **Conversión**: `LY → MusicXML` vía LilyPond + `musicxml2ly` (o conversor propio).

### KernScores (`kernscores`)

- Partituras en formato **Humdrum kern**. No ofrece MusicXML directo.
- **Bloqueado**: sin API JSON consultable; ficheros `.kern`. Requiere un fetcher propio.
- **Conversión**: `kern → MusicXML` vía `humdrum2xml` / `musicxml-converter`.

### FreeScores.com (`freescores`)

- Plataforma con varios formatos, incluidos **PDF y MusicXML**.
- **Bloqueado**: sin API pública; solo HTML. Requiere un fetcher de scraping que respete
  términos de uso y rate limits.

### Musopen (`musopen`)

- Foco en música de dominio público: grabaciones y partituras en **PDF** y a veces
  **MusicXML**.
- **Bloqueado**: su API REST (`api.musopen.org/v1`) está **deprecada** y requiere **API
  key**; el acceso actual no es fiable. Requiere reactivar/renovar la integración o un
  mirror.

## Tabla de conversión de formatos (resumen)

| Proveedor | Fuente | Conversión a MusicXML | Esfuerzo |
|---|---|---|---|
| `musescore` | MSCZ/MSCX | Descomprimir `.mscz` → usar `.mscx` | Bajo |
| `mutopia` | LY (LilyPond) | LilyPond + `musicxml2ly` | Medio |
| `kernscores` | kern (Humdrum) | `humdrum2xml` / `musicxml-converter` | Medio |
| `freescores` | PDF/MusicXML | Ninguna (ya lo incluye) | Ninguno |
| `musopen` | PDF/MusicXML | Ninguna (a veces directo) | Ninguno |

### CPDL (Choral Public Domain Library)

- Misma tecnología que IMSLP (MediaWiki), por lo que **reutiliza `MediaWikiFetcher`**
  con `base_url = https://www.cpdl.org/wiki`. Solo hay que añadir `providers/cpdl/` y
  registrarlo en `wiring.py`:
  ```python
  container.register_catalog_provider(
      RemoteCatalogProvider(
          definition_path=providers_root / "cpdl",
          fetcher=MediaWikiFetcher(MediaWikiClient(base_url="https://www.cpdl.org/wiki")),
      )
  )
  ```
- **Bloqueado**: el sitio responde **HTTP 403 Cloudflare** (`Server: cloudflare`, con
  `cf-ray`) incluso desde la página principal. Es un bloqueo por huella TLS/IP + JS
  challenge, **no** lo resuelve el User-Agent. Desde `urllib` puro no es accesible.
- **Pendiente**: desbloquear el acceso (proxy, navegador real con challenge, o mirror)
  antes de activar. La definición declarativa ya existe en `providers/cpdl/`.
- Nota: `MediaWikiClient` usa por defecto un **User-Agent de navegador real**
  (Mozilla/Chrome completo) para reducir bloqueos basados en UA.

## Objetivo de diseño

> El primer proveedor funcional sigue siendo **osap-storage**. La generalización surge de
> abstraer lo que ya funciona, no de construir un framework complejo antes de tener
> 2–3 implementaciones reales.
