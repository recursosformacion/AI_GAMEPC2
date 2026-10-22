# Pendientes — 2026-10-21

Notas para retomar mañana. No es un plan aprobado ni código: es el estado comprobado y las
decisiones que faltan. No se ha modificado `ai-recogeYouTube` ni se ha escrito en producción.

## 1. Integración de `ai-recogeYouTube` como módulo externo

**Objetivo:** desde la ficha de una obra de OSAP, buscar vídeos en YouTube, revisar resultados
y registrar la valoración del usuario (aprobado/rechazado) para esa obra y voz, invocando el
módulo Python externo. Sin segunda aplicación, sin usar su web local como API, sin duplicar su
lógica y sin tocar la BD de producción de OSAP.

Repos:

- OSAP: `D:\Proyectos\AI_OSAP\osap-api` (rama actual de trabajo, con cambios locales).
- Módulo: `D:\Proyectos\AI_OSAP\ai_recogeYouTube` (`main`, sin cambios locales).
- Contrato del módulo: `docs/INTEGRATION_CONTRACT.md`.

### Estado real del módulo (comprobado)

- Python, paquete `ai_recogeyoutube`; SQLite propia e independiente.
- Base local actual: `data/ai_recogeyoutube.sqlite3` (6 tablas: `works`, `candidates`,
  `youtube_videos`, `work_videos`, `users`, `promotions`). Solo contiene **2 obras demo**
  (`demo-001` *Ave verum corpus*, `demo-002` *O salutaris hostia*) y 66 candidatos.
- Configuración por entorno: `YOUTUBE_API_KEY`, `AI_YOUTUBE_DB_PATH` (por defecto
  `./data/ai_recogeyoutube.sqlite3`), `AI_YOUTUBE_MAX_RESULTS` (1–50).
  `get_settings()` está cacheado con `lru_cache`: cambiar el entorno exige reiniciar el proceso.
- La web local (`local_web.py`) no se va a usar.

### Contrato real (verificado en código, no solo en el doc)

`ai_recogeyoutube.global_search.search_global(db_path, *, song="", author="", voice="all", limit=50)`

- `db_path`: `Path` a la SQLite del módulo.
- Al menos uno de `song`/`author`; si no, `ValueError`.
- `voice`: `all`, `song`, `soprano`, `alto`, `tenor`, `bass`; si no, `ValueError`.
- `limit` se recorta a **50**.
- Exige `YOUTUBE_API_KEY`; si falta, `ValueError`.
- `all` lanza **5 consultas** (SATB + general); `song` una; una voz concreta, dos.
- Devuelve lista ordenada por: `approval_count` desc, `author_votes` desc,
  `rejection_count` asc, `video_title` asc.
- Campos: `work_id`, `work_title`, `video_id`, `video_title`, `url`, `channel`, `voice`,
  `material_type`, `approval_count`, `rejection_count`, `author_votes`, `last_vote`.
- Escribe candidatos (`candidates`) y relaciones (`work_videos`) en la SQLite del módulo.

`ai_recogeyoutube.community.record_promotion(db_path, *, user_id, display_name, work_id, video_id, url, title, channel_title="", voice="unknown", material_type="unknown", decision="approved", note="")`

- `user_id`, `display_name`, `work_id`, `video_id`, `url`, `title` son **obligatorios**
  (`display_name` no tiene valor por defecto real, aunque el doc lo insinúe).
- `decision`: `approved`/`rejected`; `voice` entre `soprano|alto|tenor|bass|all|unknown`.
- La clave primaria es `(user_id, work_id, video_id, voice)`: volver a votar **actualiza**,
  no duplica.
- Falla si `work_id` no existe en la tabla `works` del módulo (`Unknown work_id`).
- Crea/actualiza usuario, vídeo y relación antes del voto.

Catálogo del módulo:

- `catalog.import_catalog_csv(csv_path, db_path)`: CSV con `work_id,title` y opcionales
  `composers|alternate_titles|catalog_numbers|languages|formation` (multivalor con `|`).
- No hay importador directo desde OSAP; la correspondencia se hace por `work_id` del CSV.

### Problema crítico: asociación de obras

