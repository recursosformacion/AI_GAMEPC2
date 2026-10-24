# Estudio inicial — YouTube en la ficha de obra (`ai-recogeYouTube`)

Estado: **estudio**, sin implementación. Decisiones de la revisión del 2026-10-24 ya
incorporadas.

## Decisiones

1. **Persistencia en la BD de OSAP**, no en la SQLite del módulo. La SQLite de
   `ai-recogeYouTube` queda solo para pruebas/desarrollo del módulo.
2. OSAP ya tiene **título, work_id y resource_id**. La asociación se crea **al votar**:
   `resource_id` de OSAP + `youtube_video_id` + voz.
3. Por tanto, **no hace falta mapear el catálogo del módulo ni fiarse de su `work_id`**. El
   módulo solo busca y clasifica candidatos; la relación fiable la crea OSAP.
4. Orden de resultados: primero los que **tienen votos**, después por **semejanza** con la
   búsqueda y, por último, el orden del módulo/título.
5. Buscar y ver vídeos puede ser anónimo; **votar exige sesión**. La identidad sale del token
   de OSAP, nunca de un campo del navegador.

## 1. Estado real del módulo

- Paquete Python independiente; SQLite propia solo para el piloto/pruebas.
- `global_search.search_global(db_path, song, author, voice, limit)`:
  - voces `all`, `song`, `soprano`, `alto`, `tenor`, `bass`;
  - `all` = 5 búsquedas (SATB + general); `limit` máximo 50;
  - devuelve `work_id` (del catálogo del módulo, puede ir vacío), `work_title`,
    `video_id`, `video_title`, `url`, `channel`, `voice`, `material_type`,
    `approval_count`, `rejection_count`, `author_votes`, `last_vote`.
- `community.record_promotion(...)` no se usará en producción: escribe en la SQLite del
  módulo. OSAP guardará sus propios votos.
- Web local del módulo: solo referencia de UI; **no se usa como API**.

## 2. Modelo de datos en OSAP

Tablas propuestas (esquema de OSAP, no del módulo):

```sql
-- Vídeo de YouTube (metadatos; no se descarga el medio)
youtube_videos (
  video_id        VARCHAR(32) PRIMARY KEY,
  url             VARCHAR(512) NOT NULL,
  title           VARCHAR(512) NOT NULL,
  channel         VARCHAR(255),
  published_at    DATETIME NULL,
  duration_seconds INT NULL,
  material_type   VARCHAR(32) NULL,
  created_at      DATETIME NOT NULL
);

-- Relación explícita: nuestra representación/recurso <-> vídeo
resource_youtube_videos (
  id              BIGINT PRIMARY KEY AUTO_INCREMENT,
  resource_id     VARCHAR(64) NOT NULL,   -- id de representación de OSAP
  work_id         VARCHAR(64) NOT NULL,   -- contexto de obra
  video_id        VARCHAR(32) NOT NULL,
  voice           VARCHAR(16) NOT NULL,   -- soprano|alto|tenor|bass|unknown
  search_query    VARCHAR(512) NULL,
  similarity      DECIMAL(5,4) NULL,
  created_at      DATETIME NOT NULL,
  UNIQUE KEY uq_resource_video_voice (resource_id, video_id, voice),
  KEY ix_work (work_id),
  FOREIGN KEY (video_id) REFERENCES youtube_videos(video_id)
);

-- Voto comunitario (un usuario, un recurso, un vídeo y una voz)
resource_youtube_votes (
  user_id         VARCHAR(64) NOT NULL,
  resource_id     VARCHAR(64) NOT NULL,
  video_id        VARCHAR(32) NOT NULL,
  voice           VARCHAR(16) NOT NULL,
  decision        ENUM('approved','rejected') NOT NULL,
  note            VARCHAR(512) NULL,
  created_at      DATETIME NOT NULL,
  updated_at      DATETIME NOT NULL,
  PRIMARY KEY (user_id, resource_id, video_id, voice),
  KEY ix_video (video_id)
);
```

- Un vídeo puede asociarse a varias representaciones de la misma obra; el voto es **por
  representación**.
- Al votar se crea/actualiza `resource_youtube_videos` si no existía.
- Los contadores se calculan desde `resource_youtube_votes`; no se confía en los del módulo.
- `resource_id` es la representación concreta que el usuario elige en la pantalla. Si entra
  desde la obra, la pantalla pide elegir representación (o la recibe por query).

## 3. Flujo de usuario

1. En la ficha de obra, botón **«Explorar en YouTube»**.
2. Pantalla nueva de OSAP `/youtube/<work_id>` (dentro del `Layout`; no es la web del
   módulo).
3. Cabecera: obra + compositor + volver a la ficha. Selector de **representación** de la obra
   (obligatorio para votar; opcional para buscar/ver).
