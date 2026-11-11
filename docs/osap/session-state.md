# Estado de sesión (memoria persistente)

Actualizado: 2026-11-11. Leer al empezar una sesión compactada.

## Producción

- `osap-api`, `osap-auth`, `osap-storage`, `osap-support`: **5.10.0** desplegados; auth con migración 0014; salud OK.\n- **Chorus 0.2.0 en producción**: https://chorus.openmusicrepository.com (servicio `chorus` en 9600, SQLite piloto, editor en `/muse/`, OIDC `chorus-web`).
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

## Chorus (`ai_chorus`)

- Runtime FastAPI + web estática, SQLite piloto; **33 tests** en verde.
- Piloto verificado en local contra `http://osap-app` y `http://osap-auth/auth-api`: health 200, rutas sin token 401, proxy legal 200, login inválido 401.
- **Login OIDC PKCE** con el cliente `chorus-web`: la pantalla de Auth ofrece Google, GitHub, correo y alta de cuenta. Flujo probado hasta `authorize` y callback inválido (400); falta completar con una cuenta real.
- Audiencia: se usa la predeterminada `osap-api` (decisión CH-016); `chorus-api` queda como endurecimiento.
- Implementado: propiedad de obras (`works.owner_sub`), endpoint de integridad SHA-256, biblioteca personal (`library_items`) y colecciones; listado y guardado de referencias en la web; envoltorio del editor con vuelta a Chorus.
- Licencias: la API resuelve la licencia desde storage (representación → obra) en una consulta batch; el índice no la almacena. Etiquetas normalizadas en `licenses.py` (PDMX/CPDL/CC).
- Biblioteca: búsqueda por texto (`GET /api/v1/library?q=`) y fachada OSAP `/api/v1/workspace/library` con el token del usuario; botón “Guardar” en la ficha de obra. Pendiente: probar el login real y el puente a MuseEncore, integración con MuseScore de escritorio, PDF→MXL (OMR), funciones de grupo y motor definitivo. Backlog en `Chorus/docs/backlog.md`. Commits locales sin subir.

## Reglas operativas

- No desplegar ni empujar tags/releases sin autorización explícita; las correcciones de producción sí.
- Tests dirigidos por defecto; suites completas en segundo plano.
- Evitar volcar HTML/JSON completos en la conversación; usar resúmenes y `-q`.
- Versiones coordinadas: cuatro `pyproject.toml` + `web/package.json`, verificar con `script/check-versions.ps1`.
- Documentación de referencia: `docs/ads-integration.md`, `docs/osap/licensing-and-takedown.md`, `docs/osap/versioning.md`.
