# ADR-0029 – OpenAPI es un artefacto derivado (V3.2)

## Estado

Aceptado. Congela cómo se convierte la API en un contrato público navegable (V3.2).

## Principios

- **Los contratos públicos se definen mediante los DTO tipados y las rutas REST.**
- **La especificación OpenAPI se genera automáticamente** a partir de esos contratos y
  **nunca se modifica manualmente**.
- Cualquier cambio en OpenAPI debe originarse en el **código del contrato**, no en el
  fichero generado.
- **OpenAPI no es la fuente de verdad**; es la representación pública derivada.
- **OpenAPI 3.1.x obligatorio**; no se aceptan especificaciones 3.0.x.
- La generación es **determinista** (el mismo código produce la misma especificación).

## Contexto

V3.1 definió los DTO públicos y las rutas REST. V3.2 los convierte en un contrato público
navegable (Swagger UI, ReDoc, clientes, validación). La documentación no puede ser un
documento mantenido a mano, sino una **parte del producto** derivada del contrato.

## Decisión

- OpenAPI se genera exclusivamente desde los **DTO públicos**, las **rutas REST** y las
  **anotaciones del controlador**; nunca desde documentación escrita.
- Se exponen `/openapi.json`, `/docs` (Swagger UI) y `/redoc`.
- Metadatos completos: `title`, `description`, `version`, `license`, `contact`.
- Cinco tags: Searches, Jobs, Providers, Knowledge, System.
- Ejemplos en todos los endpoints y `request_id` en todos los ejemplos.
- No se documentan componentes internos (Matcher, Ranking, Merge, Evidence,
  KnowledgeCollector, KnowledgeMiner).
- La generación y validación forman parte de la suite de tests.

## Consecuencias

- La documentación es siempre coherente con el código (no hay deriva).
- Un endpoint ausente en OpenAPI no forma parte de la API pública.
- Cambiar el contrato implica cambiar automáticamente OpenAPI.
- FastAPI es únicamente infraestructura; el contrato vive en los DTO y las rutas.
