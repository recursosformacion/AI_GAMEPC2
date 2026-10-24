# Estudio inicial — YouTube en la ficha de obra (`ai-recogeYouTube`)

Estado: **estudio**, sin implementación. Objetivo: botón en la ficha de una obra que abra una
pantalla **de OSAP** (no la web local del módulo) para buscar vídeos en YouTube, revisarlos y
aprobar/rechazar su asociación con la obra y la voz. Solo usuarios autenticados pueden votar.

## 1. Qué existe ya en `ai-recogeYouTube`

- Paquete Python independiente con SQLite propia (`data/ai_recogeyoutube.sqlite3`).
- `global_search.search_global(db_path, song, author, voice, limit)`:
  - voces `all`, `song`, `soprano`, `alto`, `tenor`, `bass`;
  - `all` lanza 5 búsquedas (SATB + general); `limit` máximo 50;
  - devuelve `work_id`, `work_title`, `video_id`, `video_title`, `url`, `channel`, `voice`,
    `material_type`, `approval_count`, `rejection_count`, `author_votes`, `last_vote`;
  - ordena por aprobaciones, votos de autor, rechazos y título.
- `community.record_promotion(...)` registra/actualiza el voto por
  `(user_id, work_id, video_id, voice)`; `display_name` es obligatorio.
- `catalog.import_catalog_csv(...)` importa obras con `work_id` propio.
- Web local (`local_web.py`) ya tiene búsqueda, reproductor y votos, pero **no se usará como
  API**: OSAP llamará a las funciones Python.

Limitaciones confirmadas:

- **No hay un `work_id` explícito** en `search_global`: asocia por título (`LIKE`) y se queda
  con la primera obra. Es una coincidencia débil.
- La SQLite actual solo tiene obras demo; sin importar catálogo, los resultados llegan con
  `work_id` vacío y no se pueden votar.
- La búsqueda consume cuota de YouTube Data API.

## 2. Flujo de usuario propuesto

1. En la ficha de obra (`/obras/<id>`), botón **«Explorar en YouTube»**.
2. Navega a una pantalla nueva de OSAP: `/youtube/<work_id>` (SPA, mismo `Layout`, sidebar y
   estilos; **no** es la web local del módulo).
3. La pantalla carga los datos de la obra y **precarga**:
   - título de la obra (editable),
   - compositor (editable; si hay varios, se propone el principal),
   - voz: `Todas` por defecto (opciones: canción completa, soprano, alto, tenor, bajo),
   - límite de resultados (20/50).
4. El usuario pulsa **Buscar en YouTube** (nunca búsqueda automática al abrir).
5. Se muestran los vídeos:
   - título, canal, enlace, voz estimada, tipo de material, aprobaciones/rechazos;
   - botón de abrir/reproducir (enlace o iframe `youtube-nocookie`).
6. Si el usuario está autenticado, puede **seleccionar un vídeo** y:
   - elegir la voz real si la búsqueda fue `all` o la estimación no es fiable;
   - **Aprobar** o **Rechazar** para esa obra y voz.
7. Si no está autenticado, puede buscar y ver, pero los botones de voto muestran «Inicia
   sesión para valorar»; no se pide ningún identificador a mano.
8. Si un resultado no tiene `work_id` asociado: se puede abrir, pero **no se permite votar**
   como si la asociación estuviera confirmada.

## 3. Arquitectura de integración

```
SPA OSAP (/youtube/<work_id>)
        |  fetch /api/v1/works/<id>/youtube/search
        v
osap-api (adapter)
        |  import directo (mismo proceso/venv)
        v
ai_recogeyoutube.search_global / record_promotion
        |
        +--> SQLite propia del módulo (independiente de OSAP)
        +--> YouTube Data API (clave solo en servidor)
```

- **Invocación directa**, no HTTP a la web local. El módulo sigue siendo un repositorio
  independiente; no se copia su lógica.
- La búsqueda es síncrona y de red: ejecutarla en `asyncio.to_thread`/threadpool para no
  bloquear FastAPI.
- Configuración:
  - `YOUTUBE_API_KEY` (entorno del servidor, nunca navegador);
  - `AI_YOUTUBE_DB_PATH` (SQLite propia; una por entorno, fuera de la BD de OSAP);
  - ruta/instalación del paquete (`pip install -e` o `PYTHONPATH`), acordada en despliegue.
