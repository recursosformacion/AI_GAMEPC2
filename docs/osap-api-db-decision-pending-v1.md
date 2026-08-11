# OSAP — BD propia de osap-api: decisión pendiente + inventario (v1)

**Estado:** DECISIÓN ARQUITECTÓNICA PENDIENTE (probable aprobación, a confirmar tras el inventario).
**Formulación propuesta:**

> BD propia de osap-api para **estado operativo persistente**; **nunca como copia ni caché
> autoritativa del catálogo de osap-storage**.

**Objeto:** decidir si osap-api adquiere una base de datos propia y qué contiene. Antes de
implementarla se realiza el inventario de todo lo que osap-api guarda hoy en **YAML, JSON,
memoria o configuración**, clasificado en A/B/C/D.

---

# 1. Principio de propiedad de datos

- Los **compositores, obras, votos y sus estadísticas** son datos de **osap-storage**. osap-api no
  los duplica: los consulta por contrato.
- La BD de osap-api, si existe, contiene **solo estado operativo del propio proceso** (sugerencias,
  proveedores activos, configuraciones, métricas). Nunca una copia del catálogo.

---

# 2. Inventario de lo que osap-api guarda hoy

## 2.1 YAML (configuración declarativa)

`providers/*/` — un directorio por proveedor con `provider.yaml`, `endpoints.yaml`,
`mapping.yaml`, `resources.yaml` (y `transforms.yaml` en IMSLP):
`cpdl, freescores, imslp, kernscores, musescore, musicbrainz, musopen, mutopia, omr, openscore`
+ catálogo local en `library_root`.

## 2.2 Ficheros de estado / JSON

- `src/osap/api/osap_state_source_suggestions.json` → sugerencias de fuente persistidas (runtime).
- `osap_credentials.db` → almacén de credenciales (SecureCredentialStore).
- `osap_library/` → catálogo local (ficheros/partituras).

## 2.3 Configuración (`osap.toml` + env + `Configuration`)

`confidence_threshold`, `max_processing_time`, `default_quality_level`, `default_output_format`,
`default_library`, `connectivity_available`, `library_root`, `imslp_base_url`,
`resource_auto_install` (+ umbral), `github_token/timeout/retries/cache`, `openscore_repos`,
`imslp_verify_ssl`, `omr_base_url`, `omr_api_key`, `dev_mode`, `service_client_id/secret`,
`admin_client_id/secret`, `osap_auth_token_url`, `osap_auth_base_url`, `credentials_path`,
`credentials_key`.

## 2.4 En memoria (PlatformApi + stores)

- `SessionSources` (fuentes de sesión).
- `PlatformApi._searches` (caché de búsquedas), `_jobs` (trabajos), `_representations` (caché de
  descarga), `_source_suggestions` (persistido en JSON), `_job_counter`.
- `KnowledgeStore` (observaciones/sugerencias), `InMemoryCache`, `InMemoryJobEngine`,
  `InMemoryUserProfileStore`, `InMemoryMetricsCollector`, `DuplicateResolver`, `MergeEngine`.

---

# 3. Clasificación A / B / C / D

## A — Debe persistir en osap-api (estado operativo propio)

| Ítem | Motivo |
|---|---|
| Sugerencias de fuente (hoy JSON) | Estado operativo del proceso; pendiente de decisión del admin. → a BD |
| Proveedores añadidos/activados por el flujo "Añadir fuente" | Registro operativo creado en runtime (distinto del YAML de base). → a BD |
| Configuraciones de runtime por usuario/entorno | Ajustes persistidos, no versionables en código |
| Métricas/contadores acumulados (si se quieren históricos) | Solo si interesa conservarlas |

## B — Sigue siendo configuración / código (no a BD)

| Ítem | Motivo |
|---|---|
| `providers/*.yaml` (provider/endpoints/mapping/resources) | Configuración declarativa versionada; base de proveedores |
| Campos de `Configuration` / `osap.toml` / env | Configuración, no estado |
| Tabla de compositores canónicos / aliases (resources/canonical) | Datos de referencia versionados |

## C — Pertenece a osap-storage (osap-api NO lo guarda)

| Ítem | Motivo |
|---|---|
| Compositores y sus `review_status`, `works_count` | Dato de storage |
| Obras y su vínculo `composer_id` | Dato de storage |
| Votos y estadísticas de obra/compositor | Dato de storage |
| (Debate abierto) registro de proveedores/fuentes del catálogo | Podría vivir en storage por ser dominio de catálogo; si se decide, moverlo de B a C |

## D — Realmente no necesita persistencia

| Ítem | Motivo |
|---|---|
| `SessionSources` | Por sesión; efímero |
| Cachés (`_searches`, `_representations`, `InMemoryCache`) | Reconstruibles |
| `_job_counter` | Derivado del registro de trabajos |
| `KnowledgeStore` en memoria | Efímero (o → A si se quiere persistir) |

---

# 4. Conclusión / próximos pasos

- **La BD NO contiene** compositores, obras ni votos (nunca copia del catálogo de storage).
- **Candidatos claros a la BD (A):** sugerencias de fuente y proveedores añadidos en runtime;
  métricas/config de runtime si interesan.
- Antes de implementar: confirmar clasificación de **proveedores** (¿B o C?), y decidir si
  `KnowledgeStore`/métricas van a A o D.
- Mantener `providers/*.yaml` y `Configuration` fuera de la BD (B).

*Decisión pendiente v1 (2026-08) — formulación propuesta; pendiente de confirmar el inventario.*
