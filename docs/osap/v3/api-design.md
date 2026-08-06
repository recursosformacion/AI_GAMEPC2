# API REST — Diseño (V3.1)

> **Status: frozen** — congelado antes de la implementación de V3.1 (ADR-0028).
>
> Parte de V3 (Plataforma). Define los contratos de la API REST de OSAP. Implementado
> como parte de V3.1.b.

## Principio rector

> **La API no implementa lógica. Expone casos de uso del dominio ya existentes.**

La API hace exactamente lo mismo que un Provider:

```
HTTP
     │
REST Controller
     │
Application Service
     │
OSAP Domain
```

**Nunca**:

```
HTTP
     │
Controller
     │
WorkMatcher
```

Eso estaría **prohibido**: ningún componente interno del dominio se expone directamente.

---

## Estabilidad del contrato

**Los contratos REST son API pública.** La evolución de un endpoint solo puede realizarse
de forma **compatible hacia atrás** (backward compatible). Los **cambios incompatibles
requieren una nueva versión de la API** (`/api/v2`) y un **ADR**.

Esto encaja con la filosofía de **contratos congelados** de V2: la API evoluciona sin
romper a los consumidores.

---

## 1. Objetivo

Exponer el dominio de OSAP (completo en V2.2, `v2.2.0`) a través de una API REST estable.
La API **no añade lógica**: cada recurso corresponde a un **caso de uso** ya soportado por
el dominio, usando Application Services.

## 2. Organización de V3

```
V3 — Plataforma
├── V3.1  API REST          ← diseño actual (V3.1.a)
├── V3.2  OpenAPI / Swagger
├── V3.3  Cliente Web
├── V3.4  Autenticación
└── V3.5  Administración
```

**La API es el primer paso** (V3.1).

## 3. Filosofía de la API

- La API **no expone los componentes internos**. Nunca existiría `POST /matcher`,
  `POST /ranking` ni `POST /merge`: son **detalles internos** del dominio.
- La API debe **hablar el lenguaje del usuario**, no el de la implementación.
- Lo que se expone son **casos de uso**, no primitivas del dominio.

## 4. Recursos principales

Al principio, **nada más** que estos cinco recursos, todos bajo el prefijo `/api/v1/`:

| Recurso | Descripción |
|---------|-------------|
| `/api/v1/searches` | Crear/consultar búsquedas (el más importante). |
| `/api/v1/jobs` | Orquestar tareas de larga duración (V2.2.c). |
| `/api/v1/providers` | Estado de los proveedores. |
| `/api/v1/knowledge` | Conocimiento aprendido (solo lectura). |
| `/api/v1/system` | Salud, versión, estadísticas. |

## 5. Search

El recurso más importante. En REST, una búsqueda es un **recurso** que se crea y se
consulta.

```
POST /api/v1/searches          # crea una búsqueda → 201 Created + Location
GET  /api/v1/searches/{id}     # recupera el resultado
```

`POST /api/v1/searches` crea una búsqueda y el servidor devuelve:

- **`201 Created`**
- **`Location: /api/v1/searches/xxxxxxxx`**

Hoy parece innecesario; dentro de un año, cuando haya búsquedas lentas o distribuidas,
ya estará resuelto.

**Request** (contrato tipado, ver §SearchRequest/SearchResponse)

```json
{
  "query": "Ave Verum KV 618",
  "limit": 10
}
```

**Response**

```json
{
  "success": true,
  "request_id": "...",
  "data": {
    "search_id": "...",
    "results": [
      {
        "work": {},
        "representation": {},
        "score": 0.0,
        "evidence": {}
      }
    ]
  }
}
```

**Observación clave**: la respuesta **no** devuelve `MatchResult`, `RankingResult` ni
`MergeResult`. Eso es interno. Devuelve el **resultado final**: obra, representación
elegida, puntuación y evidence (para explicar la decisión).

### `SearchRequest` y `SearchResponse`

El contrato no es JSON implícito: se definen explícitamente dos **Value Objects** tipados.

- **`SearchRequest`** — `query`, `limit` (y opciones futuras).
- **`SearchResponse`** — `search_id`, `results` (work + representation + score +
  evidence), `request_id`.

Igual que `MatchResult`, `RankingResult`, `MergeResult` y `EvidenceResult`, la API
trabaja con **objetos tipados**, no con diccionarios libres.

## 6. Jobs

Apoyado sobre la arquitectura de **V2.2.c**.

```
GET  /api/v1/jobs
POST /api/v1/jobs            # body: { "type": "provider-sync" }
GET  /api/v1/jobs/{id}
```

`POST /api/v1/jobs` recibe el tipo en el cuerpo, de modo que la API **no necesita un
endpoint nuevo** cada vez que aparezca un Job:

```json
{ "type": "provider-sync" }
```

## 7. Knowledge

**Solo lectura.**

```
GET /api/v1/knowledge/observations
GET /api/v1/knowledge/facts
GET /api/v1/knowledge/suggestions
```

Si existe `KnowledgeObservation` en el dominio, debe poder consultarse.

