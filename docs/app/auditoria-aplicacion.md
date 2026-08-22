# Auditoría de aplicación — OSAP (osap-api)

**Fecha:** 2026-08-20  
**Proyecto:** osap-api  
**Versión documentada:** V3.1  
**Objetivo:** Detectar errores, incumplimientos respecto a la documentación y riesgos en el código y configuración del proyecto.

---

## Resumen ejecutivo

La aplicación cumple con la arquitectura hexagonal documentada y respeta la separación de responsabilidades entre capas. Sin embargo, se detectaron **3 hallazgos críticos de seguridad**, **3 incumplimientos altos respecto a la documentación** y varias deudas técnicas de robustez. No se pudo ejecutar el linter ni la suite de tests porque las dependencias de desarrollo (`ruff`, `mypy`, `pytest`) no están instaladas en el entorno actual.

---

## Hallazgos críticos — Seguridad

| # | Hallazgo | Ubicación |
|---|----------|-----------|
| 1 | **Secrets commiteados en `osap.toml`**: `password = "2027osapdb"` y `client_secret = "NzA6..."` están en el repositorio. La documentación indica que en producción el secreto va por variable de entorno, pero en desarrollo sigue versionado. | `osap.toml:13`, `osap.toml:28` |
| 2 | **Secrets en tests y scripts de prueba**: contraseñas hardcodeadas en `test_op_store.py` y tres scripts en `_pruebas/`. | `tests/osap/test_op_store.py:13,20`, `_pruebas/*.py` |
| 3 | **Token hardcodeado en producción code**: `service_token = "dev-storage-token"` en `platform.py`. Si se despliega sin override, se usa un token de servicio predecible. | `src/osap/api/platform.py:1215` |

---

## Hallazgos altos — Incumplimientos respecto a documentación

| # | Hallazgo | Ubicación / Nota |
|---|----------|-----------------|
| 4 | **CLI `osap` no documentada**: el entrypoint definido en `pyproject.toml` (`osap = "src.osap.cli.main:entrypoint"`) no aparece en `docs/osap/scripts.md`. | `pyproject.toml:16`, `docs/osap/scripts.md` |
| 5 | **`osap.production.toml` con `host = "127.0.0.1"`**: aunque la documentación dice que en prod el secreto va por env, el host de BD está hardcodeado a localhost, lo que impide despliegues distribuidos sin editar el fichero. | `osap.production.toml:6` |
| 6 | **`maintenance.html` en `script/`**: archivo estático en la carpeta de scripts, sin documentar y no ejecutable. | `script/maintenance.html` |

---

## Hallazgos medios — Calidad de código y robustez

| # | Hallazgo | Ubicación |
|---|----------|-----------|
| 7 | **Captura genérica de excepciones sin logging** en puntos críticos de arranque y API. Algunos usan `# noqa: BLE001`, pero otros no. | `src/osap/api/platform.py:75,119`, `src/osap/application/metadata_normalizer.py:132`, `src/osap/infrastructure/storage/work_store.py:46` |
| 8 | **Fallbacks silenciosos con `or ""`** que enmascaran configuraciones ausentes (p. ej., `client_secret=config.service_client_secret or ""`). Si falta el secreto, el sistema continúa en lugar de fallar. | `src/osap/bootstrap/wiring.py:164,283` |
| 9 | **Verificaciones estándar no ejecutables en este entorno**: `ruff`, `mypy` y `pytest` no están instalados, por lo que no se puede validar cumplimiento de reglas de estilo, tipos ni tests. | — |

---

## Hallazgos bajos — Configuración y entorno

| # | Hallazgo | Ubicación |
|---|----------|-----------|
| 10 | **Proxy de Vite en `web/vite.config.ts`** contradice la regla de no usar `npm run dev`. Si un desarrollador lo ejecuta, se conecta a `127.0.0.1:8001`, pero la app real se sirve desde Apache. | `web/vite.config.ts:9` |
| 11 | **`_pruebas/` en el repo**: carpeta con scripts ad-hoc de auditoría que deberían estar fuera del control de versiones o documentarse como herramientas de desarrollo. | `_pruebas/` |

---

## Verificaciones positivas

- **Arquitectura hexagonal respetada**: `domain/` no importa de `infrastructure/` ni `api/`. Sin violaciones detectadas.
- **Frontend no servido desde FastAPI**: no hay `StaticFiles` montados en `platform_app.py`.
- **Auth deshabilitado en V3.1**: el código confirma que Bearer está preparado pero deshabilitado.
- **Proveedores cableados coinciden con documentación**: activos `imslp`, `openscore`, `omr`, `mutopia`, `musicbrainz`, `rism`, `local`. Los definidos pero no cableados (`cpdl`, `musescore`, `kernscores`, `freescores`, `musopen`) coinciden con los bloqueos documentados.
- **`public_domain` tri-estado**: definido como `bool | None` en dominio y DTOs.
- **Scripts documentados**: los 26 scripts en `script/` tienen docstring y están referenciados en `docs/osap/scripts.md`.
- **Separación de responsabilidades**: osap-api no accede a BD de storage directamente; usa API y tokens de servicio.

---

## Recomendaciones prioritarias

1. Mover `osap.toml` a `.gitignore` o usar plantilla (`osap.toml.example`) y cargar configuración real desde variables de entorno.
2. Añadir la CLI `osap` a `docs/osap/scripts.md`.
3. Eliminar `maintenance.html` de `script/` o moverlo a `web/`.
4. Revisar los `except Exception:` sin `# noqa` para añadir logging específico o capturar excepciones concretas.
5. Instalar dependencias de desarrollo (`ruff`, `mypy`, `pytest`) para poder ejecutar las verificaciones estándar.
