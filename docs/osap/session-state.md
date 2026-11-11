# Estado de sesión (memoria persistente)

Actualizado: 2026-11-11. Leer al empezar una sesión compactada.

## Producción

- `osap-api`, `osap-auth`, `osap-storage`, `osap-support`: **5.9.0** desplegados; migraciones de auth 0011–0013 y de storage/support aplicadas; salud OK.
- Satélites: vídeos **0.5.1**, blog **1.2.1**, `ai_publicidad` **0.6.0**, `ai-importacion` **0.3.0**.
- Login con Google corregido (cliente nuevo `571610870089…`); `config.yaml` con backup `config.yaml.bak-20261110-google-fix`.
- `FUNDING.yml` publicado en los 7 repos (`github: [recursosformacion]` + `custom: [https://app.openmusicrepository.com/support]`).
- `osap-ai-enrich` en pausa por cuota de Gemini hasta ~15:33 UTC del 2026-11-11.

## Commits locales pendientes de subir

- `osap-api`: 5.9.0, hueco de anuncios, aviso legal/retirada, docs de licencias.
- `osap-auth`: 5.9.0, entidades/teléfono, correo de entidad y tipos nuevos.
- `osap-storage`/`osap-support`: release 5.9.0 y lint de scripts.
- `osap-videos`/`osap-blog`: versiones 0.5.1 y 1.2.1.
- `ai-importacion`: política de licencias y revalidación (rama `feature/github-download-analysis`).
- No se han subido tags de release.

## Pendiente funcional

- **5.10.0**: correo de entidad (migración `0014_entities_email`) implementado y probado, sin desplegar ni etiquetar.
- **Aviso legal**: descargo de agregador y retirada rápida implementados; sin desplegar (rebuild + publicar SPA).
- **Importación GitHub**: receptor JSON `osap-resource-import/1.1` por construir; campos de procedencia/bloqueo en Storage y redirección a origen. Diseño en `docs/osap/licensing-and-takedown.md`.
- Crear alias `abuso@openmusicrepository.com` (el texto legal también usa `admin@`).

## Reglas operativas

- No desplegar ni empujar tags/releases sin autorización explícita; las correcciones de producción sí.
- Tests dirigidos por defecto; suites completas en segundo plano.
- Evitar volcar HTML/JSON completos en la conversación; usar resúmenes y `-q`.
- Versiones coordinadas: cuatro `pyproject.toml` + `web/package.json`, verificar con `script/check-versions.ps1`.
- Documentación de referencia: `docs/ads-integration.md`, `docs/osap/licensing-and-takedown.md`, `docs/osap/versioning.md`.
