# OSAP — Auditoría de Lookup Providers

**Fecha:** 2026-08-01
**Objetivo:** Decidir qué proveedores de búsqueda merece la pena implementar de verdad, y en qué orden, **antes** de escribir más integraciones. Evitar invertir en APIs inexistentes, frágiles o no soportadas.

> Estado del código actual: `PdmxProvider` es la única implementación real y **está mal etiquetada** (ver «Hallazgo crítico» al final). Los demás proveedores son esqueletos.

---

## Resumen ejecutivo

| Proveedor | ¿API oficial? | Búsqueda título/compositor | Descarga automática | MusicXML | Licencia | Estabilidad | Recomendación |
|-----------|---------------|----------------------------|---------------------|----------|----------|-------------|----------------|
| **IMSLP** | ⚠️ Parcial (MediaWiki + worklist "ad-hoc") | ✅ Sí | ⚠️ Frágil (cookie + URLs a parchear) | ❌ Mayoría PDF/imagen (MusicXML minoría) | PD según región o permiso | 🟡 Media | **Implementar** (búsqueda fuerte; descarga con cuidado) |
| **PDMX** | ❌ No es API, es un **dataset** | ✅ Local (sobre índice descargado) | ✅ Del dataset (no en vivo) | ✅ Sí (nativo) | PD + cita obligatoria | 🟢 Estable como snapshot | **Solo offline/local**, no como servicio HTTP |
| **CPDL (ChoralWiki)** | ❌ No dedicada (MediaWiki estándar) | ✅ Sí (MediaWiki search) | ⚠️ Frágil (parseo HTML de la obra) | ⚠️ Variable (muchos .xml/.mxl, no garantizado) | CPDL License (basada en GPL) o PD | 🟡 Media | **Implementar** (clave para repertorio coral) |
| **MuseScore (.com)** | ❌ No para búsqueda/descarga (solo API de plugins del editor) | ❌ No oficial | ❌ No oficial (scraping contra ToS) | ⚠️ Interno (mscx/mscz), no público | Mezcla; mucho protegido | 🔴 Baja | **No implementar** por API |
| **OpenScore** | ❌ No es API, es **GitHub** (corpus CC0) | ✅ Local vía GitHub API/estructura | ✅ vía GitHub raw/API | ✅ Sí (nativo, alta calidad) | **CC0-1.0** (dominio público) | 🟢 Alta | **Implementar** (mejor calidad/esfuerzo) |

---

## Análisis por proveedor

### 1. IMSLP (International Music Score Library Project / Petrucci Music Library)

- **¿Existe una API oficial?** Sí, pero de forma limitada y "ad-hoc", no como un REST versionado y estable. IMSLP expone dos vías públicas documentadas:
  1. **Worklist API** (`imslp.org/imslpscripts/API.ISCR.php`): listado completo de obras y personas, paginado (~1000 registros/página), en formatos `pretty`, `json`, `php`, `wddx`.
  2. **MediaWiki API** (`imslp.org/api.php`): IMSLP corre sobre MediaWiki, por lo que hereda su API estándar (búsqueda `list=search`, lectura de páginas, categorías).
  - No existe un endpoint de búsqueda de texto libre por título/compositor "oficial" tan cómodo como uno esperaría; la búsqueda práctica se resuelve con MediaWiki `list=search` + categorías de compositor.
- **¿Búsqueda por título y compositor?** Sí. Los compositores se modelan como categorías (`Category:Toldrà, Eduard`), y las obras son páginas indexadas. Es la fuente con mejor búsqueda en vivo de las analizadas.
- **¿Descarga automática?** Parcial y frágil. Para descargar hay que:
  - Enviar la cookie `imslpdisclaimeraccepted=yes` (sin ella se recibe la página de disclaimer).
  - Resolver la URL real del archivo: los PDF se guardan como "imágenes" y la URL no se puede calcular de forma trivial; requiere parsear la página o parchear la URL a mano.
- **¿En qué formatos?** Fundamentalmente **PDF** (escaneos/imágenes) y, en minoría, MusicXML/MEI/MIDI tipografiados por editores voluntarios. No es una fuente fiable de MusicXML.
- **¿Límites de uso o autenticación?** Gratis sin registro (con la cookie de disclaimer). Existe un servicio de suscripción ("Pro+") para funcionalidades extra. Sin clave de API formal. Política DMCA y servidores regionales (Canadá / PML-US / IMSLP-EU).
- **¿Restricciones de licencia?** El contenido admisible es **dominio público en Canadá** (o con permiso del titular). Cada archivo puede tener su propia licencia; desde 2023 ya no se aceptan archivos "CC-ND". El hecho de que la música sea PD no garantiza que una *edición concreta* lo sea (derechos de la edición). Licenciamiento complejo según región.
- **¿Nivel de estabilidad?** 🟡 **Media.** La infraestructura MediaWiki es estable, pero la API de obras es "ad-hoc" y puede cambiar; la parte de descarga es la más frágil (cookie + parcheo de URLs). Adecuada para **búsqueda** robusta; la **descarga automática** debe diseñarse defensivamente y con fallback.

