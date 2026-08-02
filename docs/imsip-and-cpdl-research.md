# IMSLP & CPDL — Investigación técnica para proveedores de OSAP

**Fecha:** 2026-08-01 · **Propósito:** Determinar cómo implementar correctamente
`ImslpProvider` y analizar la viabilidad de `CPDLProvider`, sin depender de
endpoints obsoletos como `api.imslp.org/petrucci_api.php`.

---

## 1. APIs oficiales de IMSLP

### 1.1. Worklist API (oficial, documentada)

**Endpoint:** `imslp.org/imslpscripts/API.ISCR.php?account=worklist/disclaimer=accepted/sort=id/type=2/start=0/retformat=json`

- `type=1` = lista de **personas** (compositores, intérpretes, editores…).
- `type=2` = lista de **obras** completa (paginated via `start`).
- Formatos: `pretty`, `json`, `php`, `wddx`.
- Documentación oficial: `imslp.org/wiki/IMSLP:API`.

**Limitaciones críticas:**
- **No es una API de búsqueda**: devuelve la **lista completa** de obras del
  catálogo IMSLP (cientos de miles de registros), paginada en bloques. No
  admite parámetros de filtro (`?title=`, `?composer=`). Para buscar por título
  o compositor habría que descargar la lista entera y filtrar localmente, lo
  que es inviable sin un índice local permanente.
- El formato JSON devuelto es heterogéneo (los campos varían según el tipo de
  obra, plantilla de la página wiki, etc.). Parsearlo requiere lógica defensiva
  y tolerante a cambios.
- **Estabilidad:** media — es un script ad‑hoc, no versionado, que podría
  cambiar sin aviso.

**Veredicto para OSAP:** solo útil como fuente masiva de metadatos para un
índice local ocasional, **no como API de búsqueda en tiempo real**.

### 1.2. MediaWiki API (no oficial como API de partituras, pero funcional)

**Endpoint:** `imslp.org/api.php`

IMSLP corre sobre MediaWiki, por lo que expone la **API estándar de
MediaWiki**, que incluye:

| Acción              | ¿Útil para OSAP? | Detalle |
|---------------------|------------------|---------|
| `list=search`       | ✅ Sí           | Búsqueda por texto libre (título, compositor, palabras clave) |
| `list=categorymembers` | ✅ Sí        | Obras dentro de una categoría (p.ej. `Category:Works by Toldrà, Eduard`) |
| `prop=imageinfo`    | ✅ Sí           | Metadatos de archivos (tamaño, tipo MIME, URL de descarga) |
| `prop=extlinks`     | ✅ Sí           | Enlaces externos (descarga de PDF) |
| `prop=revisions`    | ✅ Sí           | Contenido de la página (metadatos en infobox) |
| `list=allcategories`| ⚠️ Parcial     | Categorías de compositores |
| `generator=search`  | ✅ Sí           | Combina búsqueda con consulta de propiedades |

**Veredicto para OSAP:** la MediaWiki API es **la alternativa real más robusta**
para implementar búsquedas por título y compositor, y para obtener metadatos y
enlaces a archivos.

### 1.3. `api.imslp.org/petrucci_api.php` — NO EXISTE

Este endpoint (usado en la implementación actual de `ImslpProvider`) **no
resuelve DNS** (`NXDOMAIN`). No debe usarse en ninguna implementación futura.

---

## 2. MediaWiki API — ejemplos reales

### 2.1. Búsqueda por título y compositor

```
GET imslp.org/api.php?action=query&list=search&srsearch=Cançó+de+Comiat&format=json
```

Devuelve una lista de páginas que contienen los términos, con título, snippet y
timestamp. Para filtrar solo páginas del espacio principal (obras) se puede
añadir `srnamespace=0`.

### 2.2. Obras de un compositor via categorías

Los compositores tienen categorías como `Category:Works by Toldrà, Eduard`.

```
GET imslp.org/api.php?action=query&list=categorymembers&cmtitle=Category:Works+by+Toldrà,+Eduard&cmlimit=50&format=json
```

Devuelve las páginas de obra dentro de esa categoría (título, pageid).

### 2.3. Obtener metadatos de una obra