**Nunca** `POST /knowledge`: el conocimiento **no se modifica manualmente desde la API**.
(La aplicación de sugerencias es humana, vía V3.5 / Knowledge Review.)

> **Nota de evolución (V3.2)**: en V3.1 el conocimiento usa un `KnowledgeStore` en
> memoria. En V3.2 se introducirá un **`IKnowledgeRepository`** para desacoplar
> `API → Knowledge Service → Repository → SQLite/Postgres`, sin cambiar este contrato.

## 8. Providers

Solo **estado**: capacidades y última sincronización.

```
GET /api/v1/providers
GET /api/v1/providers/{id}
GET /api/v1/providers/{id}/status
```

Nada más. `/status` se añade porque probablemente el estado crecerá.

## 9. System

Se separa **salud** de **estadísticas**, y se añaden *probes* de vida/disponibilidad:

```
GET /api/v1/system/health
GET /api/v1/system/ready
GET /api/v1/system/live
GET /api/v1/system/version
GET /api/v1/system/statistics
```

`/ready` y `/live` (como Kubernetes) inicialmente responden igual.

## 10. Versionado

Desde el principio: **todos** los recursos bajo el prefijo `/api/v1/`:

```
/api/v1/searches
/api/v1/jobs
/api/v1/providers
/api/v1/knowledge
/api/v1/system
```

**Nunca** `/api/search` (sin prefijo de versión).

## 11. OpenAPI

La especificación **OpenAPI debe generarse automáticamente** (desde el contrato de la
API, p. ej. FastAPI). **No** documentación escrita a mano. (V3.2 materializa Swagger/UI.)

**OpenAPI constituye el contrato oficial de la API.** La especificación deja de ser
documentación: pasa a ser **el contrato**. Cualquier cambio en la API debe reflejarse
primero en OpenAPI.

## 12. Autenticación

**No en V3.1.** Se deja **preparada** (`Authorization: Bearer ...`), pero inicialmente
**deshabilitada**. Se activa en V3.4.

## 13. Respuesta uniforme

Todas las respuestas siguen el mismo patrón y **siempre** incluyen `request_id` (en
cualquier endpoint), lo que simplifica logs, tracing, soporte y debugging.

**Éxito**

```json
{
  "success": true,
  "request_id": "...",
  "data": {}
}
```

**Error**

```json
{
  "success": false,
  "request_id": "...",
  "error": {
    "code": "INVALID_QUERY",
    "message": "Query cannot be empty",
    "details": {}
  }
}
```

El error incluye `code`, `message` y `details` (siempre disponible; nunca cuesta tenerlo).

## 14. Lo que la API NO expone

No se expone **ninguno** de estos:

- Canonicalizer
- Matcher
- Ranking
- Merge
- Evidence
- KnowledgeCollector
- KnowledgeMiner

Todo eso pertenece al dominio. La API **únicamente expone casos de uso**.

## 15. Plan de entrega

1. **V3.1.a — Diseño de la API REST** (este documento): contratos, recursos,
   versionado, respuestas, errores, OpenAPI.
2. **Congelación mediante un ADR**.
3. **Implementación** de la API.

**Recomendación clave**: no empezar implementando directamente FastAPI. Primero:

- **Diseñar los DTO públicos** (`SearchRequest`, `SearchResponse`, `JobResponse`,
  `ProviderResponse`, `KnowledgeResponse`, `SystemResponse`, `ErrorResponse`) como
  Value Objects tipados.
- **Congelar esos contratos mediante un ADR.**
- Después **implementar FastAPI para serializar esos DTO**.

Los **DTO públicos forman parte del contrato REST y son independientes del modelo de
dominio**: **no se reutilizan directamente los Value Objects internos del dominio**. Es
una decisión arquitectónica importante: evita que un cambio en, p. ej., `WorkDescriptor`
rompa `SearchResponse`.

Así el framework queda **completamente desacoplado** del contrato de OSAP: la API es
estable y el framework es un detalle de infraestructura sustituible.

4. Después: **V3.2** (Swagger/OpenAPI) y **V3.3** (interfaz web).

Repetir la disciplina de V2 (diseño → congelación → implementación) para que la API tenga
la misma calidad y estabilidad que el dominio.

---

## Criterios de aceptación (V3.1)

- **contratos congelados** antes de implementar;
- la API **no modifica ni expone** el dominio;
- solo los cinco recursos principales, todos bajo `/api/v1/` (`searches`, `jobs`,
  `providers`, `knowledge`, `system`);
- `SearchRequest` y `SearchResponse` como **DTOs tipados** (no JSON implícito);
- versionado `/api/v1/` desde el principio, sin excepciones;
- respuestas uniformes con **`request_id` obligatorio** y error con `code`/`message`/
  `details`;
- **OpenAPI generada automáticamente** y constituye **el contrato oficial** de la API;
- **estabilidad del contrato**: evolución solo *backward compatible*; cambios
  incompatibles → nueva versión (`/api/v2`) + ADR;
- auth **preparada y deshabilitada** en V3.1;
- `POST /knowledge` **prohibido**;
- **sin exponer** componentes internos del dominio;
- tests deterministas;
- **sin modificar el núcleo** V2 (contratos congelados intactos).