**Veredicto:** implementar. Prioridad alta para búsqueda por título/compositor; la descarga automática debe tratarse como mejor esfuerzo con degradación elegante.

---

### 2. PDMX (Public Domain MusicXML)

- **¿Existe una API oficial?** **No.** PDMX no es un servicio en línea. Es un **dataset de investigación**: *"PDMX: A Large-Scale Public Domain MusicXML Dataset for Symbolic Music Processing"* (~250 000 archivos MusicXML de dominio público extraídos de MuseScore), publicado en [GitHub (pnlong/PDMX)](https://github.com/pnlong/PDMX), Zenodo y HuggingFace.
- **¿Búsqueda por título y compositor?** Solo **local**: descargas el dataset + su índice de metadatos (interacciones, ratings, licencia) y buscas en tu máquina. No hay endpoint HTTP de búsqueda.
- **¿Descarga automática?** Del propio dataset (Zenodo/HuggingFace) o de archivos sueltos. No es una integración "en vivo".
- **¿En qué formatos?** **MusicXML** (nativo) + metadatos. Es justo lo que OSAP prefiere como salida simbólica.
- **¿Límites de uso o autenticación?** N/A como API. Como dataset: requiere citar el paper/autores. Tamaño grande (descarga masiva).
- **¿Restricciones de licencia?** Los scores son dominio público (filtrados desde MuseScore); el dataset exige cita. No apto para servir como servicio público en tiempo real.
- **¿Nivel de estabilidad?** 🟢 Estable como **snapshot** de datos, pero **no aplicable** como proveedor HTTP en línea.

**Veredicto:** no tratarlo como un *lookup provider* en vivo. Útil como fuente **offline/local** (cargar índice) cuando se quiera MusicXML masivo. Ver el hallazgo de nomenclatura a continuación.

---

### 3. CPDL (Choral Public Domain Library / ChoralWiki)

- **¿Existe una API oficial?** **No dedicada.** CPDL (ChoralWiki) es **MediaWiki** (`www.cpdl.org/wiki`), por lo que expone la API MediaWiki estándar (`api.php`) para búsqueda `list=search` y lectura. No hay una API musical específica documentada por CPDL.
- **¿Búsqueda por título y compositor?** Sí, vía MediaWiki search; el repertorio coral está muy bien indexado (título, compositor, géneros, número de voces). De altísima relevancia para Chorus.
- **¿Descarga automática?** No directa. Requiere **parsear el HTML** de la página de la obra para extraer los enlaces a los archivos (hay varias versiones por obra). Frágil ante cambios de plantilla.
- **¿En qué formatos?** PDF, PS, TIFF (imágenes); MIDI y MP3 (audio); y formatos de notación (Finale, Sibelius, NoteWorthy, LilyPond). Hay **MusicXML/`.xml`/`.mxl`** en muchas obras pero **no está garantizado** en todas.
- **¿Límites de uso o autenticación?** Gratis; registro solo para contribuir. MediaWiki típicamente pide un `User-Agent` correcto.
- **¿Restricciones de licencia?** Por defecto la **CPDL License** (basada en GNU GPL: permite copiar, distribuir, modificar y crear obras derivadas conservando los avisos), o dominio público, o permiso del titular. Cada obra puede tener su licencia concreta.
- **¿Nivel de estabilidad?** 🟡 **Media.** MediaWiki es estable y la búsqueda es sólida; la extracción de enlaces de descarga vía HTML es la parte frágil.

**Veredicto:** implementar. Es la fuente **más relevante para el dominio coral** del proyecto. Prioridad alta para búsqueda; descarga con parseo HTML controlado.

---

### 4. MuseScore (.com)

- **¿Existe una API oficial?** **No, para búsqueda/descarga.** La única "API de MuseScore" oficial es la de **plugins del editor de escritorio** ([musescore.github.io/MuseScore](https://musescore.github.io/MuseScore)), no del sitio web. No hay endpoint público documentado para buscar/descargar partituras. El programa de API de desarrollador (OAuth) que existió **no es una vía pública/soportada** hoy.
- **¿Búsqueda por título y compositor?** No oficial. Solo scraping/endpoints internos no documentados (la comunidad usa herramientas tipo `musescore-downloader`, que dependen de internals y se rompen).
- **¿Descarga automática?** No oficial. Requiere bypass; el acceso a PDF/audio/MIDI está restringido (algunos contenidos "Pro") y el sitio aplica anti-scraping.
- **¿En qué formatos?** PDF, MusicXML (formato interno mscx/mscz), MIDI, audio. El formato simbólico no es de acceso público limpio.
- **¿Límites de uso o autenticación?** Cuenta de usuario; contenido protegido por suscripción; los **términos de servicio prohíben el scraping**.
- **¿Restricciones de licencia?** Las partituras de usuarios tienen licencias propias muy heterogéneas; el corpus mezcla contenido libre y protegido. Es justamente por esto que PDMX se creó *filtrando* solo las de dominio público.
- **¿Nivel de estabilidad?** 🔴 **Baja** para integración programática. Alto riesgo de rotura y de incumplir los ToS.

**Veredicto:** **no implementar** como integración por API. No existe API oficial; cualquier vía es scraping frágil y contra las condiciones de uso. Si se necesita su contenido, usar **PDMX (dataset)** que ya lo filtra y licencia como PD.

---

### 5. OpenScore

- **¿Existe una API oficial?** **No es una API**, es una colección de **repositorios GitHub** de la organización [OpenScore](https://github.com/OpenScore) — p. ej. `OpenScore/Lieder` (espejo oficial del *OpenScore Lieder Corpus*) y `OpenScore/StringQuartets`. Consulta vía **GitHub API / raw / git clone**.
- **¿Búsqueda por título y compositor?** Local, sobre la estructura de carpetas del repo y metadatos (vía GitHub API `tree`/`contents`). No hay búsqueda semántica en vivo.
- **¿Descarga automática?** Sí, vía GitHub raw/API o clonando. Muy fiable.
- **¿En qué formatos?** **MusicXML** de alta calidad (corpus tipografiado), además de los archivos fuente (PDF/mscx).
- **¿Límites de uso o autenticación?** Gratis; la GitHub API sin token tiene límite de ~60 peticiones/h (el repositorio es público; con token sube a 5000/h).
- **¿Restricciones de licencia?** **CC0-1.0** (dedicación a dominio público). La mejor licencia para reutilización sin fricción.
- **¿Nivel de estabilidad?** 🟢 **Alta.** GitHub es infraestructura muy estable. La limitación es la **cobertura**: corpus focalizado (lieder, coral, cuartetos), no todo el repertorio.

**Veredicto:** implementar. La mejor relación **calidad de resultado / esfuerzo**: MusicXML limpio, CC0, descarga fiable. Ideal como proveedor "simbólico" complementario a IMSLP (que es mayormente imagen).

---

## Hallazgo crítico de nomenclatura

Nuestro `PdmxProvider` actual **no consulta el dataset PDMX**: apunta al endpoint de búsqueda de **IMSLP** (`petrucci_api.php`). Es una confusión de nombres. Con este análisis queda claro que:

- **PDMX** = dataset offline de MusicXML (no una API en vivo).
- **IMSLP** = la fuente en vivo real con búsqueda por título/compositor.

**Acción recomendada antes de seguir:**
1. **Renombrar** `PdmxProvider` → `ImslpProvider` (su lógica real ya es de IMSLP) y alinear `provider_id = "imslp"`, base URL y capacidades.
2. Tratar **PDMX** como un futuro **cargador offline** (descargar dataset + índice), no como proveedor HTTP.

---

## Orden de implementación recomendado

1. **IMSLP** (renombrar el actual) — búsqueda por título/compositor en vivo; PDF. Es la integración con más valor inmediato y la única búsqueda en vivo robusta. *(Alta prioridad.)*
2. **OpenScore (GitHub)** — MusicXML nativo y CC0 con descarga fiable. Mejor resultado simbólico con mínimo esfuerzo. *(Alta prioridad.)*
3. **CPDL (ChoralWiki)** — repertorio coral, el más alineado con Chorus. Búsqueda MediaWiki sólida; descarga vía HTML. *(Media/alta prioridad.)*
4. **PDMX (offline)** — como fuente local de MusicXML masivo, no en vivo. *(Baja prioridad; dependiente de descarga de dataset.)*
5. **MuseScore.com** — **descartar** como integración por API (no existe); no invertir tiempo.

**Criterio general:** priorizar **búsqueda en vivo y descarga fiable** sobre cobertura; evitar integraciones que dependan de scraping no documentado o de endpoints "ad-hoc" inestables como columna vertebral.

---

## Notas de investigación / fuentes

- IMSLP corre sobre **MediaWiki**; la API pública son los scripts de *worklist* (`API.ISCR.php`) + MediaWiki API. Descarga requiere cookie `imslpdisclaimeraccepted=yes` y parcheo de URL de "imágenes". *(Ver `github.com/jlumbroso/imslp` y `imslp.org/wiki/IMSLP:API`.)*
- PDMX: paper arXiv `2409.10831`; repositorio `github.com/pnlong/PDMX`; Zenodo/HuggingFace. Dataset de ~250K MusicXML PD extraídos de MuseScore.
- CPDL/ChoralWiki: MediaWiki en `www.cpdl.org/wiki`; licencia por defecto **CPDL License** (basada en GPL).
- MuseScore.com: única API oficial = plugins del editor (`musescore.github.io/MuseScore`); no hay API pública de búsqueda/descarga del sitio.
- OpenScore: org GitHub `OpenScore`; repos `Lieder`, `StringQuartets` (espejos de corpus en musescore.com); licencia **CC0-1.0**.
