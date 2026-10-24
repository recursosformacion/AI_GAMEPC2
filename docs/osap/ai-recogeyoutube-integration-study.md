# Estudio inicial — YouTube en la ficha de obra (`ai-recogeYouTube`)

Estado: **estudio**, sin implementación. Revisión del 2026-10-24: el aplicativo de YouTube es
**independiente**, con su **propia base de datos MySQL**. No usa la BD de OSAP ni la SQLite del
módulo (esta queda para pruebas).

## Decisiones

1. **Aplicativo independiente** (frontend + backend propio) con **MySQL propio**. OSAP no es
   su base de datos.
2. La SQLite de `ai-recogeYouTube` solo se usa en tests/desarrollo del módulo.
3. OSAP aporta el contexto: `work_id`, `resource_id`, título, compositor y la identidad
   autenticada. El aplicativo guarda la relación **resource de OSAP ↔ vídeo de YouTube** y los
   votos.
4. No se copia el catálogo de obras al aplicativo ni se depende de su `work_id`/SQLite. La
   relación fiable se crea al votar con el `resource_id` de OSAP.
5. Orden de resultados: primero los que tienen votos, después por semejanza con la búsqueda y,
   por último, orden del módulo/título.
6. Buscar y ver vídeos puede ser anónimo; **votar exige sesión de OSAP**.
7. El aplicativo se despliega en **`videos.openmusicrepository.com`** (subdominio propio),
   con frontend, backend y MySQL independientes; puede moverse a otra máquina sin tocar OSAP
   más que la URL y el token.
8. Hay **dos entradas**:
   - **Desde una representación** (botón en su fila): `resource_id` fijo; se conoce ensemble/voz;
     permite asociar y votar.
   - **Desde la ficha de obra** (cabecera): búsqueda genérica por título/compositor, sin
     ensemble ni recurso; solo búsqueda/visualización. **No se selecciona recurso ni se vota**
     desde aquí; para votar se entra por la representación.
9. El **token se pasa con el mismo mecanismo que storage/support**: `Authorization: Bearer` de
   OSAP. El aplicativo valida el token/JWKS de osap-auth; no hay login nuevo. Para leer datos
   públicos de OSAP usa el mismo patrón de token de servicio.
10. Se simplifica: sin catálogo del módulo, sin SQLite en producción, sin selector de recurso en
    la entrada de obra y sin identidades inventadas.

## 1. Estado actual del módulo

- Paquete Python independiente con SQLite para el piloto.
- `global_search.search_global(db_path, song, author, voice, limit)`:
  - voces `all`, `song`, `soprano`, `alto`, `tenor`, `bass`;
  - `all` = 5 búsquedas; `limit` máximo 50;
  - devuelve `video_id`, `video_title`, `url`, `channel`, `voice`, `material_type`,
    `approval_count`, `rejection_count`, `author_votes`, `last_vote` y un `work_id` de su
    catálogo local (puede ir vacío).
- Las funciones de comunidad (`record_promotion`) escriben en la SQLite del módulo; **no se
  usarán en producción**.
- La web local del módulo no se usa como API.

## 2. Modelo de datos del aplicativo (MySQL independiente)

```sql
-- Vídeos de YouTube (metadatos; no se descarga el medio)
youtube_videos (
  video_id         VARCHAR(32) PRIMARY KEY,
  url              VARCHAR(512) NOT NULL,
  title            VARCHAR(512) NOT NULL,
  channel          VARCHAR(255),
  published_at     DATETIME NULL,
  duration_seconds INT NULL,
  material_type    VARCHAR(32) NULL,
  created_at       DATETIME NOT NULL
);

-- Relación explícita: recurso de OSAP <-> vídeo
resource_youtube_videos (
  id              BIGINT PRIMARY KEY AUTO_INCREMENT,
  resource_id     VARCHAR(64) NOT NULL,   -- id de representación de OSAP
  work_id         VARCHAR(64) NOT NULL,   -- contexto de obra de OSAP
  video_id        VARCHAR(32) NOT NULL,
  voice           VARCHAR(16) NOT NULL,   -- soprano|alto|tenor|bass|unknown
  search_query    VARCHAR(512) NULL,
  similarity      DECIMAL(5,4) NULL,
  created_at      DATETIME NOT NULL,
  UNIQUE KEY uq_resource_video_voice (resource_id, video_id, voice),
  KEY ix_work (work_id),
  FOREIGN KEY (video_id) REFERENCES youtube_videos(video_id)
);

-- Voto comunitario: usuario de OSAP, recurso, vídeo y voz
resource_youtube_votes (
  user_id         VARCHAR(64) NOT NULL,   -- id de OSAP (sub del token)
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

- No hay claves foráneas a la BD de OSAP: `work_id`, `resource_id` y `user_id` son
  identificadores externos.
- El aplicativo valida contra la API pública de OSAP que el `resource_id` pertenece al
  `work_id` antes de crear la relación/voto.
- Un vídeo puede asociarse a varias representaciones; el voto es **por representación**.
- Los contadores se calculan desde `resource_youtube_votes`; no se usan los del módulo.
- MySQL propio: credenciales, backups y migraciones independientes.

## 3. Arquitectura

```
OSAP (ficha de obra)
  ├─ botón por representación -> https://videos.openmusicrepository.com/<work_id>?resource=<resource_id>
  └─ botón de obra (genérico) -> https://videos.openmusicrepository.com/<work_id>

