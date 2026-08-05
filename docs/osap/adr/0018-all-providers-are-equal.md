# ADR-0018 – Todos los proveedores son iguales

## Estado

Aceptado.

## Contexto

OSAP integra múltiples fuentes de representaciones musicales: IMSLP, MuseScore,
CPDL, OpenScore, PDMX, Filesystem y también **Open Music Repository (OMR)**. Existe
la tentación de tratar a OMR como "algo especial" (un repositorio propio con
privilegios o un camino de integración distinto al de los demás). Eso acoplaría OSAP
a OMR y rompería su independencia.

## Decisión

**Para OSAP todos los proveedores son iguales.** No existe un camino especial para
OMR ni para ningún otro. Todos implementan exactamente la misma interfaz
`ICatalogProvider`:

```
search(SearchRequest)     -> tuple[CandidateRepresentation, ...]
resolve(WorkDescriptor)   -> CandidateRepresentation | None
download(candidate)       -> AcquisitionResult
metadata()                -> CatalogInfo
capabilities()            -> CatalogCapabilities
```

### Consecuencias

- No hay código condicional por proveedor en el núcleo de OSAP.
- Añadir un proveedor nuevo (incluido OMR) es solo registrar otra implementación
  de `ICatalogProvider`.
- OSAP **consulta** OMR igual que consulta IMSLP, MuseScore o PDMX. OSAP no
  publica nada en OMR; OMR ya contiene sus propios recursos.
- La lógica de negocio (ranking, fusión, elección) permanece en el núcleo de OSAP.
- Refuerza el principio de **Provider autonomy** definido en
  `docs/osap/v2/provider-contract.md`.