`search_global` **no acepta un `work_id`**. Para asociar, busca en `works` por
`title LIKE %song%`, filtra por compositor si se pasa `author` y toma **la primera fila**.
Es una coincidencia débil, justo lo que el requisito prohíbe como base de una valoración.

Consecuencias:

- La BD del módulo solo tiene obras demo; sin importar el catálogo real, todo saldría con
  `work_id` vacío (se puede ver el vídeo, pero no votar).
- Aun importando el catálogo, el `work_id` asignado puede ser el de otra obra con título
  parecido. No es verificable.
- `record_promotion` exige que el `work_id` exista en el módulo; no se puede inventar.

Opciones (elegir una antes de implementar):

1. **Cambio mínimo en el módulo (recomendado):** añadir a `search_global` un parámetro
   opcional `work_id: str | None = None`. Si se pasa, se usa esa obra directamente (validando
   que existe) y se omite la búsqueda por título; si no, se mantiene el comportamiento actual.
   Es retrocompatible y no convierte el módulo en dependiente de OSAP.
2. **Resolver fuera del módulo:** OSAP importa su catálogo al módulo con
   `import_catalog_csv` y, tras la búsqueda, solo permite votar si `work_title` + compositor
   coinciden exactamente. Sigue siendo frágil y no cumple “correspondencia explícita”.
3. **No votar** hasta que exista correspondencia fiable; permitir solo visualizar. Es lo más
   seguro, pero no cumple el criterio de aceptación.

No se debe “inventar” una obra en la SQLite para saltarse la validación.

### Arquitectura propuesta

- **Invocación directa**, no HTTP: el módulo es Python y puede instalarse en el mismo venv de
  OSAP (editable o `PYTHONPATH`). Un adaptador interno en OSAP (`YouTubeModuleAdapter`) importa
  `search_global`/`record_promotion` y traduce errores.
- La búsqueda es síncrona y hace red: ejecutarla en `run_in_threadpool`/`asyncio.to_thread`
  para no bloquear el event loop de FastAPI.
- La BD del módulo se configura con `AI_YOUTUBE_DB_PATH` (fuera de la BD de OSAP). La clave de
  YouTube solo en el entorno del servidor; nunca en el navegador.
- Endpoints OSAP propuestos (a confirmar):
  - `GET /api/v1/works/{work_id}/youtube/search?song=&author=&voice=&limit=` → resultados.
  - `POST /api/v1/works/{work_id}/youtube/vote` → `{video_id, voice, decision, ...}`.
  - El `work_id` de OSAP se resuelve a la obra del módulo con la correspondencia elegida.
- Identidad: tomar `user_id` y nombre visible del **token autenticado** en el servidor
  (patrón de `/api/v1/analytics/me`), no de un parámetro del navegador.
- UI: pestaña/sección «YouTube» en la ficha de obra, con selector
  Todas las voces / Canción completa / Soprano / Alto / Tenor / Bajo, lista de resultados
  (título, canal, enlace, voz, votos) y botones aprobar/rechazar. Si `work_id` del resultado
  está vacío, abrir el vídeo pero **deshabilitar el voto** con aviso.
- Reutilizar componentes y estilos actuales de OSAP; no crear una interfaz paralela.

### Cuota y errores

- `all` = 5 búsquedas × 100 unidades ≈ 500 unidades por acción (YouTube Data API).
- No buscar automáticamente al abrir la ficha; solo a petición del usuario.
- Cachear el último resultado por obra/voz y no repetir búsquedas idénticas en la misma sesión.
- Distinguir: sin configuración (`YOUTUBE_API_KEY`), error de red/API, parámetros inválidos,
  error de SQLite, sin resultados y resultado sin obra asociada. No devolver `[]` silencioso.

### Pruebas que habrá que añadir

- Adaptador: invocación con `song`, `author`, `voice`, `limit` correctos.
- Orden de resultados (aprobaciones, votos de autor, rechazos, título).
- Voto aprobado/rechazado y actualización del mismo usuario (sin duplicar).
- Resultado sin `work_id` → no se permite votar.
- Errores de clave/red/SQLite → error explícito, sin lista vacía.
- Independencia de la BD: el adaptador usa la SQLite del módulo, no la de OSAP.
- Dobles de YouTube/módulo; ninguna prueba con cuota real.

### Decisiones pendientes