Aplicativo YouTube (videos.openmusicrepository.com, despliegue independiente)
  ├─ frontend con la misma estructura/estilo de OSAP
  ├─ backend propio (API /api/youtube/...)
  ├─ MySQL propio (vídeos, relaciones y votos)
  ├─ ai_recogeyoutube.search_global (solo búsqueda)
  ├─ validación del Bearer/JWKS de osap-auth
  └─ YouTube Data API (clave solo servidor)
```

- OSAP no escribe ni lee estas tablas; solo enlaza con `work_id`/`resource_id`.
- El aplicativo obtiene título/compositor y la representación de la API pública de OSAP (con
  token de servicio) o de los parámetros de entrada; el usuario puede corregir título y
  compositor antes de buscar.
- El token de usuario se pasa como a storage/support (`Authorization`); no se implementa otro
  login ni se pide identificador.
- Al estar en otro subdominio/máquina: HTTPS, CORS explícito y token en cabecera; secretos
  (YouTube, MySQL) solo en el servidor del aplicativo.
- El frontend puede reutilizar los tokens de diseño/estructura de OSAP, pero se despliega y
  versiona aparte.

### API del aplicativo

- `POST /api/youtube/search`
  `{work_id, resource_id?, song, author, voice, limit}` → resultados + votos/semejanza.
  Sin `resource_id` devuelve `votable: false`.
- `POST /api/youtube/votes`
  `{work_id, resource_id, video_id, voice, decision, title, url, channel, material_type}`.
  Exige `resource_id` y usuario autenticado.
- `GET /api/youtube/work/{work_id}` (opcional): datos de obra/representaciones desde OSAP.
- Autenticación: Bearer token de OSAP; el backend resuelve `user_id`/`display_name`.

## 4. Flujo de usuario

1. **Entrada por representación** (principal): en cada fila de representación de la ficha,
   botón **«Buscar vídeos»**. Abre `videos.../<work_id>?resource=<resource_id>`.
   - ensemble/voz de la representación precargados y editables;
   - sí permite asociar y votar.
2. **Entrada por obra** (cabecera de la ficha): botón **«Explorar vídeos»**. Abre
   `videos.../<work_id>` sin recurso.
   - búsqueda genérica por título/compositor;
   - sin ensemble y sin selección de recurso;
   - solo ver/reproducir; **no votar**; se indica «entra por una representación para asociar».
3. Cabecera del aplicativo: obra, compositor, volver a OSAP.
4. Formulario precargado y editable: título, compositor, voz (Todas/Canción completa/SATB) y
   límite. En entrada por representación se muestra el ensemble de esa representación.
5. **Buscar** solo a petición; se mezclan resultados del módulo con relaciones/votos del
   aplicativo para esa representación (si existe).
6. Resultados: título, canal, enlace, voz estimada, tipo, semejanza y votos. Abrir/reproducir.
7. Con sesión y `resource_id`: seleccionar vídeo, elegir voz si procede y **Aprobar/Rechazar**;
   se crea la relación resource↔vídeo y se guarda/actualiza el voto.
8. Sin sesión: buscar/ver libre; votar muestra «Inicia sesión en OSAP para valorar».
9. Sin `resource_id`: se puede ver, pero no votar ni asociar.

## 5. Orden de resultados

1. Vídeos con votos del aplicativo para esa representación: aprobaciones desc, rechazos asc,
   total de votos.
2. Vídeos sin votos: semejanza con la consulta (título/compositor/palabras distintivas)
   descendente.
3. Empate: orden del módulo y título.

La semejanza se calcula en el servidor (normalización, solapamiento de tokens, edición/
RapidFuzz si está disponible) y se guarda en `resource_youtube_videos.similarity` para no
recalcular en cada listado.

## 6. Cuota y errores

- `all` = 5 búsquedas × 100 unidades ≈ 500; free ≈ 20 búsquedas `all`/día.
- Cachear el último resultado por obra/voz/representación; no repetir búsquedas idénticas.
- Límite 20–50 resultados; no procesos masivos.
- Distinguir «sin resultados» de «búsqueda fallida»; no devolver listas vacías ante errores.
- Voto: sin sesión, recurso no válido/no pertenece a la obra, vídeo inválido, duplicado
  (actualiza), fallo de MySQL.

## 7. Fases y esfuerzo

1. **Aplicativo + MySQL + migraciones** (1 d).
2. **Backend**: búsqueda, relaciones, votos, validación de resource y tests con dobles (1–2 d).
3. **Frontend** con estructura OSAP + botón/enlace desde la ficha (2–3 d).
4. **Despliegue**: subdominio, MySQL, clave de YouTube, auth/JWKS, CORS (0,5–1 d).

MVP: 5–7 días. No incluye análisis de audio ni V6.

## 8. Decisiones abiertas

- Cómo se entrega el token de usuario al frontend del subdominio `videos`: handoff de un solo
  uso recomendado (código canjeado por el backend) frente a fragmento de URL con el access
  token. En ambos casos se usa `Authorization`/JWKS, no un login nuevo.
- ¿La entrada genérica de obra permite elegir representación después? Propuesta: no; solo
  ver/reproducir. Para asociar/votar se entra por la representación.
- ¿El voto se agrega a nivel de obra además de representación? Propuesta: por representación.
- ¿Embed de YouTube o solo enlace? Privacidad/consentimiento.
- ¿Qué representación se preselecciona si hay varias? La pulsada; no hay selector genérico.
- Estrategia de migraciones y backups del MySQL propio, y separación física de
  frontend/backend/MySQL si se reparte en varias máquinas.
