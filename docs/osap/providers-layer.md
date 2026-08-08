# Capa Provider — Arquitectura (Provider API v1.3)

> Documenta la nueva capa de adaptación de proveedores. Todos los proveedores devuelven
> el mismo contrato (`ProviderWork`); OSAP-API es el único que lo transforma al modelo
> interno. El núcleo (Canonicalizer, Matcher, Ranking, Work Resolution, Relationships,
> Knowledge Hub) nunca conoce cómo responde un proveedor.

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
│   └── mediawiki_fetcher.py   # IMSLP (Nivel 2)
└── (definiciones por proveedor fuera del paquete, p. ej. providers/{omr,imslp,openscore}/)
    ├── provider.yaml          # id, name, base_url, authentication, protocol
    ├── endpoints.yaml         # bloques endpoint: lookup, search, resource, download
    ├── mapping.yaml           # bloque `work:` (target plano -> ruta del proveedor)
    └── resources.yaml         # bloque `work:` con array/fields/links de recursos
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

| Proveedor | Nivel | Tipo | Estado |
|---|---|---|---|
| `omr` | 1 | REST (`storage.openmusicrepository.com`) | **Activo** (wiring) |
| `imslp` | 2 | MediaWiki (`MediaWikiFetcher`) | **Activo** (wiring) |
| `openscore` | 2 | GitHub (`GitHubFetcher`) | **Activo** (wiring) |
| `local` | 3 | Ficheros | **Activo** (wiring) |
| `cpdl` | 2 | MediaWiki (`MediaWikiFetcher`) | **Definido, NO cableado** |

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