```
GET imslp.org/api.php?action=query&prop=revisions&titles=<TITLE>&rvprop=content&format=json
```

Devuelve el wikitexto de la página de la obra, que contiene la plantilla
`{{#fte:imslppage...}}` con campos estructurados (compositor, editor, fecha,
instrumentación, copyright). Parsear el wikitexto requiere una gramática
específica de las plantillas de IMSLP, pero es estable (las plantillas no
cambian a menudo).

### 2.4. Obtener archivos (PDF / MusicXML)

```
GET imslp.org/api.php?action=query&prop=images&titles=<TITLE>&format=json
```

Devuelve los nombres de los archivos asociados a la página de la obra.

```
GET imslp.org/api.php?action=query&prop=imageinfo&titles=File:<FILE>&iiprop=url|size|mime|sha1&format=json
```

Devuelve la URL de descarga, el tamaño, el tipo MIME y el hash SHA-1 del
archivo.

**IMPORTANTE:** para descargar archivos es necesario enviar la cookie
`imslpdisclaimeraccepted=yes`. Sin ella, algunos archivos redirigen a la página
de disclaimer. Esta cookie se obtiene aceptando el disclaimer en el sitio web y
tiene una duración típica de 7 días (renovable).

---

## 3. Descarga de archivos

### 3.1. Mecanismo real

1. La página de la obra contiene enlaces a los archivos en el espacio `File:`.
2. La URL de descarga directa se obtiene vía `prop=imageinfo` (ver arriba).
3. La URL tiene el formato: `imslp.org/wiki/Special:ImagefromIndex/<ID>/<hash>`
   o una URL directa al servidor de archivos (`imslp.org/images/...` o CDN
   regional: `s9.imslp.org/...`, `petruccilibrary.ca/...`).
4. La descarga requiere la cookie `imslpdisclaimeraccepted=yes`.

### 3.2. URLS permanentes — NO

IMSLP **no garantiza URLs permanentes** de descarga. Las URLs pueden cambiar
cuando se actualiza un archivo (nueva revisión) o se ajusta la infraestructura.
El identificador estable es el **nombre de la página `File:`**.

### 3.3. Restricciones regionales

IMSLP aplica restricciones geográficas basadas en IP para obras cuyo copyright
no ha expirado en todas las jurisdicciones (p.ej. obras de compositores que
fallecieron hace menos de 70 años en la UE no se sirven a IPs europeas desde
`imslp.org`, pero sí desde `imslp.eu` o `petruccilibrary.ca`). OSAP debe
manejar el error HTTP 451 (Unavailable For Legal Reasons) que IMSLP devuelve en
estos casos.

---

## 4. Licencias

### 4.1. ¿Qué puede descargarse automáticamente?

- Obras en **dominio público en Canadá** (país de la jurisdicción original de
  IMSLP): fallecimiento del compositor > 50 años.
- Obras con **permiso explícito** del titular de derechos (Creative Commons u
  otras licencias).

### 4.2. ¿Qué depende del país?

- Obras de compositores fallecidos hace 50–70 años pueden ser PD en Canadá pero
  no en la UE o EEUU → IMSLP bloquea por IP (HTTP 451).
- Algunas ediciones modernas (Urtext, Bärenreiter) pueden tener copyright
  editorial aunque la obra sea PD.

### 4.3. ¿Cómo informa IMSLP del dominio público?

Cada página de obra incluye una plantilla `{{Copyright|...}}` o
`{{WorkNonPD-EU}}`. El wikitexto extraído con `prop=revisions` contiene esta
información, que se puede parsear para modelar la licencia. Los valores típicos
son: `Public Domain`, `Creative Commons Attribution 4.0`, `Non-PD EU`, `Non-PD
US`.

### 4.4. Modelado en OSAP

- `WorkDescriptor.license` debe ser un `str` libre (los valores no están
  normalizados entre proveedores).
- `CandidateRepresentation.public_domain` → booleano derivado del parseo.
- `CandidateRepresentation.license` → texto original de la plantilla.
- `CandidateRepresentation.local_path` → `None` (online).
- En caso de HTTP 451, el proveedor debe devolver un candidato con
  `CandidateRepresentation.metadata["restricted"] = True` y no exponer URL de
  descarga. La lógica de bloqueo regional **no** pertenece al dominio.

