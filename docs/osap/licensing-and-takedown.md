# Licencias, alojamiento y retirada de contenido

Documento de diseño para incorporar material adquirido desde GitHub mediante
`ai-importacion`. Define qué se guarda, cuándo se puede alojar un fichero, cómo se
revisa la licencia y qué ocurre cuando el titular la cambia o reclama derechos.

## 1. Principio

OpenMusicRepository actúa como agregador automatizado de buena fe: cataloga
metadatos públicos y licencias **declaradas por el repositorio de origen**. No
verifica la licencia de cada fichero ni sustituye una revisión jurídica.

- Se puede **catalogar** un recurso con independencia de su licencia.
- Solo se **aloja** el fichero cuando la licencia declarada permite redistribuirlo.
- Si no hay licencia o deja de permitirlo, el fichero se bloquea y la descarga se
  redirige al origen para que el usuario decida bajo su responsabilidad.

## 2. Datos de origen y licencia

`ai-importacion` exporta `osap-resource-import/1.1` con estos campos relevantes:

```json
{
  "source": {
    "provider": "github",
    "repository": "owner/repo",
    "repository_url": "https://github.com/owner/repo",
    "default_branch": "main",
    "file_path": "scores/obra.mxl",
    "file_url": "https://github.com/owner/repo/blob/main/scores/obra.mxl",
    "download_url": "https://raw.githubusercontent.com/...",
    "git_blob_sha": "…",
    "license": {
      "spdx": "cc-by-4.0",
      "name": "Creative Commons Attribution 4.0",
      "url": "https://spdx.org/licenses/CC-BY-4.0.html",
      "scope": "repository_declared_license",
      "verified_for_file": false,
      "status": "hostable",
      "policy_version": "2026-11-11",
      "checked_at": "2026-11-11T09:00:00+00:00",
      "previous_spdx": null,
      "changed_at": null
    }
  }
}
```

Estados de `source.license.status`:

| Estado | Significado | Alojamiento |
| --- | --- | --- |
| `hostable` | Licencia reconocida que permite redistribuir | Sí |
| `link_only` | Licencia conocida que no permite redistribuir | No: enlace al origen |
| `unknown` | Sin licencia declarada o no reconocida | No: enlace al origen |

La lista de licencias hospedables vive en `ai_importacion/app/license_policy.py`
(`HOSTING_ALLOWED_SPDX`). Cambiarla exige revisar este documento y la política de
revalidación.

## 3. Recepción en OSAP (fase de importación)

El receptor debe validar, para cada documento:

1. `schema` admitido y `resource_key` estable.
2. `source.provider`, `source.repository`, `source.file_path` y
   `source.download_url` no vacíos.
3. `source.license.status` presente. Si falta, se trata como `unknown`.
4. `file.sha256` con formato válido y tamaño por debajo del límite.

Reglas:

- Un documento sin origen verificable se rechaza (no se importa).
- Un recurso `hostable` puede descargarse y publicarse; el fichero se sube a
  Storage y queda disponible en `works_resources`.
- Un recurso `link_only` o `unknown` se cataloga **sin fichero alojado**: la ficha
  muestra la licencia, el origen y un botón “Descargar en GitHub”.
- Nunca se publica un fichero cuyo estado no sea `hostable`.

## 4. Revalidación periódica

`ai-importacion` revisa la licencia declarada de cada repositorio con
`python -m app.license_recheck --days 7 --limit 50` (cron diario). Guarda historial
en `github_license_checks` y actualiza el repositorio con `license_status`,
`license_checked_at`, `license_previous_spdx` y `license_changed_at`.

Cadencia y límites:

- Revisión por defecto: cada 7 días por repositorio, con un máximo diario para no
  agotar la cuota de GitHub.
- `GITHUB_TOKEN` es opcional; sin token la cuota es menor y la cola avanza más
  despacio.
- Un fallo de red o `403` no cambia el estado: se reintenta en la siguiente pasada.
- Un `404` (repositorio borrado o privado) se trata como `unknown`: deja de
  alojarse.

Cuando el estado cambia a `link_only` o `unknown`, el siguiente paquete JSON lo
refleja y la reconciliación de OSAP debe:

