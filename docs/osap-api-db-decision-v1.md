# OSAP — BD propia de osap-api: decisión (v1)

**Estado:** DECISIÓN CONFIRMADA (frontera de datos). Las obras de usuario quedan abiertas.
**Formulación:**

> BD propia de osap-api para **estado operativo persistente**; **nunca como copia ni caché
> autoritativa del catálogo de osap-storage**.

---

# 1. Principio de propiedad

- **Los proveedores son responsabilidad de osap-api**, como lo han sido desde el principio.
- **osap-storage es esencialmente el servidor de datos del catálogo.** No se le traslada el
  concepto de proveedor solo porque algunas obras tengan una procedencia determinada.
- Distinción clave: que storage almacene el **dato de proveedor asociado a una obra** no convierte
  al proveedor en un dominio propiedad de storage; es simplemente un **dato necesario para el
  registro del catálogo**.

---

# 2. Frontera de la BD de osap-api

## SÍ (vive en osap-api / su BD)

| Dominio | Dónde |
|---|---|
| `providers/*.yaml` (provider/endpoints/mapping/resources) | osap-api (configuración versionada) |
| Proveedores añadidos/activados dinámicamente | BD de osap-api |
| Configuración de conectores/proveedores | osap-api |
| Sugerencias de nuevas fuentes/proveedores | BD de osap-api |
| Auditoría de esas decisiones (aprobar/cancelar) | BD de osap-api |
| Configuración operativa persistente que decidamos conservar | BD de osap-api |

- La información de proveedor que osap-api necesita para una operación (p. ej. el voto) se obtiene
  y gestiona **desde osap-api** y se transmite a storage cuando corresponde.

## NO (vive en osap-storage — servidor de datos del catálogo)

| Dominio |
|---|
| Obras |
| Compositores |
| Relaciones del catálogo |
| Votos |
| Estadísticas |

## NO / PENDIENTE (abierto)

| Dominio | Nota |
|---|---|
| Obras de usuario | **Abierto deliberadamente.** Probablemente terminarán almacenadas en el entorno OSAP/storage, pero los **datos de gestión** asociados (propiedad, visibilidad, publicación, relaciones) requieren una decisión posterior sobre dónde viven. No se decide ni se implementa nada ahora. |
| Identidad / usuarios | No en la BD de osap-api (dominio de osap-auth). |

---

# 3. Conclusión

- La BD de osap-api aloja **solo estado operativo del propio proceso de osap-api**: proveedores,
  config de proveedores, sugerencias de fuentes y su auditoría, y config operativa conservada.
- **Nunca** obras, compositores, votos, estadísticas, obras de usuario (de momento) ni identidad.
- Es una frontera coherente con cómo ha funcionado OSAP desde el primer día: osap-api gestiona los
  proveedores; osap-storage es el servidor de datos del catálogo.

*Decisión v1 (2026-08) — frontera de datos confirmada; obras de usuario abiertas; nada implementado.*