- Aprobar el cambio mínimo de `search_global(work_id=...)` o elegir la opción 2/3.
- Cómo se exporta el catálogo de OSAP al módulo (qué `work_id`: `index-...` u otro).
- Dónde se instala el módulo en producción (mismo venv de `osap-api`, ruta y despliegue).
- Política de caché y límite de búsquedas por usuario.

## 2. Fuentes externas de partituras — estado (2026-10-21)

Comprobación con peticiones automatizadas desde local y desde el VPS. Un **403** puede ser
WAF/bot protection, no necesariamente caída; requiere navegador, allowlist o API oficial.

| Fuente | Estado | API / formato | Descarga de partituras | Nota |
|---|---|---|---|---|
| BNE Digital (`bne.es/es/catalogos/bne-digital`) | **403** (local y VPS); `datos.bne.es` y `bdh.bne.es` también 403 | IIIF/BNE Digital y datos enlazados (a confirmar) | No verificable ahora | WAF; hace falta navegador/API o acuerdo |
| `data.bnf.fr` | **200** | **SPARQL funciona** (200 XML) | No: es datos enlazados de autores/obras | Fuente de autoridad/obra, no de PDF |
| BL `bibliographic/datafree.html` | **404** | — | No | URL antigua retirada/movida; localizar servicio actual |
| DNB LinkedData (`dnb.de/.../linkeddata_node.html`) | **404** | GND/SRU (a confirmar URL actual) | No: autoridad | URL antigua; localizar endpoint vigente |
| `id.loc.gov` | **200** | JSON/MARC, autoridades LCSH/nombres | No: autoridad | Útil para compositores, no para partituras |
| Europeana Music | **200** | API con clave; metadatos/thumbnails | No directa; derechos variables | Requiere API key; enlazar al objeto |
| LOC Notated Music | **403** (local y VPS) | API JSON (`?fo=json`) y PDF/JPEG por ítem | Potencial, bloqueada | WAF; derechos variables; probar desde navegador/allowlist |
| Cantorion SATB | **200**; `robots.txt` prohíbe `/download` | PDFs por obra | Solo enlace, no scraping | Revisar licencia de cada partitura |
| Gallica (`gallica.bnf.fr`) | **403** (local y VPS) | IIIF/SRU existen | Potencial (dominio público), bloqueada | WAF; necesita navegador/allowlist/API |

Conclusión provisional:

- **Metadatos/apoyo**: `data.bnf.fr` (SPARQL), `id.loc.gov` (autoridades) y Europeana (con
  clave) son utilizables ya; no dan el PDF.
- **Partituras**: LOC, Gallica y BNE son candidatas por contenido, pero están bloqueadas a
  clientes automatizados desde aquí; Cantorion es solo enlace. No añadir como proveedor de
  descarga hasta confirmar API/acceso y licencia.
- BL y DNB requieren localizar sus URLs/servicios actuales.
- No hacer scraping masivo ni descargas sin revisar condiciones; mantenerlo como enlaces o
  metadatos hasta que haya una vía estable.

Ya existe contexto en `docs/osap/sources-investigation.md` (OMR/IMSLP/MB/RISM/Wikidata/VIAF y
la lista de fuentes bloqueadas). Esta tabla es el repaso específico de la lista de hoy.

## 3. Para mañana

- [ ] Decidir la correspondencia obra OSAP ↔ obra del módulo (preferible: `work_id` opcional
      en `search_global`).
- [ ] Exportar una muestra del catálogo de OSAP a CSV y probar `import_catalog_csv`.
- [ ] Montar el adaptador y los endpoints con dobles, sin clave real.
- [ ] Diseñar la pestaña YouTube en la ficha de obra.
- [ ] Revisar acceso oficial (API/IIIF) y licencias de LOC, Gallica, BNE y Cantorion.
- [ ] Localizar las URLs vigentes de BL y DNB.
- [ ] **OMR/Cloudflare**: el fallo de descarga en dev (`UPSTREAM_ERROR`/401) apunta al
      service token `storage:read` o a la resolución del fichero, **no** a que los binarios
      no existan: OMR siempre funcionó. Comprobar con el token de servicio antes de tocar
      nada.
- [ ] Despliegue SSR: seguir `docs/osap/prod-ssr-plan.md` (ficha de PROD y ventana).
