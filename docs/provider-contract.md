# Provider Contract — OSAP V2

> **Status: draft** (se congelará en V2.0 — Freeze public contracts).
>
> Documento más importante de la V2. Define **por escrito** el contrato que todo
> proveedor obedece. Antes de que IMSLP, MuseScore, OMR, CPDL, OpenScore,
> Filesystem o PDMX se implementen o amplíen, deben cumplir exactamente este
> contrato.

## Principio rector

Para OSAP, **todos los proveedores son iguales**. No existe un camino especial
para OMR ni para ningún otro. Todos implementan la interfaz `ICatalogProvider`:

```python
class ICatalogProvider(ABC):
    provider_id -> ProviderId
    search(request: ResolveRequest) -> tuple[CandidateRepresentation, ...]
    resolve(request: ResolveRequest) -> CandidateRepresentation | None
    download(candidate, output_format=None) -> AcquisitionResult
    metadata() -> CatalogInfo
    capabilities() -> CatalogCapabilities
```

Los tipos de dominio (`Work`, `Representation`, `Evidence`, `ResourceBundle`) son
parte del contrato público y se congelan en V2.0.

---

## 1. `search()`

### Entrada
`ResolveRequest` — texto, título, compositor, voces, formato, min_quality,
online/offline, proveedores permitidos/excluidos.

### Salida
`tuple[CandidateRepresentation, ...]` — cero o más candidatos. Cada candidato es
una **representación posible** de una obra.

### Reglas
- No debe fallar por un término sin resultados: devuelve tupla vacía.
- Es **best-effort**: puede devolver candidatos de distinta calidad.
- No bloquea en red indefinidamente: obedece timeouts del `ProviderExecutionPlan`.

### Errores
- Errores de red/transporte → el orquestador decide (reintento, degradación, salto).
- Errores de contrato (formato inesperado) → se reportan como diagnóstico, no como
  excepción que rompa la búsqueda global.

---

## 2. `resolve()`

### Entrada
`ResolveRequest` (igual que `search`).

### Salida
`CandidateRepresentation | None` — la **mejor** representación del proveedor para la
obra, o `None` si el proveedor no puede resolverla.

### Reglas
- Devuelve una sola representación candidata con sus **licencias** y **evidencia**.
- El proveedor no decide la elección final; solo propone. La elección la hace el
  `ProviderOrchestrator` + ranking/evidence.

### Representaciones y licencias
Cada `CandidateRepresentation` declara:
- formato (`OutputFormat`), proveedor, calidad, confianza, checksum, tamaño, ruta local.
- licencia y si es de dominio público.

---

## 3. `download()`

### Entrada
`candidate: CandidateRepresentation`, `output_format: OutputFormat | None`.

### Modos de acceso
| Modo | Descripción | Soporte |
|------|-------------|---------|
| **Acceso directo** | URL/endpoint directo, descarga sin interacción | vía `CatalogCapabilities.supports_download` |
| **Acceso manual** | Requiere elección/confirmación del usuario (lista numerada) | cuando hay varias versiones |
| **Streaming** | Obtener sin descargar todo; reproducir/transmitir | vía `CatalogCapabilities.supports_streaming` |

### Salida
`AcquisitionResult` — representación adquirida o reporte de fallo.

### Reglas
- OSAP decide e instala recursos cuando es necesario; solo pide aprobación si es
  estrictamente necesario.
- La descarga respeta costes y límites (ver §5).

---

## 4. `capabilities()` — qué soporta un proveedor

`CatalogCapabilities` es el contrato que el orquestador usa para decidir a quién
consultar. **Nada de listas de proveedores hardcodeadas.**

| Campo | Significado |
|-------|-------------|
| `supports_search` | Puede buscar |
| `supports_download` | Puede descargar |
| `supports_streaming` | Puede transmitir sin descargar todo |
| `offline` | Funciona sin red |
| `formats` | Formatos que ofrece |
| `public_domain_only` | Solo dominio público |
| `requires_auth` | Necesita credenciales |
| `metadata` | Datos adicionales del proveedor |

---

## 5. `costs` — coste de uso

OSAP debe **conocer el coste** de cada proveedor. No es un campo cosmético:
condiciona la orquestación (a quién preguntar, en qué orden, si paralelizar).

| Proveedor | Coste |
|-----------|-------|
| OMR | **Sí** (infraestructura de pago). Consultar de forma controlada. |
| IMSLP | No |
| Filesystem | No |
| PDMX / OpenScore / CPDL | No (públicos) |
| MuseScore | Según API/plan → declarado por el proveedor |

Propuesta: ampliar `CatalogCapabilities.metadata` (o añadir un campo de dominio
`CostLevel` ya existente) para que cada proveedor declare su coste de forma
estructurada, y que `ProviderExecutionPlan` lo tenga en cuenta.

---

## 6. `quality` — semántica

Significado de las métricas de calidad, de forma **consistente entre proveedores**:

- **`confidence`** — qué seguros estamos de que el candidato **es la obra buscada**
  (coincidencia de identidad con `WorkDescriptor`).
- **`quality`** — qué buena es la representación **en sí misma** (nivel de la fuente,
  notación, metadatos): el `QualityLevel` del dominio.
- **`completeness`** — qué completa está la obra en esa representación (movimientos
  completos, instrumentación, edición).

Regla: los tres se normalizan a una escala común (p. ej. 0–1) para que el
`ProviderResultAggregator` pueda comparar proveedores heterogéneos.

---

## 7. Contratos de dominio congelados (V2.0)

Se escriben y se congelan antes de implementar:
- `ResourceBundle` — agrupación de recursos de una obra.
- `Work` (`WorkDescriptor`) — identidad de la obra.
- `Representation` (`CandidateRepresentation`) — forma concreta.
- `Evidence` — justificación de por qué se eligió una representación.

---

## 8. Modelo mental

```
OSAP
  search()      -> tuple[CandidateRepresentation, ...]
  resolve()     -> CandidateRepresentation | None
  download()    -> AcquisitionResult
  capabilities()-> CatalogCapabilities  (incl. costs)
  quality       -> confidence | quality | completeness
```
```
consulta IMSLP
consulta MuseScore
consulta OMR
consulta PDMX
consulta Filesystem
...
```
Todos son `ICatalogProvider`. Nada más.