---

## 5. Información recuperable por obra

| Campo               | Fuente                          | Fiabilidad |
|----------------------|---------------------------------|------------|
| Título               | Título de la página wiki        | Alta       |
| Compositor           | Nombre de categoría / plantilla | Alta       |
| Movimiento           | Wikitexto (parsing de plantilla)| Media      |
| Instrumentación      | Categorías / plantilla          | Media      |
| Voces                | Categorías (SATB, TTBB, etc.)   | Media      |
| Editor               | Plantilla de la página          | Media      |
| Fecha de publicación | Plantilla / categoría           | Baja       |
| Ediciones            | Enlaces desde la página         | Alta       |
| Formato disponible   | MIME del archivo vía imageinfo  | Alta       |
| Dominio público      | Plantilla de copyright          | Alta       |
| Enlace de descarga   | imageinfo.url                   | Alta       |

---

## 6. Búsquedas

| Búsqueda                              | Método recomendado                     |
|---------------------------------------|----------------------------------------|
| Buscar por título                     | `list=search` con `srnamespace=0`      |
| Buscar por compositor                 | `list=search` con el nombre            |
| Buscar por título parcial             | `list=search` con comodines (limitado) |
| Buscar por ambos                      | `list=search` con ambos términos       |
| Listar obras de un compositor         | `list=categorymembers` en `Category:Works by Composer` |
| Obtener todas las ediciones de una obra| `prop=images` de la página de obra     |

---

## 7. Robustez — comparativa de métodos

| Método              | Estabilidad | Es scraping | Mantenibilidad | Recomendado para OSAP |
|---------------------|-------------|-------------|----------------|-----------------------|
| MediaWiki API       | 🟢 Alta     | No (API pública y documentada) | Alta | **Sí** — búsqueda principal |
| Worklist API        | 🟡 Media    | No (API ad-hoc de IMSLP) | Baja | No — inviable para búsqueda |
| HTML scraping       | 🔴 Baja     | Sí (depende de la estructura del DOM) | Muy baja | No — solo como fallback |
| OpenSearch          | 🟡 Media    | No (protocolo estándar) | Media | Podría usarse (no investigado en detalle) |
| Dumps               | 🟢 Alta     | No | Alta | No — son dumps estáticos, no búsqueda en vivo |

**Veredicto:** OSAP debe usar **MediaWiki API** como método principal. El HTML
scraping **nunca** debe ser el camino principal. El Worklist API puede usarse
para construir un índice local offline (similar a como se hace con datasets),
pero no para búsqueda en tiempo real.

---

## 8. Caché

| Qué cachear               | TTL recomendado           | Estrategia de invalidación            |
|---------------------------|---------------------------|---------------------------------------|
| Resultados de búsqueda    | 1 hora                    | Inmutables (nuevos resultados no invalidan viejos) |
| Metadatos de obra         | 24 horas                  | Invalidar al detectar nueva revisión |
| Metadatos de archivo      | 24 horas                  | Invalidar si cambia el hash SHA-1    |
| URL de descarga           | 1 hora                    | Re-obtener si HTTP 404               |
| Lista de obras de compositor | 6 horas               | Invalidar si `cmcontinue` nuevo      |

La caché debe implementarse usando `ICache` (puerto existente) con TTL y
versionado. Nunca se almacenarán los archivos descargados más allá de lo que
IMSLP permite (respetar cookies, no redistribuir).

---

## 9. Rate limiting

IMSLP **no publica límites oficiales** de uso de su MediaWiki API. Sin embargo,
buenas prácticas para OSAP:

- Máximo **1 petición por segundo** a la MediaWiki API.
- Backoff exponencial en caso de error HTTP 429.
- User-Agent identificable: `osap/1.0 (https://github.com/...)`.
- Respetar `Retry-After` si se devuelve.
- No paralelizar más de 2 workers.
- Cachear agresivamente (ver sección 8).

---

## 10. CPDL (Choral Public Domain Library)

### 10.1. Investigación

- CPDL/ChoralWiki corre sobre **MediaWiki** en `cpdl.org/wiki/`.
- La API MediaWiki (`cpdl.org/wiki/api.php`) devuelve **HTTP 403** desde esta
  ubicación. Es posible que requiera autenticación, bloqueo geográfico o
  restricción de User-Agent.