1. Marcar el recurso como `blocked` (deja de servirse el fichero).
2. Mantener la ficha, los metadatos, la licencia anterior y la fecha de cambio.
3. Redirigir la descarga a `source.file_url` o `source.download_url`.
4. Registrar el cambio en el historial del recurso.

La vuelta a `hostable` **no reanuda el alojamiento automáticamente**: requiere
revisión y nueva descarga del fichero.

## 5. Modelo de datos previsto en Storage

Añadir a `works_resources` (o a una tabla `resource_provenance` si se prefiere
separar la trazabilidad):

| Campo | Tipo | Uso |
| --- | --- | --- |
| `source_provider` | varchar | `github` |
| `source_repository` | varchar | `owner/repo` |
| `source_path` | varchar | ruta dentro del repositorio |
| `source_url` | varchar | URL pública del fichero |
| `source_download_url` | varchar | URL directa usada en la descarga |
| `license_spdx` | varchar | licencia declarada |
| `license_status` | varchar | `hostable` / `link_only` / `unknown` |
| `license_checked_at` | datetime | última comprobación |
| `license_previous_spdx` | varchar | licencia anterior |
| `license_changed_at` | datetime | último cambio detectado |
| `policy_version` | varchar | versión de la política aplicada |
| `hosting_status` | varchar | `hosted` / `blocked` |
| `blocked_at` | datetime | fecha de bloqueo |
| `block_reason` | varchar | motivo |

Estados de `hosting_status`:

- `hosted`: fichero en Storage y servido por OSAP.
- `blocked`: fichero no servido; la descarga apunta al origen.
- `link_only`: no existe copia local; solo enlace.

## 6. Retirada rápida (Notice and Takedown)

Canal visible: **abuso@openmusicrepository.com** y
`admin@openmusicrepository.com` (este último ya figura en el aviso legal). La
notificación debe incluir:

1. Identificación del contenido (URL de OSAP y, si existe, identificador).
2. Identidad y legitimación del reclamante.
3. Derecho supuestamente infringido y base de la reclamación.
4. Documentación acreditativa y datos de contacto.

Procedimiento:

1. Acuse de recibo y **bloqueo cautelar inmediato** cuando la reclamación sea
   verosímil, sin perjuicio de la plataforma.
2. Comprobación con el origen y la licencia declarada.
3. Retirada definitiva o restauración motivada, con aviso al reclamante y al
   aportante.
4. Registro de la incidencia (fecha, contenido, decisión y evidencia).

La retirada no elimina la ficha catalográfica si el problema es solo de licencia:
se bloquea el fichero y se enlaza al origen. Si la reclamación afecta a los
metadatos, se retira también la ficha.

## 7. Fases de implementación

1. **Hecho (ai-importacion 0.3.0)**: política de licencias, revalidación con
   historial y campos nuevos en el JSON.
2. **Siguiente**: receptor del paquete JSON en OSAP, con dry-run, idempotencia y
   validación de origen/licencia.
3. **Después**: campos de procedencia en Storage, bloqueo y redirección de
   descargas; panel de cambios de licencia y cola de revisión.
4. **Legal**: aviso de agregador y retirada rápida en el aviso legal/TOS
   (ver `web/src/pages/legal/LegalPages.tsx`).

## Resolución de la licencia en la API

El índice **no almacena licencias**: solo conceptos buscables. Al construir la respuesta, el
proveedor `index` recoge los `resource_id` de los resultados y hace **una consulta batch** a
storage:

- `representations.representations_license` (edición) con respaldo de `works.works_license`.
- Devuelve `license`, `license_url` y `license_source` en el `metadata` de cada representación.
- `licenses.py` normaliza los valores heredados: `publicdomain`/`Public Domain` → dominio
  público; `cc-zero` → CC0 1.0; `CPDL`; `Personal`; variantes CC BY/BY-SA/BY-NC/BY-NC-SA/BY-NC-ND.
- Los marcadores de corpus (`PDMX`) y los textos sucios se descartan; si no hay licencia
  reconocible, la UI muestra «no indicada» en lugar de inventarla.
- IMSLP no tiene licencia en storage (NULL); seguirá sin indicar hasta capturar su estado de
  copyright.

La consulta es una sola por búsqueda (hasta `max_results`), no una por resultado.
