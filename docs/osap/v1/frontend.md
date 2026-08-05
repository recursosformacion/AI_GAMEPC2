# OSAP — Frontend React (contrato)

El frontend React **no se escribe todavía**. Este documento define el contrato
entre la futura interfaz web y la API pública de OSAP. Cada pantalla se mapea a
**casos de uso del dominio** y consume únicamente la API REST + eventos; nunca
accede a infraestructura.

## Pantallas y casos de uso

| Pantalla        | Caso de uso                     | API                              | Eventos consumidos       |
|-----------------|---------------------------------|----------------------------------|--------------------------|
| Dashboard       | Resumen del sistema             | `/providers`, `/datasets`, `/jobs` | JobStarted/Completed   |
| Buscar obra     | Búsqueda tolerante              | `/search`                        | —                        |
| Resolver obra   | Crear resolución                | `POST /resolve`                  | Job*, Stage*             |
| Resultados      | Ver `ResolveResult`             | `/jobs/{id}`                     | JobCompleted             |
| Biblioteca      | Listar/abrir scores guardados   | `/library`                       | LibraryStored            |
| Datasets        | Instalar/verificar datasets     | `/datasets`                      | DatasetInstalled         |
| Proveedores     | Ver catálogos y capacidades     | `/providers`                     | ProviderStarted/Finished |
| Knowledge Base  | Ver estadísticas de aprendizaje | `/providers`, `/jobs`            | —                        |
| Configuración   | Editar `UserProfile`/settings   | `/settings`, `/users`            | —                        |
| Monitor         | Logs y eventos en tiempo real   | `/events` (WebSocket/SSE)        | todos                    |
| Historial       | Jobs anteriores                 | `/jobs`                          | —                        |

## Patrones

- **Progreso:** toda operación larga devuelve `{ job_id, type, state }`; la UI
  muestra una barra usando los eventos `JobSubmitted/Started/Completed/Failed`
  y `Stage*` del EventBus.
- **Cola de trabajos:** `/jobs` lista `Job { id, type, state, progress, logs,
  started_at, finished_at, result }`.
- **Cancelación:** `POST /jobs/{id}/cancel` → el `Job` pasa a `cancelled`.
- **Resolución:** `POST /resolve` → si hay varias versiones, el `ResolveResult`
  expone el ranking; la UI permite elegir (o `osap download`).
- **Calidad:** `QualityReport` (dimensiones independientes) → `QualityLevel`;
  Chorus decide qué materiales generar según el nivel.

## Reglas

- El frontend nunca importa el paquete Python `osap`.
- Los contratos son: `WorkDescriptor`, `CandidateRepresentation`, `ResolveResult`,
  `QualityReport`, `Job`, `Event`, `UserProfile`, `DatasetDescriptor`.
- Sin estados globales mutables compartidos; los eventos impulsan la UI.