- No se conecta el módulo a la BD de producción de OSAP.

### Endpoints propuestos

- `POST /api/v1/works/{work_id}/youtube/search`
  `{song, author, voice, limit}` → `{items: [...], count}`.
- `POST /api/v1/works/{work_id}/youtube/votes`
  `{video_id, voice, decision, title, url, channel, material_type}` → voto guardado/actualizado.
- La identidad (`user_id`, `display_name`) se toma del token de OSAP en el servidor; no se
  acepta identidad del navegador.

## 4. Asociación obra OSAP ↔ obra del módulo (crítico)

No se puede asumir que los IDs coinciden (OSAP almacena `index-*`/UUID y el módulo usa su
catálogo). Dos opciones:

1. **Cambio mínimo en el módulo (recomendado):** `search_global(..., work_id: str | None =
   None)`. Si se pasa, usa esa obra y omite la búsqueda por título; si no, mantiene el
   comportamiento actual. Retrocompatible; no convierte el módulo en dependiente de OSAP.
2. Importar el catálogo con `import_catalog_csv` usando el ID canónico de OSAP y exigir
   coincidencia exacta antes de permitir voto. Sigue siendo más frágil que la opción 1.

Mientras no exista asociación fiable, la pantalla debe mostrar «sin obra asociada» y
deshabilitar el voto. La votación comunitaria es una señal, no una confirmación editorial.

## 5. Pantalla nueva (propuesta de UI)

Ruta `/youtube/<work_id>` dentro del `Layout` de OSAP:

- Cabecera: obra + compositor + enlace «Volver a la ficha».
- Panel de búsqueda: título, compositor, selector de voz, límite y botón Buscar; aviso de
  cuota.
- Estado vacío: «Busca para ver vídeos» (no lanzar búsqueda sola).
- Resultados en tarjetas/filas OSAP:
  - miniatura/emblema de YouTube, título, canal, voz, tipo, votos;
  - acciones: Abrir/Reproducir, Aprobar, Rechazar.
- Mensajes:
  - sin resultados ≠ error de búsqueda;
  - falta `YOUTUBE_API_KEY`, cuota/red/API, datos inválidos, SQLite;
  - sin sesión → CTA de login;
  - sin `work_id` → aviso y voto deshabilitado.
- No meter la pantalla dentro del visor de partituras ni del flujo admin.

## 6. Cuota y caché

- `voice=all` = 5 consultas × 100 unidades ≈ 500 unidades por búsqueda (10.000/día gratis
  ≈ 20 búsquedas `all`).
- Buscar solo a petición; cachear el último resultado por obra/voz y no repetir búsquedas
  idénticas; límite de resultados 20–50.
- No lanzar procesos masivos ni automáticos.

## 7. Fases y esfuerzo orientativo

1. **Contrato y catálogo** (0,5–1 d): decidir `work_id` opcional; importar una muestra de
   obras OSAP y verificar correspondencias.
2. **Backend** (1–2 d): adaptador, endpoints, identidad, errores, tests con dobles (sin
   cuota real).
3. **Pantalla OSAP** (2–3 d): ruta, botón en ficha, formulario, resultados, voto, estados.
4. **Despliegue** (0,5–1 d): instalar paquete en el venv de osap-api, SQLite y clave en el
   servidor, smoke tests.

Total MVP: **4–7 días** sin contar la migración V6 de IDs de obra ni análisis de audio.

## 8. Decisiones pendientes

- ¿Se acepta el cambio mínimo `work_id` en `search_global`?
- ¿La pantalla `/youtube/<work_id>` es una ruta SPA normal (recomendado) o una app aparte?
- ¿La búsqueda exige login o solo el voto? (propuesta: buscar/ver libre; votar con sesión).
- ¿Voz del voto: la estimada por el módulo o la que elija el usuario? (propuesta: elegirla).
- ¿Se permite embeber YouTube o solo abrir enlace? (privacidad/consentimiento).
- ¿El catálogo del módulo se importa desde OSAP en cada entorno o se mantiene un CSV?

## 9. Criterio de aceptación del MVP

Desde una obra de OSAP, un usuario autenticado abre la pantalla, busca en YouTube con datos
precargados y editables, ve resultados, abre un vídeo y registra aprobación/rechazo para esa
obra y voz. Los errores y la falta de asociación se muestran explícitamente; no se escribe en
la BD de OSAP ni se usa la web local del módulo.
