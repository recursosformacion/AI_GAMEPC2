# API REST — OpenAPI (V3.2)

> **Status: frozen** — congelado antes de la implementación de V3.2 (ADR-0029).
>
> Parte de V3 (Plataforma). Define cómo la API se convierte en un **contrato público
> navegable**. Implementado.

## Principio rector

> **OpenAPI es la representación pública del contrato REST; nunca la fuente de verdad.**

La fuente de verdad siguen siendo los **DTO públicos** definidos en V3.1. OpenAPI se
**genera automáticamente** a partir de ellos. **Nunca se edita manualmente.**

## 1. Objetivo

Proporcionar una especificación OpenAPI completa que permita:

- **explorar** la API;
- **generar clientes**;
- **generar documentación**;
- **validar contratos**;
- servir como **documentación oficial**.

## 2. Relación con V3.1

V3.1 definía:

```
DTO
 ↓
REST
 ↓
FastAPI
```

V3.2 añade:

```
DTO
 ↓
REST
 ↓
OpenAPI
 ↓
Swagger UI
```

**No modifica ningún endpoint.**

## 3. Fuente del contrato

La especificación OpenAPI se genera **exclusivamente** desde:

- los **DTO públicos**;
- las **rutas REST**;
- las **anotaciones del controlador**.

**Nunca** desde documentación escrita.

## 4. Versionado

La especificación corresponde exactamente a `/api/v1/`. Cuando exista `/api/v2/`,
existirá también `/openapi-v2.json`. Las versiones son **independientes**.

## 5. Endpoints adicionales

Se añaden únicamente:

```
GET /openapi.json
GET /docs
GET /redoc
```

**No pertenecen al dominio**: son infraestructura.

**Formato**: la especificación se publica en formato **OpenAPI 3.1.x (JSON)**, compatible
con Swagger UI y ReDoc. **OSAP utiliza OpenAPI 3.1.x; no se aceptan especificaciones
3.0.x.** FastAPI moderno ya soporta 3.1 y evita ambigüedades futuras.

## 6. Swagger UI

Debe mostrar:

- **descripción** del proyecto;
- **versión**;
- **recursos agrupados**: Searches, Jobs, Providers, Knowledge, System.

**No debe mostrar componentes internos.** Nunca aparecerán:

- Matcher
- Ranking
- Merge
- Evidence
- KnowledgeCollector

## 7. Esquemas

Todos los **DTO públicos** aparecen automáticamente. Ejemplos:

```
SearchRequest
SearchResponse
JobResponse
ProviderResponse
KnowledgeResponse
SystemResponse
ErrorEnvelope
SuccessEnvelope
```

## 8. Ejemplos

Todos los endpoints deben incluir **ejemplos**.

Ejemplo `POST /searches`:

**Request**

```json
{
  "query": "Ave Verum KV 618",
  "limit": 10
}
```

**Response** `201` — con ejemplo real.

## 9. Códigos HTTP

Todos los endpoints documentan explícitamente los códigos que correspondan:

```
200 · 201 · 400 · 404 · 422 · 500
```

## 10. Tags

La documentación queda organizada mediante **cinco tags**:

- Searches
- Jobs
- Providers
- Knowledge
- System

## 11. Metadatos

La especificación incluye:

- `title`
- `description`
- `version`
- `license`
- `contact`

Ejemplo: *OSAP REST API — Version 3.1*.

## 12. OpenAPI como contrato

La especificación OpenAPI **constituye la documentación oficial** de la API. **No se
mantiene documentación REST paralela.**

## 13. ¿Qué NO hace V3.2?

V3.2 **no añade**:

- autenticación;
- autorización;
- nuevos endpoints;
- lógica;
- persistencia.

Solo **documenta el contrato existente**.

## 14. ADR-0029 — OpenAPI es un artefacto derivado

Se congelará en el ADR:

> Los contratos públicos se definen mediante los DTO tipados y las rutas REST. La
> especificación OpenAPI se genera automáticamente a partir de esos contratos y **nunca
> se modifica manualmente**. Cualquier cambio en OpenAPI debe originarse en el **código
> del contrato**, no en el fichero generado.

Coherente con la filosofía del proyecto: **el código define el contrato; la
documentación se deriva del contrato.**

---

## 15. Invariantes

- OpenAPI **nunca es la fuente de verdad**; siempre se genera a partir de los contratos
  públicos.
- Toda modificación del contrato REST implica una **modificación automática** de OpenAPI.
- La **ausencia** de un endpoint en OpenAPI implica que **no forma parte** de la API
  pública.
- OpenAPI **no puede documentar** recursos internos del dominio.
- La documentación generada debe ser **determinista**: el mismo código produce la misma
  especificación.

---

## Criterios de aceptación (V3.2)

- OpenAPI **generado automáticamente**;
- **sin edición manual**;
- **Swagger UI** operativo;
- **ReDoc** operativo;
- **todos los DTO visibles**;
- **ejemplos** en todos los endpoints;
- **tags** correctamente agrupados (Searches, Jobs, Providers, Knowledge, System);
- **metadatos completos** (title, description, version, license, contact);
- tests que verifiquen la existencia de `/openapi.json`, `/docs` y `/redoc`;
- la especificación OpenAPI **valida sin errores** mediante un **validador OpenAPI
  estándar**;
- **la generación de OpenAPI forma parte de la suite de tests** (`test_openapi_generation.py`):
  genera correctamente, valida correctamente, contiene todos los DTO, todos los tags y
  todos los ejemplos;
- **sin modificar el dominio V2 ni los contratos V3.1**.

---

## Plan de entrega

1. **V3.2.a — Diseño** (este documento): congela cómo se convierte la API en un
   contrato público navegable.
2. **ADR-0029** (OpenAPI es un artefacto derivado).
3. **Implementación**: metadatos, tags, ejemplos, códigos HTTP y endpoints
   `/openapi.json`, `/docs`, `/redoc` sobre el contrato V3.1 existente.
4. **Tests**: existencia y contenido de los tres endpoints.