4. Formulario precargado y editable: título, compositor, voz (Todas/Canción completa/SATB) y
   límite.
5. **Buscar** (solo a petición). Los resultados se mezclan con los votos/relaciones de OSAP
   para esa representación.
6. Cada vídeo muestra título, canal, enlace, voz estimada, tipo, semejanza y votos
   (aprobados/rechazados). Se puede abrir/reproducir.
7. Con sesión: seleccionar vídeo, elegir voz si procede y **Aprobar/Rechazar**; se crea la
   relación con el `resource_id` y se guarda/actualiza el voto.
8. Sin sesión: buscar/ver libre; votar muestra «Inicia sesión para valorar».
9. Sin representación seleccionada: se puede ver, pero el voto está deshabilitado.

## 4. Orden de resultados

1. Vídeos con **votos de OSAP** para esa representación:
   - primero por aprobaciones descendente,
   - luego por rechazos ascendente,
   - luego por total de votos.
2. Vídeos sin votos: por **semejanza** con la consulta (título/compositor/palabras
   distintivas) descendente.
3. Empate: orden del módulo y título.

La semejanza se calcula en el servidor al asociar el resultado a la búsqueda (normalización,
solapamiento de tokens, distancia de edición/RapidFuzz si está disponible) y se guarda en
`resource_youtube_videos.similarity` para no recalcular en cada listado.

## 5. Arquitectura de integración

```
SPA OSAP /youtube/<work_id>
   |  POST /api/v1/works/<work_id>/youtube/search
   v
osap-api (adaptador YouTube)
   |-- import directo -> ai_recogeyoutube.search_global  (solo búsqueda)
   |-- lee/escribe OSAP DB: youtube_videos / resource_youtube_videos / votes
   |-- identidad desde el token de OSAP
   v
OSAP DB (MySQL)  +  YouTube Data API (clave solo servidor)
```

- Invocación **directa** del paquete Python (mismo venv o `PYTHONPATH`), en threadpool.
- El módulo no escribe en la BD de OSAP; el adaptador OSAP sí.
- SQLite del módulo solo para sus tests/desarrollo.
- `YOUTUBE_API_KEY` solo en el entorno del servidor.

### Endpoints

- `POST /api/v1/works/{work_id}/youtube/search`
  `{song, author, voice, limit, resource_id?}` → `{items: [...]}` con votos y relación de OSAP.
- `POST /api/v1/resources/{resource_id}/youtube/votes`
  `{video_id, voice, decision, title, url, channel, material_type}` → voto y relación.
- La identidad (`user_id`, `display_name`) sale del token de OSAP; no del cuerpo.

## 6. Pantalla dentro de OSAP

- Mismo `Layout`, tipografía, tarjetas y botones de OSAP.
- Panel de búsqueda y selector de representación.
- Estado inicial: «Elige representación y busca»; no lanzar búsqueda automática.
- Resultados con badges de voz/tipo/semejanza y votos.
- Mensajes distintos para: sin resultados, falta de clave, cuota/red/API, error de SQLite/BD,
  sin sesión, sin representación.
- No incluir la pantalla en el visor de partituras ni en admin.

## 7. Cuota y errores

- `all` = 5 búsquedas × 100 unidades ≈ 500; free ≈ 20 búsquedas `all`/día.
- Cachear el último resultado por obra/voz/representación y no repetir búsquedas idénticas.
- Límite 20–50 resultados; no procesos masivos.
- Distinguir «sin resultados» de «búsqueda fallida»; no devolver listas vacías ante errores.
- Errores de voto: sin sesión, sin representación, vídeo inválido, duplicado (se actualiza),
  fallo de BD.

## 8. Fases y esfuerzo

1. **Esquema OSAP + migración** (0,5 d).
2. **Adaptador/búsqueda/votos** con tests y dobles de YouTube (1–2 d).
3. **Pantalla OSAP + botón en ficha + selector de representación** (2–3 d).
4. **Despliegue** (paquete en venv, clave y tabla; 0,5 d).

MVP: 4–7 días. No incluye análisis de audio ni V6.

## 9. Decisiones abiertas

- ¿Se guarda en `osap_storage` (junto a resources) o en `osap_api`? Propuesta:
  `osap_storage`, por la FK a `resource_id`.
- ¿El voto se agrega a nivel de obra además de representación? Propuesta: por representación;
  la obra solo agrupa.
- ¿Se muestra un contador global del módulo (SQLite) además del de OSAP? Propuesta: no; solo
  votos de OSAP.
- ¿Embed de YouTube o solo enlace? Privacidad/consentimiento.
- ¿Qué representación se preselecciona si la obra tiene varias? La primera disponible, pero el
  usuario debe confirmarla antes de votar.