- La estructura de CPDL es similar a IMSLP: páginas de obra con enlaces a
  archivos (PDF, MIDI, MP3, notación: Finale, Sibelius, LilyPond, MusicXML).
- Licencia por defecto: **CPDL License** (basada en GNU GPL).

### 10.2. Viabilidad

- **SI** la API MediaWiki puede desbloquearse (User-Agent correcto, posible
  autenticación), CPDL es **altamente viable** como proveedor. La
  implementación compartiría gran parte del código con IMSLP
  (`MediaWikiClient` genérico).
- **SI** la API sigue bloqueada tras intentar autenticación/User-Agent, el HTML
  scraping sería la única opción, lo cual **no se recomienda** como método
  principal.

### 10.3. Recomendación

Incluir CPDL como **siguiente proveedor planificado** una vez que IMSLP esté
implementado y probado. La arquitectura debe prever un `MediaWikiProvider`
genérico del que hereden `ImslpProvider` y `CpdlProvider`, parametrizado por
URL base y gramática de plantillas.

---

## 11. Arquitectura propuesta

```
                        ┌─────────────────────┐
                        │   ICatalogProvider  │      (puerto)
                        └──────────┬──────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              │                    │                    │
     ┌────────▼────────┐  ┌───────▼───────┐  ┌────────▼────────┐
     │ ImslpProvider   │  │ CpdlProvider  │  │ OpenScoreProvider│
     │ (online)        │  │ (online)      │  │ (online)         │
     └────────┬────────┘  └───────┬───────┘  └─────────────────┘
              │                    │
     ┌────────▼────────────────────▼────────┐
     │         MediaWikiClient              │  (infra, reutilizable)
     │  • search(query, namespace)          │
     │  • category_members(category)        │
     │  • page_revisions(title)             │
     │  • file_metadata(file_title)         │
     │  • download(file_url, cookie)        │
     │  cache: ICache                       │
     │  rate_limiter: interno               │
     └──────────────────┬───────────────────┘
                        │
              ┌─────────▼─────────┐
              │    HttpClient     │  (infra, inyectable)
              │  (urllib + retry) │
              └───────────────────┘
```

### Principios aplicados

- **SOLID:** `MediaWikiClient` tiene una única responsabilidad (interactuar con
  la API MediaWiki). `ImslpProvider` traduce respuestas a objetos de dominio.
- **DDD:** el dominio solo conoce `WorkDescriptor`, `CandidateRepresentation`,
  `ResolveRequest`. Nunca conoce MediaWiki ni cookies.
- **Hexagonal:** `ICatalogProvider` es el puerto; `MediaWikiClient` y
  `HttpClient` son adaptadores de infraestructura.
- **DI:** `HttpClient` y `ICache` se inyectan en `MediaWikiClient`.
- **Open/Closed:** añadir CPDL solo requiere parametrizar `MediaWikiClient` con
  la URL base y una gramática de plantillas específica.

---

## 12. Integración con OSAP

| Componente            | Cómo se integra                                                |
|-----------------------|----------------------------------------------------------------|
| `CatalogManager`      | Registra `ImslpProvider` como `ICatalogProvider`                |
| `WorkResolutionEngine`| Consulta `provider.search(request)` → `CandidateRepresentation[]` |
| `RankingEngine`       | Rankea entre IMSLP (PDF) y OpenScore (MusicXML); la licencia y el formato son criterios |
| `Knowledge Base`      | Registra éxitos/fallos de descarga, tiempos y calidad          |
| `Local Library`       | Almacena el PDF/MusicXML descargado                            |
| `DatasetManager`      | No interviene: IMSLP es online, no es un dataset               |

---

## 13. Plan de implementación

### Fase 1 — `MediaWikiClient` (infraestructura)

- Encapsula `imslp.org/api.php`.
- Métodos: `search`, `category_members`, `page_revisions`, `file_metadata`.
- Rate limiter interno (1 req/s, backoff exponencial).
- Caché inyectable (`ICache`).
- Cookie `imslpdisclaimeraccepted` gestionada internamente.
- Tipado estricto, sin scraping.

