# ADR-0019 – Búsqueda en dos fases (OSAP responde preguntas musicales)

## Estado

Aceptado.

## Contexto

OSAP integra proveedores de representaciones (IMSLP, MuseScore, CPDL, OpenScore,
Filesystem, PDMX, OMR). Surge la tentación de delegar consultas complejas a un
proveedor concreto (por ejemplo, preguntar directamente a Open Music Repository
por una obra y sus recursos). Eso acoplaría OSAP a OMR y rompería la
intercambiabilidad de proveedores.

## Decisión

La búsqueda de OSAP es **siempre de dos fases**, nunca un diálogo directo con un
proveedor. El flujo es fijo:

```
Usuario
   ↓
OSAP Search      → pregunta musical
   ↓
Work             → identidad de la obra
   ↓
Resolve          → obra concreta
   ↓
Provider         → proveedor (todos iguales)
   ↓
Download
```

- **OMR responde preguntas sobre sus recursos.**
- **OSAP responde preguntas musicales.**

No se vuelve a la idea de preguntar cosas complejas directamente a OMR.

### Consecuencias

- Ambos proyectos (OSAP y OMR) permanecen **independientes**.
- Puedes **sustituir OMR por otro proveedor** sin cambiar el núcleo de OSAP.
- La lógica de búsqueda musical (normalización, matcher, ranking, evidencia) vive
  exclusivamente en OSAP.
- Refuerza ADR-0018 (todos los proveedores son iguales) y el principio de
  **Provider autonomy** de `docs/osap/v2/provider-contract.md`.