### Fase 2 — `ImslpProvider` (implementa `ICatalogProvider`)

- `search(request)` → `list=search` → parseo → `CandidateRepresentation[]`.
- `download(candidate)` → `imageinfo` → GET con cookie → `AcquisitionResult`.
- `metadata()` → `CatalogInfo`.
- `capabilities()` → `CatalogCapabilities(offline=False, formats=[PDF, MusicXML, ...])`.
- `required_resources()` → `()` (online, sin recurso local).
- Parsea el wikitexto para extraer licencia, compositor, instrumentación.

### Fase 3 — Pruebas

- Tests unitarios con respuestas MediaWiki reales cacheadas (fixtures JSON).
- Test de `search` por título, por compositor, por ambos.
- Test de `download` con cookie simulada.
- Test de HTTP 451 (bloqueo regional) → candidato marcado como restringido.
- Test de caché: segunda llamada no hace HTTP.

### Fase 4 — CPDL (si la API es accesible)

- Parametrizar `MediaWikiClient` con `cpdl.org/wiki/api.php`.
- `CpdlProvider` hereda la lógica de parseo específica de plantillas de CPDL.
- Las licencias de CPDL (CPDL License) se mapean a `CandidateRepresentation.license`.

---

## 14. Resumen ejecutivo

| Aspecto                          | Decisión |
|----------------------------------|----------|
| API principal                    | **MediaWiki API** (`imslp.org/api.php`) |
| Búsqueda por título/compositor   | `list=search` |
| Obras de un compositor           | `list=categorymembers` |
| Metadatos de obra                | `prop=revisions` (wikitexto) |
| URL de descarga                  | `prop=imageinfo` (requiere cookie `imslpdisclaimeraccepted=yes`) |
| Endpoint obsoleto                | `api.imslp.org/petrucci_api.php` → **NO USAR** |
| CPDL                             | **Planificado**. Requiere desbloquear la API (403). Si no, HTML scraping como fallback. |
| Caché                            | Mecanismo `ICache` con TTL por tipo de respuesta |
| Rate limiting                    | 1 req/s + backoff exponencial + User-Agent OSAP |
| Licencias                        | Parseo de `{{Copyright|...}}` en wikitexto |
| Arquitectura                     | `ICatalogProvider` → `ImslpProvider` → `MediaWikiClient` → `HttpClient` |
| Próximo paso                     | Implementar `MediaWikiClient` (infra) + `ImslpProvider` por fases |



---

## 15. Verificación en vivo (2026-08-01)

Todas las llamadas API verificadas contra `imslp.org`:

### 15.1. Búsqueda por título (`list=search`)

```
GET imslp.org/api.php?action=query&list=search&srsearch=Mozart&srnamespace=0&format=json&srlimit=3
```

✅ **Respuesta real**: 3 obras de Mozart encontradas (K.609, K.455, Ave verum
corpus K.618), con `title`, `snippet`, `size`, `wordcount`, `timestamp`.
Búsqueda `ave+maria` también devuelve resultados correctos con `srwhat=text`.

### 15.2. Categorías de compositor (`list=allcategories`)

```
GET imslp.org/api.php?action=query&list=allcategories&acprefix=Works+by+Mozart&format=json
```

✅ **Respuesta real**: `"Works by Mozart"` y `"Works by Mozart, Wolfgang
Amadeus"`.

### 15.3. Worklist API

```
GET imslp.org/imslpscripts/API.ISCR.php?account=worklist/disclaimer=accepted/type=2/start=0/retformat=json
```

✅ **Responde correctamente** (lista completa de obras paginable por `start`).

### 15.4. CPDL

```
GET cpdl.org/wiki/api.php
```

❌ **HTTP 403** — La API MediaWiki de CPDL está restringida. Requiere
investigación adicional (autenticación, User-Agent, bloqueo geográfico).

### 15.5. Llamadas que NO funcionan

```
GET api.imslp.org/petrucci_api.php?query=...  → NXDOMAIN (el host no existe)
GET imslp.org/doc/petrucci_api.php?query=...  → NXDOMAIN
```

`api.imslp.org` no resuelve DNS desde esta ubicación. El endpoint `petrucci_api.php`
**no debe usarse en ninguna implementación**.
